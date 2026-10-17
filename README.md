# TraceGuard AI — Real-Time Anti-Money Laundering & Mule Network Detection

**TraceGuard AI** is built for the **IBM Z Datathon 2026** to detect suspicious financial transactions before authorization and uncover complex money-mule networks using machine learning and graph algorithms.

---

## 📁 Repository Structure

```text
TraceGuard-AI/
├── IBM Backend/              # Original FastAPI backend service
│   └── TraceGuard-Backend/
│       ├── main.py
│       └── requirements.txt
├── TraceGuard-ML/            # Machine learning pipeline and models
│   └── TraceGuard-ML/
│       ├── traceguard/       # Feature engineering & inference core
│       ├── models/           # Trained models (tx_model, account_model)
│       ├── reports/          # Evaluation metrics & suspicious networks
│       ├── scripts/          # Training & data inspection pipeline
│       └── tests/            # ML feature correctness tests
└── TraceGuard-Integration/   # Production-ready integrated backend
    ├── app/
    │   ├── main.py           # FastAPI endpoints (/score, /record, /networks)
    │   ├── service.py        # Model lifecycle and HistoryStore management
    │   ├── schemas.py        # Pydantic v2 schemas conforming to ML contract
    │   └── config.py         # Portable paths for Windows and IBM LinuxONE
    ├── tests/                # Comprehensive end-to-end integration tests
    └── requirements.txt      # Production dependencies
```

---

## ⚡ Quick Start (Integrated Service)

### 1. Installation
```bash
cd TraceGuard-Integration
python -m pip install -r requirements.txt
```

### 2. Run Tests
```bash
python -m pytest -v
```

### 3. Launch API Server
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive API docs: `http://localhost:8000/docs`.

---

## 🛡️ Key Features

- **Pre-Authorization Scoring**: Millisecond-level inference determining transaction risk before settlement (`POST /score`).
- **No Historical Leakage**: Features strictly evaluate against prior transactions; `/score` does not mutate history.
- **Auditable Lifecycle**: Settled transactions are recorded into the behavioural store exactly once via `POST /record`.
- **Mule Network Discovery**: Surfaces communities of suspected mule accounts precomputed with Louvain clustering (`GET /networks`).
- **Graph Visualization**: Interactive ego-networks for investigator dashboards (`GET /networks/ego/{account_id}`).
