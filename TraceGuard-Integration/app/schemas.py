"""Pydantic request and response schemas conforming to INTEGRATION.md."""
from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _extract_int_id(val: Any) -> Optional[int]:
    """Helper to extract integer account ID from int or strings like 'ACC101' -> 101."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        val_clean = val.strip()
        if val_clean.isdigit():
            return int(val_clean)
        # Extract digits if string contains prefix like 'ACC101'
        match = re.search(r"\d+", val_clean)
        if match:
            return int(match.group(0))
    return None


class ScoreRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "transaction_id": "TX-1001",
                "sender_account_id": 10,
                "receiver_account_id": 13,
                "amount": 120.5,
                "step": 125,
                "sender_balance": 300.0,
            }
        },
    )

    transaction_id: Optional[str] = Field(None, description="Caller's id; echoed back in the response")
    sender_account_id: int = Field(..., description="Sender account integer ID")
    receiver_account_id: int = Field(..., description="Receiver account integer ID")
    amount: float = Field(..., gt=0, description="Transaction amount (must be positive)")
    step: int = Field(
        ...,
        ge=0,
        description="Integer time step of the transaction (same unit as training data). Steps must be non-decreasing across live calls.",
    )
    sender_balance: Optional[float] = Field(
        None, gt=0, description="Sender's balance/limit for amount-to-balance ratio; optional"
    )

    @model_validator(mode="before")
    @classmethod
    def accommodate_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        # Map legacy 'sender' -> 'sender_account_id' if not provided
        if "sender_account_id" not in d and "sender" in d:
            parsed = _extract_int_id(d["sender"])
            if parsed is not None:
                d["sender_account_id"] = parsed

        # Map legacy 'receiver' -> 'receiver_account_id' if not provided
        if "receiver_account_id" not in d and "receiver" in d:
            parsed = _extract_int_id(d["receiver"])
            if parsed is not None:
                d["receiver_account_id"] = parsed

        # Map legacy 'timestamp' -> 'step' if step not provided
        if "step" not in d and "timestamp" in d:
            # Default step to 125 (demo stream start) if only datetime given
            d["step"] = 125

        return d

    @model_validator(mode="after")
    def sender_and_receiver_differ(self):
        # We allow self-transfers since dataset has them and flags them, but record warning
        return self


class Reason(BaseModel):
    code: str
    description: str


class ScoreResponse(BaseModel):
    transaction_id: Optional[str] = None
    risk_score: float = Field(..., ge=0, le=1, description="Risk score 0-1 (higher = riskier)")
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    recommended_action: Literal["ALLOW", "REVIEW", "HOLD"]
    reasons: list[Reason]
    sender_known: bool
    receiver_known: bool
    model_version: str
    latency_ms: float


class BatchScoreRequest(BaseModel):
    transactions: list[ScoreRequest] = Field(..., max_length=1000)


class BatchScoreResponse(BaseModel):
    results: list[ScoreResponse]


class NetworkSummary(BaseModel):
    network_id: str
    accounts: list[int]
    n_accounts: int
    n_transactions: int
    total_amount: float
    mean_account_score: float
    pattern_hint: str
    hub_account: int
    hub_in_degree: int


class EgoNode(BaseModel):
    id: int
    risk_score: Optional[float] = None


class EgoEdge(BaseModel):
    source: int
    target: int
    tx_count: int
    total_amount: float


class EgoNetworkResponse(BaseModel):
    center: int
    nodes: list[EgoNode]
    edges: list[EgoEdge]


class HealthResponse(BaseModel):
    status: str
    service: str
    model_version: str
    known_accounts: int
    transactions_in_history: int
