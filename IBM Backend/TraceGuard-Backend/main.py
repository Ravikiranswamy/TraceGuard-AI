"""
TraceGuard AI - Backend API (Milestone 1)

Run:   python -m uvicorn main:app --reload
Docs:  http://127.0.0.1:8000/docs

IMPORTANT
---------
Scoring in this version is a TEMPORARY MOCK based on simple hand-written rules.
It is NOT an AI prediction and says nothing about real fraud-detection
performance. Every response is labelled `is_mock: true` so nobody mistakes it
for a trained-model output.

File layout (everything is in this one file for now; each section is written so
it can be moved into its own module later, e.g. schemas.py / scoring.py /
network.py):

    1. Schemas          - request / response models + validation
    2. Feature prep     - turns a transaction into model inputs      (Friend 1 will refine)
    3. Scorer interface - the swap point for Friend 1's trained model
    4. Mock scorer      - temporary placeholder
    5. Network analysis - NetworkX account graph                     (to refine after dataset review)
    6. Assessment       - combines scorer output + network evidence
    7. API endpoints
"""

import threading
from datetime import datetime
from enum import Enum
from typing import Protocol

import networkx as nx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

SERVICE_NAME = "TraceGuard AI"
MAX_AMOUNT = 1_000_000_000_000  # sanity ceiling; adjust once the dataset is known


# =============================================================================
# 1. SCHEMAS
# =============================================================================
# The request format is PROVISIONAL. It may change after Friend 1 inspects the
# real dataset. Keep all request/response shape changes in this section.


class TransactionRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "transaction_id": "TXN001",
                "sender": "ACC101",
                "receiver": "ACC205",
                "amount": 25000,
                "timestamp": "2026-10-17T10:30:00",
            }
        },
    )

    transaction_id: str = Field(min_length=1, max_length=64)
    sender: str = Field(min_length=1, max_length=64)
    receiver: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0, le=MAX_AMOUNT, allow_inf_nan=False)
    timestamp: datetime

    @model_validator(mode="after")
    def sender_and_receiver_differ(self):
        if self.sender == self.receiver:
            raise ValueError("sender and receiver must be different accounts")
        return self


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RecommendedAction(str, Enum):
    APPROVE = "APPROVE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    HOLD_AND_ESCALATE = "HOLD_AND_ESCALATE"


class Reason(BaseModel):
    code: str
    description: str
    source: str  # "mock_rules" | "network_analysis" (later: "ml_model")
    points: float = 0  # contribution to the risk score


class NetworkEvidence(BaseModel):
    """Relationship facts about the accounts, based on PRIOR transactions only."""

    prior_transfers_between_pair: int
    sender_distinct_receivers: int
    receiver_distinct_senders: int
    receiver_distinct_recipients: int
    accounts_in_history: int
    transactions_in_history: int
    note: str = (
        "In-memory history only: reflects transactions scored since the server "
        "started. It is not a full dataset analysis."
    )


class ScoringInfo(BaseModel):
    engine: str
    is_mock: bool
    note: str


class ScoreResponse(BaseModel):
    transaction_id: str
    risk_score: float = Field(description="0 (lowest risk) to 100 (highest risk)")
    risk_level: RiskLevel
    reasons: list[Reason]
    recommended_action: RecommendedAction
    recommended_action_detail: str
    network_evidence: NetworkEvidence
    scoring: ScoringInfo


# =============================================================================
# 2. FEATURE PREPARATION
# =============================================================================
# PLACEHOLDER features, used only by the mock scorer. Friend 1 decides the real
# model features after inspecting the dataset; replace this function then.


def prepare_features(txn: TransactionRequest) -> dict[str, float | int | bool]:
    return {
        "amount": txn.amount,
        "hour_of_day": txn.timestamp.hour,
        "is_round_amount": txn.amount >= 10_000 and txn.amount % 1000 == 0,
    }


# =============================================================================
# 3. SCORER INTERFACE  (the swap point for the real AI model)
# =============================================================================
# To integrate Friend 1's model:
#   1. Write a class with the same `name`, `is_mock` and `score()` signature
#      (e.g. `class TrainedModelScorer`) that loads the model and returns
#      a ScorerOutput with is_mock=False.
#   2. Change what `get_scorer()` returns (section 7).
# Nothing else in the app should need to change.


class ScorerOutput(BaseModel):
    score: float  # 0-100
    reasons: list[Reason]
    engine: str
    is_mock: bool


