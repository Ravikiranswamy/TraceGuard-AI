"""Minimal FastAPI wrapper around the ML component (reference for Friend 2).

Run from the project root:
    python -m pip install fastapi uvicorn
    python -m uvicorn api_example.main:app --reload
Docs UI: http://127.0.0.1:8000/docs
"""
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from traceguard import config as C
from traceguard.inference import TraceGuardScorer
from traceguard.schemas import BatchScoreRequest, BatchScoreResponse, NetworkSummary, ScoreRequest, ScoreResponse

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DEMO: history = AMLSim transactions up to the end of the validation period.
    # In the real system, build the history from the backend's transaction database instead.
    state["scorer"] = TraceGuardScorer.from_dataset(up_to_step=C.TX_VAL_END)
    nets = C.REPORTS_DIR / "suspicious_networks.json"
    state["networks"] = json.loads(nets.read_text()) if nets.exists() else []
    yield


app = FastAPI(title="TraceGuard AI - ML service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "model_version": state["scorer"].version}


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest):
    return state["scorer"].score(req)


@app.post("/score/batch", response_model=BatchScoreResponse)
def score_batch(req: BatchScoreRequest):
    return BatchScoreResponse(results=state["scorer"].score_batch(req.transactions))


@app.post("/record", status_code=204)
def record(req: ScoreRequest):
    """Call after a transaction was processed so it becomes history for later scoring."""
    state["scorer"].record(req)


@app.get("/networks", response_model=list[NetworkSummary])
def networks(limit: int = 20):
    return state["networks"][:limit]


@app.get("/networks/{network_id}", response_model=NetworkSummary)
def network(network_id: str):
    for n in state["networks"]:
        if n["network_id"] == network_id:
            return n
    raise HTTPException(404, "network not found")
