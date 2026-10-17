"""
Automated Integration Tests for TraceGuard AI

Verifies:
1. Model loading and artifact integrity.
2. Endpoint schemas and contract compliance.
3. Scoring output ranges and action policies.
4. Input validation (422 for invalid payloads).
5. History isolation: /score MUST NOT mutate history.
6. History update: /record updates history exactly once and idempotently.
7. Subsequent scoring properly utilizes updated history.
8. Networks endpoints and 404 handling.
9. Legacy payload compatibility (sender/receiver strings).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.service import service


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient):
    """GET /health must return status ok, model version, and loaded history."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "TraceGuard AI"
    assert data["model_version"] == "0.1.0"
    assert data["known_accounts"] > 0
    assert data["transactions_in_history"] > 0


def test_score_contract_and_ranges(client: TestClient):
    """POST /score must return valid 0-1 risk score and matching actions."""
    payload = {
        "transaction_id": "TEST-SCORE-001",
        "sender_account_id": 10,
        "receiver_account_id": 13,
        "amount": 120.5,
        "step": 125,
        "sender_balance": 300.0,
    }
    response = client.post("/score", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["transaction_id"] == "TEST-SCORE-001"
    assert 0.0 <= data["risk_score"] <= 1.0
    assert data["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert data["recommended_action"] in {"ALLOW", "REVIEW", "HOLD"}
    expected_action = {"LOW": "ALLOW", "MEDIUM": "REVIEW", "HIGH": "HOLD"}[data["risk_level"]]
    assert data["recommended_action"] == expected_action
    assert isinstance(data["reasons"], list)
    assert isinstance(data["sender_known"], bool)
    assert isinstance(data["receiver_known"], bool)
    assert data["model_version"] == "0.1.0"
    assert data["latency_ms"] >= 0.0


def test_invalid_inputs_produce_validation_errors(client: TestClient):
    """Invalid input values must trigger 422 Unprocessable Entity."""
    # Negative amount
    res1 = client.post(
        "/score",
        json={"sender_account_id": 10, "receiver_account_id": 13, "amount": -10.0, "step": 125},
    )
    assert res1.status_code == 422
    assert "validation_error" in res1.json()["error"]["type"]

    # Zero amount
    res2 = client.post(
        "/score",
        json={"sender_account_id": 10, "receiver_account_id": 13, "amount": 0.0, "step": 125},
    )
    assert res2.status_code == 422

    # Negative step
    res3 = client.post(
        "/score",
        json={"sender_account_id": 10, "receiver_account_id": 13, "amount": 50.0, "step": -1},
    )
    assert res3.status_code == 422


def test_score_does_not_modify_history(client: TestClient):
    """
    CRITICAL CONTRACT: POST /score evaluates against history strictly
    WITHOUT adding the transaction to history.
    """
    test_sender = 88881
    test_receiver = 88882

    # Check store state before
    before_out = len(service.scorer.store.out.get(test_sender, ([], [], []))[0])
    before_inc = len(service.scorer.store.inc.get(test_receiver, ([], [], []))[0])

    payload = {
        "transaction_id": "TEST-NO-LEAK-01",
        "sender_account_id": test_sender,
        "receiver_account_id": test_receiver,
        "amount": 250.0,
        "step": 140,
    }

    # Score multiple times
    res1 = client.post("/score", json=payload)
    assert res1.status_code == 200
    res2 = client.post("/score", json=payload)
    assert res2.status_code == 200

    # Store state MUST be identical to before
    after_out = len(service.scorer.store.out.get(test_sender, ([], [], []))[0])
    after_inc = len(service.scorer.store.inc.get(test_receiver, ([], [], []))[0])

    assert before_out == after_out
    assert before_inc == after_inc
    assert not service.scorer.store.is_known(test_sender)
    assert not service.scorer.store.is_known(test_receiver)


def test_record_updates_history_and_affects_subsequent_scoring(client: TestClient):
    """
    CRITICAL CONTRACT:
    1. POST /record updates history for settled transactions.
    2. Repeated calls with the same transaction_id are idempotent.
    3. Subsequent scoring reflects the updated history.
    """
    s_acc = 9991
    r_acc = 9992
    step_t1 = 141
    step_t2 = 142

    # Before record: pair_cnt should be 0
    f_before = service.scorer.store.features(s_acc, r_acc, amount=100.0, step=step_t2)
    assert f_before.iloc[0]["pair_cnt"] == 0

    # Record first transaction
    rec_payload = {
        "transaction_id": "TX-RECORD-UNIQUE-1",
        "sender_account_id": s_acc,
        "receiver_account_id": r_acc,
        "amount": 150.0,
        "step": step_t1,
    }
    rec_res = client.post("/record", json=rec_payload)
    assert rec_res.status_code == 204

    # Now the accounts are known
    assert service.scorer.store.is_known(s_acc)
    assert service.scorer.store.is_known(r_acc)

    # Subsequent features at step_t2 > step_t1 must see the recorded transfer
    f_after = service.scorer.store.features(s_acc, r_acc, amount=100.0, step=step_t2)
    assert f_after.iloc[0]["pair_cnt"] == 1
    assert f_after.iloc[0]["s_out_cnt"] == f_before.iloc[0]["s_out_cnt"] + 1
    assert f_after.iloc[0]["r_in_cnt"] == f_before.iloc[0]["r_in_cnt"] + 1

    # Idempotency check: recording the exact same transaction ID again must not double-count
    rec_dup = client.post("/record", json=rec_payload)
    assert rec_dup.status_code == 204
    f_after_dup = service.scorer.store.features(s_acc, r_acc, amount=100.0, step=step_t2)
    assert f_after_dup.iloc[0]["pair_cnt"] == 1


def test_batch_score_endpoint(client: TestClient):
    """POST /score/batch evaluates multiple transactions."""
    batch_payload = {
        "transactions": [
            {"transaction_id": "B1", "sender_account_id": 10, "receiver_account_id": 13, "amount": 50.0, "step": 125},
            {"transaction_id": "B2", "sender_account_id": 13, "receiver_account_id": 10, "amount": 75.0, "step": 126},
        ]
    }
    res = client.post("/score/batch", json=batch_payload)
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) == 2
    assert results[0]["transaction_id"] == "B1"
    assert results[1]["transaction_id"] == "B2"


def test_networks_endpoints(client: TestClient):
    """GET /networks and GET /networks/{id} return expected data."""
    # List networks
    res = client.get("/networks?limit=3")
    assert res.status_code == 200
    networks = res.json()
    assert len(networks) == 3
    net1 = networks[0]
    assert "network_id" in net1
    assert "accounts" in net1
    assert "mean_account_score" in net1
    assert "pattern_hint" in net1

    # Retrieve specific network
    net_id = net1["network_id"]
    res_single = client.get(f"/networks/{net_id}")
    assert res_single.status_code == 200
    assert res_single.json()["network_id"] == net_id

    # 404 on nonexistent network
    res_404 = client.get("/networks/NET-NONEXISTENT")
    assert res_404.status_code == 404


def test_legacy_format_compatibility(client: TestClient):
    """Verify compatibility with frontend string IDs like 'ACC101'."""
    legacy_payload = {
        "transaction_id": "LEGACY-001",
        "sender": "ACC101",
        "receiver": "ACC205",
        "amount": 250.0,
        "timestamp": "2026-10-17T10:30:00",
    }
    res = client.post("/score", json=legacy_payload)
    assert res.status_code == 200
    assert res.json()["transaction_id"] == "LEGACY-001"


def test_ego_network_endpoint(client: TestClient):
    """GET /networks/ego/{account_id} returns ego network nodes and edges."""
    res = client.get("/networks/ego/10?hops=2&max_nodes=30")
    assert res.status_code == 200
    data = res.json()
    assert data["center"] == 10
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)
    assert len(data["nodes"]) > 0
