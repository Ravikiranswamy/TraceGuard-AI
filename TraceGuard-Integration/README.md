# TraceGuard AI — Integrated Backend

Production integration for **TraceGuard AI** (IBM Z Datathon 2026), unifying the trained ML model (`TraceGuard-ML`) with the high-performance FastAPI service layer.

---

## 1. Architecture & Design Principles

1. **Source of Truth**: Implements Vidyashankar's `INTEGRATION.md` specifications and schemas directly.
2. **True ML Pre-Authorization Scoring**: Powered by the shipped `HistGradientBoostingClassifier` serialized in `tx_model.joblib`.
3. **No Historical Leakage**:
   - `POST /score` evaluates features strictly using transactions prior to the requested `step`.
   - Scoring never mutates the feature store.
   - `POST /record` idempotently appends settled transactions to `HistoryStore` exactly once after authorization.
4. **Original Project Preservation**: Both `IBM Backend/TraceGuard-Backend/` and `TraceGuard-ML/TraceGuard-ML/` remain untouched.
5. **Security**: Secrets and private keys (`tracguardkey1.pem`) are excluded from version control and never exposed.

---

## 2. API Contract

| Endpoint | Method | Request | Response | Description |
|---|---|---|---|---|
| `/health` | `GET` | None | `HealthResponse` | System status, model version, historical transactions count |
| `/score` | `POST` | `ScoreRequest` | `ScoreResponse` | Real-time pre-authorization scoring (4-5ms) |
| `/score/batch` | `POST` | `BatchScoreRequest` | `BatchScoreResponse` | Batch scoring up to 1,000 transactions |
| `/record` | `POST` | `ScoreRequest` | `204 No Content` | Appends settled transaction to history |
| `/networks` | `GET` | `limit` (query, default 20) | `list[NetworkSummary]` | Precomputed money-mule communities/networks |
| `/networks/{id}` | `GET` | None | `NetworkSummary` | Detailed network summary by ID (e.g. `NET-0001`) |
| `/networks/ego/{acc}` | `GET` | `hops`, `max_nodes` | `EgoNetworkResponse` | Ego-network graph around an account for UI visualization |

### Example Scoring Request (`POST /score`)
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

### Example Scoring Response
```json
{
  "transaction_id": "TX-1001",
  "risk_score": 0.998412,
  "risk_level": "HIGH",
  "recommended_action": "HOLD",
  "reasons": [
    {
      "code": "AMOUNT_BELOW_NORMAL_RANGE",
      "description": "Amount is below the range normally seen for ordinary transfers (dataset-specific signal)"
    }
  ],
  "sender_known": true,
  "receiver_known": true,
  "model_version": "0.1.0",
  "latency_ms": 4.5
}
```

---

## 3. Environment & Configuration

Environment variables can be configured or defaulted:

| Variable | Default | Description |
|---|---|---|
| `TG_ML_DIR` | Auto-detected relative to project | Path to `TraceGuard-ML/TraceGuard-ML` |
| `TG_MODEL_PATH` | `${TG_ML_DIR}/models/tx_model.joblib` | Path to trained transaction model |
| `TG_NETWORKS_PATH` | `${TG_ML_DIR}/reports/suspicious_networks.json` | Path to suspicious networks report |
| `TG_DATA_DIR` | `${TG_ML_DIR}/data/raw` | Path to raw AMLSim dataset |
| `TG_UP_TO_STEP` | `120` | Initial historical transactions step limit |
| `ALLOWED_ORIGINS` | `localhost:3000, localhost:5173, *` | CORS allowed origins |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |

---

## 4. Setup & Running Instructions

### Local Execution (Windows / PowerShell)

```powershell
cd TraceGuard-Integration

# Install dependencies with the documented scikit-learn version
python -m pip install -r requirements.txt

# Run automated tests
python -m pytest -v

# Start the API server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive documentation is available at: `http://127.0.0.1:8000/docs`.

### Linux / IBM LinuxONE Deployment

```bash
cd TraceGuard-Integration
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
