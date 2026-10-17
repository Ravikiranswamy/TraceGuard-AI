"""Configuration and portable path resolution for TraceGuard AI."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Base paths
APP_DIR = Path(__file__).resolve().parent
INTEGRATION_ROOT = APP_DIR.parent
WORKSPACE_ROOT = INTEGRATION_ROOT.parent

# Resolve ML root directory portably
ML_CANDIDATE_PATHS = [
    Path(os.environ.get("TG_ML_DIR", "")),
    WORKSPACE_ROOT / "TraceGuard-ML" / "TraceGuard-ML",
    WORKSPACE_ROOT / "TraceGuard-ML",
    INTEGRATION_ROOT.parent / "TraceGuard-ML" / "TraceGuard-ML",
]

ML_DIR: Path | None = None
for candidate in ML_CANDIDATE_PATHS:
    if candidate and candidate.exists() and (candidate / "models" / "tx_model.joblib").exists():
        ML_DIR = candidate.resolve()
        break

if ML_DIR is None:
    # Fallback to standard relative path even if file check pending
    ML_DIR = (WORKSPACE_ROOT / "TraceGuard-ML" / "TraceGuard-ML").resolve()

# Ensure traceguard ML package is accessible on sys.path
if str(ML_DIR) not in sys.path and ML_DIR.exists():
    sys.path.insert(0, str(ML_DIR))

# Artifact paths
MODEL_PATH = Path(
    os.environ.get("TG_MODEL_PATH", str(ML_DIR / "models" / "tx_model.joblib"))
).resolve()

ACCOUNT_MODEL_PATH = Path(
    os.environ.get("TG_ACCOUNT_MODEL_PATH", str(ML_DIR / "models" / "account_model.joblib"))
).resolve()

NETWORKS_PATH = Path(
    os.environ.get("TG_NETWORKS_PATH", str(ML_DIR / "reports" / "suspicious_networks.json"))
).resolve()

DATA_DIR = Path(
    os.environ.get("TG_DATA_DIR", str(ML_DIR / "data" / "raw"))
).resolve()

# Training / validation step thresholds
DEFAULT_UP_TO_STEP = int(os.environ.get("TG_UP_TO_STEP", "120"))
DATASET_NAME = os.environ.get("TG_DATASET_NAME", "20K_fanin200cycle200")

# CORS and Server configuration
ALLOWED_ORIGINS_ENV = os.environ.get("ALLOWED_ORIGINS", "")
if ALLOWED_ORIGINS_ENV:
    ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS_ENV.split(",") if origin.strip()]
else:
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*",  # Permissive for local dev / testing; tighten in production
    ]

SERVICE_NAME = "TraceGuard AI"
SERVICE_VERSION = "0.1.0"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
