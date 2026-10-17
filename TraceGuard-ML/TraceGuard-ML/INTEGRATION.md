# Integration guide for Friend 2 (FastAPI backend)

## What the ML component gives you
| Capability | How | Latency |
|---|---|---|
| Score ONE transaction before authorization | `TraceGuardScorer.score(request)` / `POST /score` | ~4-5 ms |
| Batch scoring (<=1000) | `POST /score/batch` | ~5 ms each |
| Suspicious networks list (precomputed offline) | `GET /networks`, `GET /networks/{id}` | instant |
| Account ego-network for a graph widget | `traceguard.networks.ego_network(tx, account)` | ~ms |

A reference FastAPI app is in `api_example/main.py`:
```powershell
python -m pip install fastapi uvicorn
python -m uvicorn api_example.main:app --reload       # open http://127.0.0.1:8000/docs
```
To embed instead of calling over HTTP: `pip install -e .` in this folder, then `from traceguard.inference import TraceGuardScorer`.

## Input - `POST /score`
```json
{
  "transaction_id": "TX-1001",
  "sender_account_id": 10,
  "receiver_account_id": 13,
  "amount": 120.5,
  "step": 125,
  "sender_balance": 300.0
}
```
| Field | Required | Notes |
|---|---|---|
| transaction_id | no | echoed back |
| sender_account_id, receiver_account_id | yes | integers (training ids). Map your account ids to ints, or tell me and I will switch to strings |
| amount | yes | > 0, same currency scale as training data |
| step | yes | integer time step, **non-decreasing across live calls**. Real system: use e.g. day index since a fixed start date; the model's velocity window is 7 steps |
| sender_balance | no | if omitted, falls back to the balance known to the scorer, else the ratio feature is NaN (model handles it) |

## Output
```json
{
  "transaction_id": "TX-1001",
  "risk_score": 0.998,
  "risk_level": "HIGH",
  "recommended_action": "HOLD",
  "reasons": [{"code": "AMOUNT_BELOW_NORMAL_RANGE", "description": "..."}],
  "sender_known": true,
  "receiver_known": true,
  "model_version": "0.1.0",
  "latency_ms": 4.6
}
```
* `risk_score` 0-1 (higher = riskier). Not a calibrated probability.
* `risk_level`/`recommended_action`: score >= 0.879 -> HIGH/HOLD; >= 0.605 -> MEDIUM/REVIEW; else LOW/ALLOW. Thresholds live in `models/tx_model.joblib` (`thr_high`, `thr_medium`) - the business should own the final policy.
* `reasons`: rule-based codes (`REPEATED_COUNTERPARTY, REVERSE_FLOW, RECEIVER_HIGH_FAN_IN, AMOUNT_ABOVE_SENDER_NORM, AMOUNT_BELOW_NORMAL_RANGE`); only returned for MEDIUM/HIGH and can be empty.
* `sender_known/receiver_known = false` -> cold start: no history for that account, treat the score with less trust.
* Validation errors (e.g. negative amount) -> HTTP 422 from FastAPI.

## REQUIRED backend behaviour
1. **History:** the scorer needs past transactions. At startup build `TraceGuardScorer(history_df, balances)` from your DB (columns `sourceNodeId, targetNodeId, value, time`).
2. **After a transaction is processed (allowed or settled) call `POST /record`** (`scorer.record(req)`) so it becomes history. Do not record blocked transactions unless you want them to count.
3. Keep one scorer instance per process; it holds history in memory (tested here with ~120K transactions; for much larger volumes plan a feature store / database-backed history).
4. Never send future-dated steps relative to already recorded ones.

## Networks - `GET /networks`
`[{"network_id":"NET-0001","accounts":[6506,8057,...],"n_accounts":9,"n_transactions":37,"total_amount":2648.69,"mean_account_score":0.9959,"pattern_hint":"cycle","hub_account":14232,"hub_in_degree":3}]`
Precomputed by `scripts/03_train_account_model.py` -> `reports/suspicious_networks.json`. `pattern_hint` is weak on this dataset (almost all communities contain cycles).

## Files you may need
`models/tx_model.joblib` (shipped model + thresholds) | `models/account_model.joblib` | `reports/*.json` | `traceguard/schemas.py` (pydantic models you can import directly).
Models were trained with the scikit-learn version recorded in the joblib (`sklearn_version`); use the same major version in the backend.