class RiskScorer(Protocol):
    name: str
    is_mock: bool

    def score(self, features: dict[str, float | int | bool]) -> ScorerOutput: ...


# =============================================================================
# 4. MOCK SCORER  (TEMPORARY - NOT AN AI MODEL)
# =============================================================================


class MockRiskScorer:
    """Simple hand-written rules so the API has something to return.

    Thresholds and point values are arbitrary placeholders. They are NOT derived
    from data and must not be presented as real detection logic.
    """

    name = "mock_rules_v0"
    is_mock = True

    def score(self, features: dict[str, float | int | bool]) -> ScorerOutput:
        reasons: list[Reason] = []
        amount = float(features["amount"])

        if amount >= 100_000:
            reasons.append(Reason(
                code="HIGH_AMOUNT",
                description="Transaction amount is very high (mock rule: >= 100,000).",
                source="mock_rules", points=40))
        elif amount >= 50_000:
            reasons.append(Reason(
                code="ELEVATED_AMOUNT",
                description="Transaction amount is high (mock rule: >= 50,000).",
                source="mock_rules", points=25))
        elif amount >= 10_000:
            reasons.append(Reason(
                code="MODERATE_AMOUNT",
                description="Transaction amount is moderately large (mock rule: >= 10,000).",
                source="mock_rules", points=10))

        if features["is_round_amount"]:
            reasons.append(Reason(
                code="ROUND_AMOUNT",
                description="Amount is an exact multiple of 1,000 (mock rule).",
                source="mock_rules", points=5))

        if int(features["hour_of_day"]) < 6:
            reasons.append(Reason(
                code="UNUSUAL_HOUR",
                description="Transaction occurred between 00:00 and 05:59 (mock rule).",
                source="mock_rules", points=15))

        return ScorerOutput(
            score=sum(r.points for r in reasons),
            reasons=reasons,
            engine=self.name,
            is_mock=self.is_mock,
        )


# =============================================================================
# 5. ACCOUNT-NETWORK ANALYSIS (NetworkX)
# =============================================================================
# Accounts are nodes; a transfer sender -> receiver is a directed edge. Each
# edge remembers which transaction IDs it contains, so re-scoring the same
# transaction never double-counts it.
#
# Currently in-memory only (lost on restart). Later this can be built from the
# real dataset instead (e.g. loaded with pandas at startup).


class TransactionGraph:
    def __init__(self) -> None:
        self._g = nx.DiGraph()
        self._txn_ids: set[str] = set()
        self._lock = threading.Lock()

    def analyze(self, txn: TransactionRequest) -> NetworkEvidence:
        """Describe the accounts using PRIOR transactions (excluding this one)."""
        tid = txn.transaction_id
        with self._lock:
            g = self._g

            def prior(data: dict) -> bool:
                return bool(data["txn_ids"] - {tid})

            pair = g.get_edge_data(txn.sender, txn.receiver)
            pair_count = len(pair["txn_ids"] - {tid}) if pair else 0

            def count(edges) -> int:
                return sum(1 for _, _, d in edges if prior(d))

            return NetworkEvidence(
                prior_transfers_between_pair=pair_count,
                sender_distinct_receivers=(
                    count(g.out_edges(txn.sender, data=True)) if txn.sender in g else 0),
                receiver_distinct_senders=(
                    count(g.in_edges(txn.receiver, data=True)) if txn.receiver in g else 0),
                receiver_distinct_recipients=(
                    count(g.out_edges(txn.receiver, data=True)) if txn.receiver in g else 0),
                accounts_in_history=g.number_of_nodes(),
                transactions_in_history=len(self._txn_ids - {tid}),
            )

    def record(self, txn: TransactionRequest) -> None:
        """Add the transaction to the graph (safe to call twice for the same ID)."""
        with self._lock:
            if self._g.has_edge(txn.sender, txn.receiver):
                self._g[txn.sender][txn.receiver]["txn_ids"].add(txn.transaction_id)
            else:
                self._g.add_edge(txn.sender, txn.receiver, txn_ids={txn.transaction_id})
            self._txn_ids.add(txn.transaction_id)


