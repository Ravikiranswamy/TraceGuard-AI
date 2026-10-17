"""
TraceGuard AI — Integrated Backend API

FastAPI application integrating the trained TraceGuard-ML model, feature-store
lifecycle, network community graph, and pre-authorization scoring endpoints.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config as C
from .schemas import (
    BatchScoreRequest,
    BatchScoreResponse,
    EgoNetworkResponse,
    HealthResponse,
    NetworkSummary,
    ScoreRequest,
    ScoreResponse,
)
from .service import service

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("traceguard.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle hook: initialize model artifacts, network graphs, and history store."""
    logger.info("Starting up %s API...", C.SERVICE_NAME)
    service.initialize()
    logger.info("TraceGuard AI engine ready for inference.")
    yield
    logger.info("Shutting down %s API.", C.SERVICE_NAME)


app = FastAPI(
    title=C.SERVICE_NAME,
    description="Pre-authorization financial transaction risk scoring and money-mule network detection.",
    version=C.SERVICE_VERSION,
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=C.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Exception handlers -----------------------------------------------------


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"] if p != "body") or "request"
        message = err["msg"].removeprefix("Value error, ")
        details.append({"field": field, "message": message, "type": err["type"]})
    return JSONResponse(
        status_code=422,
        content={"error": {"type": "validation_error", "message": "Invalid request data.", "details": details}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"type": "http_error", "message": str(exc.detail), "details": []}},
    )


# ---- API Endpoints ----------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    """Health check endpoint: reports system status, model version, and history count."""
    return service.get_health()


@app.post("/score", response_model=ScoreResponse, tags=["Scoring"])
def score(req: ScoreRequest):
    """
    Score ONE transaction before authorization.

    Evaluates against prior history strictly WITHOUT adding this transaction to history.
    """
    return service.score(req)


@app.post("/score/batch", response_model=BatchScoreResponse, tags=["Scoring"])
def score_batch(req: BatchScoreRequest):
    """
    Score a batch of transactions (up to 1,000) before authorization.
    """
    return service.score_batch(req)


@app.post("/record", status_code=status.HTTP_204_NO_CONTENT, tags=["History"])
def record(req: ScoreRequest):
    """
    Record a processed/settled transaction into history.

    Must be called AFTER authorization so the transaction becomes part of
    the historical context for future scoring calls.
    """
    service.record(req)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/networks", response_model=list[NetworkSummary], tags=["Networks"])
def get_networks(limit: int = Query(20, ge=1, le=1000, description="Max networks to return")):
    """
    List precomputed suspicious money-mule communities/networks.
    """
    return service.get_networks(limit=limit)


@app.get("/networks/{network_id}", response_model=NetworkSummary, tags=["Networks"])
def get_network(network_id: str):
    """
    Get full details of a specific money-mule network by ID (e.g. NET-0001).
    """
    net = service.get_network_by_id(network_id)
    if not net:
        raise HTTPException(status_code=404, detail=f"Network '{network_id}' not found.")
    return net


@app.get("/networks/ego/{account_id}", response_model=EgoNetworkResponse, tags=["Networks"])
@app.get("/accounts/{account_id}/ego", response_model=EgoNetworkResponse, tags=["Networks"])
def get_ego_network(
    account_id: int,
    hops: int = Query(2, ge=1, le=4, description="Number of hops for neighbor reach"),
    max_nodes: int = Query(60, ge=5, le=200, description="Max nodes to display in graph"),
):
    """
    Get the ego-network graph around an account for interactive graph visualization.
    """
    ego = service.get_ego_network(account_id=account_id, hops=hops, max_nodes=max_nodes)
    if not ego:
        raise HTTPException(
            status_code=404, detail=f"Ego-network unavailable for account {account_id} or history not loaded."
        )
    return ego
