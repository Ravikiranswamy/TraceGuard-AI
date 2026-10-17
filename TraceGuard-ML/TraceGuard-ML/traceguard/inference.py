"""Live scoring: one transaction in -> risk score, level, action and reason codes out."""
from __future__ import annotations

import time
from pathlib import Path

import joblib
import pandas as pd

from . import config as C
from .features import HistoryStore
from .schemas import Reason, ScoreRequest, ScoreResponse

_REASON_TEXT = {
    "REPEATED_COUNTERPARTY": "Sender has already sent money to this receiver at least twice",
    "REVERSE_FLOW": "Receiver has previously sent money back to the sender (round-tripping)",
    "RECEIVER_HIGH_FAN_IN": "Receiver collects money from an unusually large number of different senders",
    "AMOUNT_ABOVE_SENDER_NORM": "Amount is at least 2x the sender's usual transfer size",
    "AMOUNT_BELOW_NORMAL_RANGE": "Amount is below the range normally seen for ordinary transfers (dataset-specific signal)",
}


class TraceGuardScorer:
    def __init__(self, history: pd.DataFrame, balances: dict[int, float] | None = None,
                 model_path: Path = C.MODELS_DIR / "tx_model.joblib"):
        art = joblib.load(model_path)
        self.model, self.features = art["model"], art["features"]
        self.thr_high, self.thr_med = art["thr_high"], art["thr_medium"]
        self.reason_t, self.version = art["reason_thresholds"], art.get("version", "0")
        self.store = HistoryStore.from_dataframe(history)
        self.balances = balances or {}

    @classmethod
    def from_dataset(cls, up_to_step: int | None = None, name: str = C.DATASET_NAME) -> "TraceGuardScorer":
        """Convenience for demos/tests: history = the AMLSim transactions up to `up_to_step`."""
        from . import data as D
        nodes, tx, _ = D.clean(*D.load_raw(name))
        if up_to_step is not None:
            tx = tx[tx[C.TIME] <= up_to_step]
        return cls(tx, nodes.set_index(C.NODE_ID)[C.NODE_BAL].to_dict())

    # ------------------------------------------------------------------
    def score(self, req: ScoreRequest | dict) -> ScoreResponse:
        t0 = time.perf_counter()
        req = req if isinstance(req, ScoreRequest) else ScoreRequest(**req)
        bal = req.sender_balance if req.sender_balance is not None else self.balances.get(req.sender_account_id)
        f = self.store.features(req.sender_account_id, req.receiver_account_id, req.amount, req.step, bal)
        p = float(self.model.predict_proba(f[self.features])[:, 1][0])
        level = "HIGH" if p >= self.thr_high else "MEDIUM" if p >= self.thr_med else "LOW"
        action = {"HIGH": "HOLD", "MEDIUM": "REVIEW", "LOW": "ALLOW"}[level]
        return ScoreResponse(
            transaction_id=req.transaction_id, risk_score=round(p, 6), risk_level=level, recommended_action=action,
            reasons=self._reasons(f.iloc[0]) if level != "LOW" else [], sender_known=self.store.is_known(req.sender_account_id),
            receiver_known=self.store.is_known(req.receiver_account_id), model_version=self.version,
            latency_ms=round((time.perf_counter() - t0) * 1000, 2))

    def score_batch(self, reqs: list[ScoreRequest | dict]) -> list[ScoreResponse]:
        return [self.score(r) for r in reqs]

    def record(self, req: ScoreRequest | dict) -> None:
        """Call AFTER a transaction is processed so it becomes history for later transactions."""
        req = req if isinstance(req, ScoreRequest) else ScoreRequest(**req)
        self.store.add(req.sender_account_id, req.receiver_account_id, req.amount, req.step)

    def _reasons(self, r: pd.Series) -> list[Reason]:
        """Rule-based explanations (NOT model attributions). Only rules that showed real lift on held-out data are kept."""
        t, codes = self.reason_t, []
        if r["pair_cnt"] >= 2: codes.append("REPEATED_COUNTERPARTY")
        if r["reverse_pair_cnt"] >= 1: codes.append("REVERSE_FLOW")
        if r["r_in_uniq"] >= t["r_in_uniq_p95"]: codes.append("RECEIVER_HIGH_FAN_IN")
        if pd.notna(r["amt_vs_sender_avg_out"]) and r["amt_vs_sender_avg_out"] >= t["amt_vs_sender_avg_out_min"]: codes.append("AMOUNT_ABOVE_SENDER_NORM")
        if r["amount"] < t["low_amount_p05_of_normal"]: codes.append("AMOUNT_BELOW_NORMAL_RANGE")
        return [Reason(code=c, description=_REASON_TEXT[c]) for c in codes]
