"""Service layer: Model loading, HistoryStore management, and scoring engine."""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

import pandas as pd

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

logger = logging.getLogger("traceguard.service")


class TraceGuardService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recorded_tx_ids: set[str] = set()
        self._recorded_count: int = 0
        self.scorer: Optional[Any] = None
        self.networks: list[dict] = []
        self._history_tx: Optional[pd.DataFrame] = None
        self.is_ready: bool = False

    def initialize(self) -> None:
        """Load model artifact, suspicious networks, and initial transaction history."""
        with self._lock:
            if self.is_ready:
                return

            logger.info("Initializing TraceGuard AI Service...")

            # Enable cross-version unpickling compatibility for scikit-learn (e.g. 1.8.x artifacts on 1.9.x)
            import sys
            try:
                import sklearn._loss
                if "sklearn._loss.loss" not in sys.modules:
                    sys.modules["sklearn._loss.loss"] = sklearn._loss
                if "loss" not in sys.modules:
                    sys.modules["loss"] = sklearn._loss
                if hasattr(sklearn._loss, "_loss") and "_loss" not in sys.modules:
                    sys.modules["_loss"] = sklearn._loss._loss
            except Exception as e:
                logger.debug("Sklearn compatibility bridge skipped: %s", e)

            # 1. Import traceguard ML components
            try:
                from traceguard import config as ML_C
                from traceguard import data as D
                from traceguard.inference import TraceGuardScorer
            except ImportError as e:
                logger.error("Failed to import traceguard package from %s: %s", C.ML_DIR, e)
                raise RuntimeError(
                    f"Could not import traceguard. Ensure {C.ML_DIR} contains the traceguard package."
                ) from e

            # 2. Check and load model artifact
            if not C.MODEL_PATH.exists():
                raise FileNotFoundError(
                    f"Model artifact not found at {C.MODEL_PATH}. Check TG_MODEL_PATH configuration."
                )
            logger.info("Found model artifact at %s", C.MODEL_PATH)

            # 3. Load initial history
            raw_tx_path = C.DATA_DIR / C.DATASET_NAME / "transactions.csv"
            raw_nodes_path = C.DATA_DIR / C.DATASET_NAME / "nodes.csv"

            history_df = pd.DataFrame(columns=[ML_C.SRC, ML_C.DST, ML_C.AMT, ML_C.TIME])
            balances: dict[int, float] = {}

            if raw_tx_path.exists() and raw_nodes_path.exists():
                logger.info("Loading initial history up to step %d from %s", C.DEFAULT_UP_TO_STEP, raw_tx_path)
                nodes, tx = D.load_raw(C.DATASET_NAME, base=C.DATA_DIR)
                nodes, tx, _ = D.clean(nodes, tx)
                if C.DEFAULT_UP_TO_STEP is not None:
                    tx = tx[tx[ML_C.TIME] <= C.DEFAULT_UP_TO_STEP]
                history_df = tx
                balances = nodes.set_index(ML_C.NODE_ID)[ML_C.NODE_BAL].to_dict()
                self._history_tx = tx
                logger.info("Loaded %d historical transactions across %d accounts.", len(history_df), len(balances))
            else:
                logger.warning(
                    "Raw AMLSim data not found at %s. Initializing scorer with empty baseline history.",
                    raw_tx_path,
                )

            # 4. Instantiate scorer
            self.scorer = TraceGuardScorer(
                history=history_df,
                balances=balances,
                model_path=C.MODEL_PATH,
            )
            self._recorded_count = len(history_df)

            # 5. Load precomputed suspicious networks
            if C.NETWORKS_PATH.exists():
                logger.info("Loading suspicious networks report from %s", C.NETWORKS_PATH)
                self.networks = json.loads(C.NETWORKS_PATH.read_text(encoding="utf-8"))
                logger.info("Loaded %d precomputed suspicious networks.", len(self.networks))
            else:
                logger.warning("Suspicious networks file not found at %s. Using empty list.", C.NETWORKS_PATH)
                self.networks = []

            self.is_ready = True
            logger.info("TraceGuard AI Service successfully initialized (model version %s).", self.scorer.version)

    def score(self, req: ScoreRequest) -> ScoreResponse:
        """Score a transaction strictly against prior history without modifying history."""
        if not self.is_ready or self.scorer is None:
            raise RuntimeError("Service is not initialized.")

        # Convert to traceguard ML ScoreRequest or dict
        from traceguard.schemas import ScoreRequest as MLScoreRequest

        ml_req = MLScoreRequest(
            transaction_id=req.transaction_id,
            sender_account_id=req.sender_account_id,
            receiver_account_id=req.receiver_account_id,
            amount=req.amount,
            step=req.step,
            sender_balance=req.sender_balance,
        )

        # Scorer.score reads store.features without updating store
        res = self.scorer.score(ml_req)

        return ScoreResponse(
            transaction_id=res.transaction_id,
            risk_score=res.risk_score,
            risk_level=res.risk_level,
            recommended_action=res.recommended_action,
            reasons=[{"code": r.code, "description": r.description} for r in res.reasons],
            sender_known=res.sender_known,
            receiver_known=res.receiver_known,
            model_version=res.model_version,
            latency_ms=res.latency_ms,
        )

    def score_batch(self, req: BatchScoreRequest) -> BatchScoreResponse:
        """Score a batch of transactions without mutating history."""
        results = [self.score(t) for t in req.transactions]
        return BatchScoreResponse(results=results)

    def record(self, req: ScoreRequest) -> bool:
        """Record a settled transaction into history exactly once. Returns True if recorded, False if duplicate."""
        if not self.is_ready or self.scorer is None:
            raise RuntimeError("Service is not initialized.")

        with self._lock:
            # Idempotency check: if transaction_id is present and already recorded, skip
            if req.transaction_id:
                if req.transaction_id in self._recorded_tx_ids:
                    logger.debug("Transaction %s already recorded; skipping duplicate record.", req.transaction_id)
                    return False
                self._recorded_tx_ids.add(req.transaction_id)

            from traceguard.schemas import ScoreRequest as MLScoreRequest

            ml_req = MLScoreRequest(
                transaction_id=req.transaction_id,
                sender_account_id=req.sender_account_id,
                receiver_account_id=req.receiver_account_id,
                amount=req.amount,
                step=req.step,
                sender_balance=req.sender_balance,
            )

            # Record into the in-memory HistoryStore
            self.scorer.record(ml_req)
            self._recorded_count += 1
            return True

    def get_networks(self, limit: int = 20) -> list[NetworkSummary]:
        """Return precomputed suspicious money-mule networks."""
        return [NetworkSummary(**net) for net in self.networks[:limit]]

    def get_network_by_id(self, network_id: str) -> Optional[NetworkSummary]:
        """Return a specific suspicious network by ID."""
        for net in self.networks:
            if net.get("network_id") == network_id:
                return NetworkSummary(**net)
        return None

    def get_ego_network(self, account_id: int, hops: int = 2, max_nodes: int = 60) -> Optional[EgoNetworkResponse]:
        """Generate an ego-network graph around an account for UI visualization."""
        if self._history_tx is None or self._history_tx.empty:
            return None
        try:
            from traceguard.networks import ego_network

            data = ego_network(self._history_tx, account=account_id, hops=hops, max_nodes=max_nodes)
            return EgoNetworkResponse(**data)
        except Exception as e:
            logger.warning("Error computing ego-network for account %d: %s", account_id, e)
            return None

    def get_health(self) -> HealthResponse:
        """Health check details."""
        if not self.is_ready or self.scorer is None:
            return HealthResponse(
                status="initializing",
                service=C.SERVICE_NAME,
                model_version="unknown",
                known_accounts=0,
                transactions_in_history=0,
            )
        known_accs = len(self.scorer.store.out) + len(self.scorer.store.inc)
        return HealthResponse(
            status="ok",
            service=C.SERVICE_NAME,
            model_version=self.scorer.version,
            known_accounts=known_accs,
            transactions_in_history=self._recorded_count,
        )


# Singleton instance
service = TraceGuardService()
