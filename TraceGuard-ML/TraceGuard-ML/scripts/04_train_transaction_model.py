"""Step 3b: transaction-level pre-authorization model.

* features use only history strictly BEFORE each transaction (see traceguard/features.py)
* TEMPORAL split: train time<=100, validation 101-120, test >120 (never a random split on time-series data)
* label = proxy label (both endpoints fraud accounts) - AMLSim has no per-transaction label
* ablations show how much of the score comes from amount alone (a known simulator artifact)
"""
import _bootstrap  # noqa: F401
import json
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.inspection import permutation_importance

from traceguard import config as C
from traceguard import data as D
from traceguard import evaluate as E
from traceguard import models as M
from traceguard.features import TX_FEATURES, build_tx_features

name = sys.argv[1] if len(sys.argv) > 1 else C.DATASET_NAME
nodes, tx, _ = D.clean(*D.load_raw(name))
tx = D.add_tx_label(tx, nodes)
F = build_tx_features(tx, nodes)
tx = tx.reset_index(drop=True)
y = tx["tx_label"]
masks = {"train": tx[C.TIME] <= C.TX_TRAIN_END,
         "val": (tx[C.TIME] > C.TX_TRAIN_END) & (tx[C.TIME] <= C.TX_VAL_END),
         "test": tx[C.TIME] > C.TX_VAL_END}
for k, m in masks.items():
    print(f"{k:<5} rows={int(m.sum()):>6}  positives={int(y[m].sum()):>5} ({y[m].mean():.2%})")

AMOUNT_FEATS = ["amount", "log_amount", "amt_to_sender_balance", "amt_vs_sender_avg_out", "amt_vs_receiver_avg_in"]
HISTORY_FEATS = [f for f in TX_FEATURES if f not in AMOUNT_FEATS]
experiments = {
    "logistic_regression (all)": (M.logistic_baseline(), TX_FEATURES),
    "hist_gradient_boosting (all)": (M.gradient_boosting(), TX_FEATURES),
    "ablation: amount features only": (M.gradient_boosting(), AMOUNT_FEATS),
    "ablation: history features only": (M.gradient_boosting(), HISTORY_FEATS),
}
results, fitted = {}, {}
for ename, (model, feats) in experiments.items():
    model.fit(F.loc[masks["train"], feats], y[masks["train"]])
    sv = model.predict_proba(F.loc[masks["val"], feats])[:, 1]
    st = model.predict_proba(F.loc[masks["test"], feats])[:, 1]
    thr = E.best_f1_threshold(y[masks["val"]], sv)
    results[ename] = {"val": E.report(y[masks["val"]], sv, thr), "test": E.report(y[masks["test"]], st, thr)}
    fitted[ename] = (model, feats)
    print(E.fmt(ename + " [test]", results[ename]["test"]))

iso = M.isolation_forest().fit(F.loc[masks["train"], TX_FEATURES])
sv, st = -iso.score_samples(F.loc[masks["val"], TX_FEATURES]), -iso.score_samples(F.loc[masks["test"], TX_FEATURES])
thr = E.best_f1_threshold(y[masks["val"]], sv)
results["isolation_forest (unsupervised)"] = {"val": E.report(y[masks["val"]], sv, thr), "test": E.report(y[masks["test"]], st, thr)}
print(E.fmt("isolation_forest [test]", results["isolation_forest (unsupervised)"]["test"]))
print(f"{'prevalence baseline':<26} PR-AUC={y[masks['test']].mean():.3f} (a random scorer)")

# ---- production candidate: gradient boosting on all features
prod_name = "hist_gradient_boosting (all)"
model, feats = fitted[prod_name]
sv = model.predict_proba(F.loc[masks["val"], feats])[:, 1]
yv = y[masks["val"]]
thr_high = E.best_f1_threshold(yv, sv)                      # F1-optimal  -> HIGH risk
thr_med = E.threshold_for_precision(yv, sv, 0.50)           # precision>=50% -> MEDIUM (manual review queue)
st = model.predict_proba(F.loc[masks["test"], feats])[:, 1]
yt = y[masks["test"]]
tiers = {
    "HIGH (score >= thr_high)": E.report(yt, st, thr_high),
    "MEDIUM+ (score >= thr_medium)": E.report(yt, st, thr_med),
}
print(f"\nTier thresholds from validation: HIGH={thr_high:.3f}  MEDIUM={thr_med:.3f}")
for k, r in tiers.items():
    print(E.fmt(k, r), f"| flagged {r['alert_rate']:.1%} of tx")

pi = permutation_importance(model, F.loc[masks["val"], feats], yv, scoring="average_precision", n_repeats=3, random_state=C.RANDOM_STATE, n_jobs=-1)
imp = pd.Series(pi.importances_mean, index=feats).sort_values(ascending=False)
print("\nTop features (drop in PR-AUC when shuffled):\n", imp.head(10).round(4).to_string())

# heuristics for human-readable reason codes (thresholds learned from TRAIN only)
tr = F[masks["train"]]
reason_thresholds = {
    "r_in_uniq_p95": float(tr["r_in_uniq"].quantile(0.95)),
    "amt_vs_sender_avg_out_min": 2.0,
    "low_amount_p05_of_normal": float(tx.loc[masks["train"] & (y == 0), C.AMT].quantile(0.001)),
}

# refit on train+val for the shipped model (thresholds above stay fixed)
tv = masks["train"] | masks["val"]
final = clone(model).fit(F.loc[tv, feats], y[tv])
C.MODELS_DIR.mkdir(exist_ok=True); C.REPORTS_DIR.mkdir(exist_ok=True)
joblib.dump({"model": final, "features": feats, "thr_high": thr_high, "thr_medium": thr_med,
             "reason_thresholds": reason_thresholds, "model_name": prod_name, "dataset": name,
             "label_definition": "tx_label = sender AND receiver are fraud accounts (proxy)",
             "trained_at": datetime.now(timezone.utc).isoformat(), "sklearn_version": sklearn.__version__, "version": "0.1.0"},
            C.MODELS_DIR / "tx_model.joblib")
json.dump({"dataset": name, "label": "proxy: both endpoints fraud", "split": {"train_end": C.TX_TRAIN_END, "val_end": C.TX_VAL_END},
           "results": results, "production_tiers_test": tiers, "thresholds": {"high": thr_high, "medium": thr_med},
           "top_features": imp.head(15).round(5).to_dict()}, open(C.REPORTS_DIR / "tx_model_metrics.json", "w"), indent=1)

# scored test set for Friend 2 / debugging
out = tx.loc[masks["test"], ["tx_id", C.SRC, C.DST, C.AMT, C.TIME, "tx_label"]].copy()
out["risk_score"] = st
out.to_csv(C.REPORTS_DIR / "tx_test_scored.csv", index=False)

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve
fig, ax = plt.subplots(figsize=(6, 4.5))
for en in ["hist_gradient_boosting (all)", "logistic_regression (all)", "ablation: amount features only", "ablation: history features only"]:
    m, fs = fitted[en]
    p, r, _ = precision_recall_curve(yt, m.predict_proba(F.loc[masks["test"], fs])[:, 1])
    ax.plot(r, p, label=en)
ax.axhline(yt.mean(), ls=":", c="grey", label="random"); ax.set(xlabel="recall", ylabel="precision", title="Transaction model - precision/recall (test)")
ax.legend(fontsize=7); plt.tight_layout(); plt.savefig(C.REPORTS_DIR / "tx_pr_curve.png", dpi=120)
print("\nSaved models/tx_model.joblib, reports/tx_model_metrics.json, reports/tx_test_scored.csv, reports/tx_pr_curve.png")
