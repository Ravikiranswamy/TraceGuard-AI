"""Smoke test: verify model loading and live scoring with cross-version compatibility on LinuxONE."""
import sys
from pathlib import Path
import joblib
import pandas as pd

def enable_sklearn_compat():
    """Register compatibility aliases so sklearn 1.8.0 artifacts unpickle cleanly on sklearn 1.9.x."""
    try:
        import sklearn._loss
        if "sklearn._loss.loss" not in sys.modules:
            sys.modules["sklearn._loss.loss"] = sklearn._loss
        if "loss" not in sys.modules:
            sys.modules["loss"] = sklearn._loss
        if hasattr(sklearn._loss, "_loss") and "_loss" not in sys.modules:
            sys.modules["_loss"] = sklearn._loss._loss
    except Exception as e:
        print(f"Warning: could not register sklearn compatibility aliases: {e}")

def main():
    enable_sklearn_compat()
    
    # 1. Direct artifact unpickle test
    candidate_paths = [
        Path("TraceGuard-ML/TraceGuard-ML/models/tx_model.joblib"),
        Path("../TraceGuard-ML/TraceGuard-ML/models/tx_model.joblib"),
        Path("models/tx_model.joblib"),
    ]
    model_path = next((p for p in candidate_paths if p.exists()), None)
    if not model_path:
        raise FileNotFoundError(f"Could not find tx_model.joblib in any candidate location: {candidate_paths}")
    
    print(f"[1/3] Loading raw artifact from: {model_path}")
    art = joblib.load(model_path)
    model = art["model"]
    feats = art["features"]
    print(f"      Loaded {type(model).__name__} (serialized with sklearn {art.get('sklearn_version')})")
    
    # 2. Raw inference test
    print("[2/3] Testing raw inference with dummy input...")
    sample = pd.DataFrame([{f: 0.0 for f in feats}])
    probs = model.predict_proba(sample)
    print(f"      Inference output shape: {probs.shape}, proba: {probs[0]}")
    
    # 3. Integration Service test
    print("[3/3] Initializing full TraceGuardService...")
    from app.service import service
    service.initialize()
    from app.schemas import ScoreRequest
    res = service.score(ScoreRequest(
        transaction_id="SMOKE-LINUXONE-1",
        sender_account_id=4634,
        receiver_account_id=18352,
        amount=3.25,
        step=121
    ))
    print(f"      Scored TX: {res.transaction_id}")
    print(f"      Risk Score: {res.risk_score} | Level: {res.risk_level} | Action: {res.recommended_action}")
    print(f"      Latency: {res.latency_ms} ms | Reasons: {[r.code for r in res.reasons]}")
    
    print("\n>>> ALL SMOKE TESTS PASSED CLEANLY ON THIS HOST! <<<")

if __name__ == "__main__":
    main()
