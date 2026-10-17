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


# Also mount identical endpoints under /api for full frontend compatibility
@app.get("/api/health", response_model=HealthResponse, tags=["System"], include_in_schema=False)
def api_health():
    return service.get_health()

@app.post("/api/score", response_model=ScoreResponse, tags=["Scoring"], include_in_schema=False)
def api_score(req: ScoreRequest):
    return service.score(req)

@app.post("/api/score/batch", response_model=BatchScoreResponse, tags=["Scoring"], include_in_schema=False)
def api_score_batch(req: BatchScoreRequest):
    return service.score_batch(req)

@app.post("/api/record", status_code=status.HTTP_204_NO_CONTENT, tags=["History"], include_in_schema=False)
def api_record(req: ScoreRequest):
    service.record(req)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.get("/api/networks", response_model=list[NetworkSummary], tags=["Networks"], include_in_schema=False)
def api_get_networks(limit: int = Query(20, ge=1, le=1000)):
    return service.get_networks(limit=limit)

@app.get("/api/networks/{network_id}", response_model=NetworkSummary, tags=["Networks"], include_in_schema=False)
def api_get_network(network_id: str):
    net = service.get_network_by_id(network_id)
    if not net:
        raise HTTPException(status_code=404, detail=f"Network '{network_id}' not found.")
    return net

@app.get("/api/networks/ego/{account_id}", response_model=EgoNetworkResponse, tags=["Networks"], include_in_schema=False)
def api_get_ego_network(account_id: int, hops: int = Query(2, ge=1, le=4), max_nodes: int = Query(60, ge=5, le=200)):
    ego = service.get_ego_network(account_id=account_id, hops=hops, max_nodes=max_nodes)
    if not ego:
        raise HTTPException(status_code=404, detail=f"Ego-network unavailable for account {account_id}.")
    return ego


# ---- Static Frontend Serving (Single-Port Self-Contained Deployment) ---------
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).parent.parent / "static"
if not STATIC_DIR.exists():
    STATIC_DIR = Path(__file__).parent.parent.parent / "TraceGuard-Frontend" / "dist"

if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    logger.info("Serving frontend static assets from %s", STATIC_DIR)
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str = ""):
        target = STATIC_DIR / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(STATIC_DIR / "index.html")