def network_reasons(ev: NetworkEvidence) -> list[Reason]:
    """PROVISIONAL network rules. Thresholds are placeholders to be refined
    once the dataset has been inspected."""
    reasons: list[Reason] = []

    if ev.prior_transfers_between_pair >= 3:
        reasons.append(Reason(
            code="REPEATED_TRANSFERS",
            description=(f"{ev.prior_transfers_between_pair} earlier transfers already "
                         "recorded between this sender and receiver."),
            source="network_analysis", points=20))

    if ev.receiver_distinct_senders >= 5:
        reasons.append(Reason(
            code="RECEIVER_FAN_IN",
            description=(f"Receiver has already received from "
                         f"{ev.receiver_distinct_senders} distinct accounts."),
            source="network_analysis", points=25))

    if ev.sender_distinct_receivers >= 5:
        reasons.append(Reason(
            code="SENDER_FAN_OUT",
            description=(f"Sender has already sent to "
                         f"{ev.sender_distinct_receivers} distinct accounts."),
            source="network_analysis", points=15))

    if ev.receiver_distinct_senders >= 1 and ev.receiver_distinct_recipients >= 1:
        reasons.append(Reason(
            code="RECEIVER_PASS_THROUGH",
            description="Receiver both receives and forwards funds in recorded history.",
            source="network_analysis", points=10))

    return reasons


# =============================================================================
# 6. ASSESSMENT  (validate -> features -> scorer -> network -> combine)
# =============================================================================

MEDIUM_THRESHOLD = 35  # provisional
HIGH_THRESHOLD = 70    # provisional

_ACTIONS = {
    RiskLevel.LOW: (RecommendedAction.APPROVE,
                    "No review needed based on current checks."),
    RiskLevel.MEDIUM: (RecommendedAction.MANUAL_REVIEW,
                       "Route to an analyst for review before authorization."),
    RiskLevel.HIGH: (RecommendedAction.HOLD_AND_ESCALATE,
                     "Hold the transaction and escalate for urgent investigation."),
}


def level_for(score: float) -> RiskLevel:
    if score >= HIGH_THRESHOLD:
        return RiskLevel.HIGH
    if score >= MEDIUM_THRESHOLD:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def assess_transaction(
    txn: TransactionRequest, scorer: RiskScorer, graph: TransactionGraph
) -> ScoreResponse:
    features = prepare_features(txn)               # step 3
    model_out = scorer.score(features)             # step 4
    evidence = graph.analyze(txn)                  # step 5
    net_reasons = network_reasons(evidence)

    # PROVISIONAL combination: model score + network points, capped at 100.
    total = min(100.0, model_out.score + sum(r.points for r in net_reasons))
    reasons = model_out.reasons + net_reasons
    if not reasons:
        reasons = [Reason(
            code="NO_INDICATORS",
            description="No suspicious indicators were triggered by the current checks.",
            source=model_out.engine)]

    level = level_for(total)
    action, detail = _ACTIONS[level]

    graph.record(txn)  # remember it for future network analysis

    return ScoreResponse(
        transaction_id=txn.transaction_id,
        risk_score=round(total, 1),
        risk_level=level,
        reasons=reasons,
        recommended_action=action,
        recommended_action_detail=detail,
        network_evidence=evidence,
        scoring=ScoringInfo(
            engine=model_out.engine,
            is_mock=model_out.is_mock,
            note=("TEMPORARY MOCK SCORE from hand-written rules. This is NOT an AI "
                  "prediction." if model_out.is_mock
                  else "Score produced by the trained model plus network analysis.")),
    )


# =============================================================================
# 7. API
# =============================================================================

app = FastAPI(
    title=SERVICE_NAME,
    description="Transaction risk scoring and money-mule network analysis. "
                "Scoring is currently a temporary mock.",
    version="0.1.0",
)

# Allow the React dev server (Friend 3) to call this API. Tighten for deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173",
                   "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_scorer: RiskScorer = MockRiskScorer()   # <-- swap in Friend 1's model here later
_graph = TransactionGraph()


def get_scorer() -> RiskScorer:
    return _scorer


def get_graph() -> TransactionGraph:
    return _graph


# ---- consistent error format -------------------------------------------------
# Every error looks like: {"error": {"type": ..., "message": ..., "details": [...]}}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"] if p != "body") or "request"
        message = err["msg"].removeprefix("Value error, ")
        details.append({"field": field, "message": message, "type": err["type"]})
    return JSONResponse(
        status_code=422,
        content={"error": {"type": "validation_error",
                           "message": "Invalid request data.",
                           "details": details}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"type": "http_error", "message": str(exc.detail), "details": []}},
    )


# ---- endpoints ---------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "running", "service": SERVICE_NAME}


@app.post("/score", response_model=ScoreResponse)
def score(
    txn: TransactionRequest,
    scorer: RiskScorer = Depends(get_scorer),
    graph: TransactionGraph = Depends(get_graph),
):
    return assess_transaction(txn, scorer, graph)
