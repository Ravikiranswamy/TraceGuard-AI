# TraceGuard AI — React Investigation Dashboard

A polished, responsive frontend for **IBM Z Datathon 2026** using **React 18, Vite, Recharts, Lucide icons and React Router**. UI stages 1 and 2 are structured so you can demonstrate now and connect the ML-backed FastAPI service later.

## Run on Windows (VS Code)

1. Install **Node.js LTS** from https://nodejs.org/. Restart VS Code.
2. Extract the ZIP. Open **TraceGuard-Aesthetic-Frontend** in VS Code.
3. In the VS Code terminal:

```powershell
npm.cmd install
npm.cmd run dev
```

4. Open **http://localhost:5173**. Use `npm.cmd` instead of `npm` if PowerShell blocks `npm.ps1`. On macOS/Linux run `npm install` and `npm run dev`.

For an optimized production build:

```powershell
npm.cmd run build
npm.cmd run preview
```

## The five screens

- **Overview** — a premium light-dashboard experience with navy navigation, a featured investigation banner, risk metrics, trends, distribution, priority alerts, sample transactions and backend/model connection indicators.
- **Risk check** — form validation, exact ML input field names, status/loading/error handling, readable result panel, reasons, source badges and quick sample examples.
- **Transaction history** — search, filter, pagination, CSV export, offline sample vs session checks and detail popovers.
- **Alerts & reviews** — HIGH/MEDIUM queue, risk ordering, investigation detail and **local-only** review toggles (no banking action performed).
- **Account networks** — candidate community summaries, selected membership information and a **separate** SVG showing only real observed edges from an AMLSim sample.

## Demo mode vs Live API

The sidebar defaults to **Demo** so the UI always works without FastAPI.

- **Offline report**: 120 real *precomputed ML test scores* from `TraceGuard-ML/reports/tx_test_scored.csv`, and 52 candidate communities from `TraceGuard-ML/reports/suspicious_networks.json`. These are **synthetic test outputs, not real banking activity or fresh API results**. Only a subset of the scored test output is supplied here.
- **Demo form**: if the submitted values exactly match one of the supplied offline records, the recorded score is shown and identified as an offline report score. Any other input produces an explicitly labelled, deterministic **mock heuristic score, NOT an AI prediction**.
- **Live API**: all submitted transactions go to `POST /score`. Scores must follow `TraceGuard-ML/INTEGRATION.md`; no fallback to a demo result on error.
- Session checks exist **only in browser memory** and can be viewed in Transaction history and Alerts. They are not server-side transaction-history records.
- Review ticks update browser session UI only. They do not cause holds, approvals, recordings or investigations in any real system.

## Configure FastAPI

Copy `.env.example` to `.env`:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

Restart Vite after changing the environment. Local Vite proxies `/api/*` to that host, so **you do not need to modify the ML reference FastAPI to enable CORS for local development**. For production, this environment variable is used as the browser-facing backend URL; configure the backend's CORS/HTTPS and origin accordingly. Never include credentials in `VITE_*` variables: values are bundled into the frontend.

To try the ML reference app (requires its dependencies, trained models, and downloaded dataset):

```powershell
# In extracted TraceGuard-ML folder, configure per that project's README
python -m uvicorn api_example.main:app --reload
```

After the Python server is running, select **Live API** in the sidebar. The `/health` response identifies whether a model version is exposed. Do not confuse API reachability with proving an actual trained model is loaded.

### ML scoring contract (exact field names)

`POST /score`

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

`transaction_id` and `sender_balance` are optional. `sender_account_id`, `receiver_account_id` and `step` are integers, amount > 0, and steps must be non-decreasing across requests to a stateful scoring service. Risk returns 0–1 (not necessarily a calibrated probability):

```json
{
  "transaction_id": "TX-1001",
  "risk_score": 0.998,
  "risk_level": "HIGH",
  "recommended_action": "HOLD",
  "reasons": [{ "code": "AMOUNT_BELOW_NORMAL_RANGE", "description": "..." }],
  "sender_known": true,
  "receiver_known": true,
  "model_version": "0.1.0",
  "latency_ms": 4.6
}
```

`src/services/api.js` implements `getHealth`, `scoreTransaction`, `getNetworks`, `getNetwork` and `recordTransaction` with explicit response validation and error messages.

**Important:** The supplied `IBM Backend.zip` implements a *different, legacy mock contract*: `sender`, `receiver`, `timestamp`, `risk_score` 0–100, action labels such as `HOLD_AND_ESCALATE`, and `scoring.is_mock`. It **cannot** be used as a trained-model API without backend changes. This frontend rejects legacy score replies instead of misrepresenting them.

### Planned backend integrations

| Endpoint | Frontend use | Verified where |
| --- | --- | --- |
| `GET /health` | Connectivity / model status | ML reference + legacy backend |
| `POST /score` | Live check | ML reference (not yet integrated into legacy backend) |
| `POST /record` | Exposed service function **only** | ML reference; must be called by backend **after allowed/settled** transactions. UI does **not** auto-record. |
| `GET /networks` | Candidate list (when available) | ML reference only |
| `GET /networks/{id}` | Selected summary (when available) | ML reference only |
| History / alert API | Not yet specified/implemented | UI uses offline reports and session memory; **no fabricated endpoints** |

Confirm the real deployment API schema and endpoint availability with the backend owner before merging. The network detail API only returns **community summaries**, not graph edges. Our graph uses separately exported actual edges and is clearly labelled as such.

## Project layout

```text
TraceGuard-Aesthetic-Frontend/
├── public/favicon.svg
├── src/
│   ├── components/{Navigation,Shared}.jsx
│   ├── context/WorkspaceContext.jsx
│   ├── data/{demoTransactions,networks,observedEdges}.json
│   ├── pages/{Dashboard,RiskCheck,TransactionHistory,Alerts,Networks}.jsx
│   ├── services/api.js
│   ├── utils/data.js
│   ├── App.jsx
│   ├── main.jsx
│   └── index.css
├── .env.example
├── .gitignore
├── index.html
├── vite.config.js
└── package.json
```

## Handover notes

The demo uses the team’s *synthetic AMLSim data*. The transaction labels in the dataset are proxies defined by the ML teammate rather than true individual-transaction ground truth. Model results should not be represented as validated bank performance. Scores are not automated authorization decisions. Please deploy a stateful scorer carefully; don't call `/record` on transactions merely checked or held.
