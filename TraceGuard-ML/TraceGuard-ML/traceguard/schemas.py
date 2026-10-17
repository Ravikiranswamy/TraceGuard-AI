"""Request/response contract between the FastAPI backend (Friend 2) and the ML component.
These are pydantic v2 models, so FastAPI can use them directly as request/response models."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    transaction_id: Optional[str] = Field(None, description="Caller's id; echoed back in the response")
    sender_account_id: int
    receiver_account_id: int
    amount: float = Field(..., gt=0)
    step: int = Field(..., ge=0, description="Integer time step of the transaction (same unit as training data). "
                                              "Steps must be non-decreasing across live calls.")
    sender_balance: Optional[float] = Field(None, gt=0, description="Sender's balance/limit for amount-to-balance ratio; optional")


class Reason(BaseModel):
    code: str
    description: str


class ScoreResponse(BaseModel):
    transaction_id: Optional[str]
    risk_score: float = Field(..., ge=0, le=1)
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
