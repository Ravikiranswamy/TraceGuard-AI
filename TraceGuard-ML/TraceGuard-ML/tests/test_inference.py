"""Inference-layer tests (need models/tx_model.joblib and the dataset: run steps 1 and 4 first)."""
import pytest

from traceguard import config as C

pytest.importorskip("fastapi")
if not (C.MODELS_DIR / "tx_model.joblib").exists() or not (C.DATA_RAW / C.DATASET_NAME / "transactions.csv").exists():
    pytest.skip("run scripts 01 and 04 first", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from api_example.main import app  # noqa: E402
from traceguard.inference import TraceGuardScorer  # noqa: E402

REQ = {"transaction_id": "T1", "sender_account_id": 10, "receiver_account_id": 13, "amount": 120.5, "step": 125}


def test_score_contract_and_ranges():
    res = TraceGuardScorer.from_dataset(up_to_step=C.TX_VAL_END).score(REQ)
    assert 0 <= res.risk_score <= 1
    assert res.risk_level in {"LOW", "MEDIUM", "HIGH"}
    assert res.recommended_action == {"LOW": "ALLOW", "MEDIUM": "REVIEW", "HIGH": "HOLD"}[res.risk_level]
    assert res.transaction_id == "T1"


def test_unknown_accounts_do_not_crash():
    res = TraceGuardScorer.from_dataset(up_to_step=50).score({**REQ, "sender_account_id": 10**9, "receiver_account_id": 10**9 + 1})
    assert not res.sender_known and not res.receiver_known


def test_score_ignores_future_history():
    """Scoring a step-125 transaction must give the same answer whether or not later data is in the store."""
    a = TraceGuardScorer.from_dataset(up_to_step=124).score(REQ).risk_score
    b = TraceGuardScorer.from_dataset(up_to_step=149).score(REQ).risk_score
    assert a == b


def test_http_endpoints():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        r = client.post("/score", json=REQ)
        assert r.status_code == 200 and set(r.json()) >= {"risk_score", "risk_level", "recommended_action", "reasons"}
        assert client.post("/score", json={**REQ, "amount": -5}).status_code == 422       # validation
        assert client.post("/score/batch", json={"transactions": [REQ, REQ]}).status_code == 200
        assert client.get("/networks?limit=3").status_code == 200
