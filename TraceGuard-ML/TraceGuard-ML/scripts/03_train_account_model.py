"""Step 3a: account-level mule detection (uses the real isFraud labels).
Stratified 60/20/20 split by ACCOUNT. Threshold is chosen on validation, metrics are reported on test."""
import _bootstrap  # noqa: F401
import json
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.inspection import permutation_importance
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split

from traceguard import config as C
from traceguard import data as D
from traceguard import evaluate as E
from traceguard import models as M
from traceguard.features import build_account_features
from traceguard.networks import find_suspicious_networks

name = sys.argv[1] if len(sys.argv) > 1 else C.DATASET_NAME
nodes, tx, _ = D.clean(*D.load_raw(name))
X = build_account_features(nodes, tx)
y = nodes.set_index(C.NODE_ID)[C.NODE_LABEL].reindex(X.index)
print(f"Accounts: {len(X)}  fraud: {int(y.sum())} ({y.mean():.2%})  features: {X.shape[1]}")

Xtr, Xtmp, ytr, ytmp = train_test_split(X, y, test_size=0.4, stratify=y, random_state=C.RANDOM_STATE)
Xva, Xte, yva, yte = train_test_split(Xtmp, ytmp, test_size=0.5, stratify=ytmp, random_state=C.RANDOM_STATE)
print(f"train/val/test = {len(Xtr)}/{len(Xva)}/{len(Xte)}")

results, fitted = {}, {}
for mname, model in {"logistic_regression": M.logistic_baseline(), "hist_gradient_boosting": M.gradient_boosting()}.items():
    model.fit(Xtr, ytr)
    sv, st = model.predict_proba(Xva)[:, 1], model.predict_proba(Xte)[:, 1]
    thr = E.best_f1_threshold(yva, sv)
    results[mname] = {"val": E.report(yva, sv, thr), "test": E.report(yte, st, thr)}
    fitted[mname] = model
    print(E.fmt(mname + " [test]", results[mname]["test"]))

# unsupervised reference: fit WITHOUT labels, flip sign so higher = more anomalous
iso = M.isolation_forest().fit(Xtr)
sv, st = -iso.score_samples(Xva), -iso.score_samples(Xte)
thr = E.best_f1_threshold(yva, sv)
results["isolation_forest_unsupervised"] = {"val": E.report(yva, sv, thr), "test": E.report(yte, st, thr)}
print(E.fmt("isolation_forest [test]", results["isolation_forest_unsupervised"]["test"]))
print(f"{'prevalence baseline':<26} PR-AUC={yte.mean():.3f} (a random scorer)")

best = max(("logistic_regression", "hist_gradient_boosting"), key=lambda k: results[k]["val"]["pr_auc"])
print("\nBest on validation PR-AUC:", best)

# permutation importance (on validation, best model)
pi = permutation_importance(fitted[best], Xva, yva, scoring="average_precision", n_repeats=3, random_state=C.RANDOM_STATE, n_jobs=-1)
imp = pd.Series(pi.importances_mean, index=X.columns).sort_values(ascending=False)
print("Top features (drop in PR-AUC when shuffled):\n", imp.head(8).round(4).to_string())

# refit best model on train+val, final test numbers stay as reported above (threshold fixed from val)
final = clone(fitted[best]).fit(pd.concat([Xtr, Xva]), pd.concat([ytr, yva]))
thr_final = results[best]["test"]["threshold"]

# out-of-fold scores for EVERY account -> network discovery without label leakage
oof = pd.Series(cross_val_predict(clone(fitted[best]), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=C.RANDOM_STATE),
                                  method="predict_proba")[:, 1], index=X.index, name="risk_score")
print("\nOut-of-fold account metrics:", E.fmt("oof", E.report(y, oof, thr_final)))
nets = find_suspicious_networks(tx, oof, thr_final, min_size=3)
members = {a for n in nets for a in n["accounts"]}
purity = float(y.loc[list(members)].mean()) if members else float("nan")
coverage = float(y.loc[list(members)].sum() / y.sum()) if members else 0.0
by_pat = pd.Series([n["pattern_hint"] for n in nets]).value_counts().to_dict()
print(f"Suspicious networks found: {len(nets)} {by_pat} | accounts in networks: {len(members)} | "
      f"fraction truly fraud (purity): {purity:.3f} | share of all fraud accounts covered: {coverage:.3f}")

C.MODELS_DIR.mkdir(exist_ok=True); C.REPORTS_DIR.mkdir(exist_ok=True)
joblib.dump({"model": final, "features": list(X.columns), "threshold": thr_final, "model_name": best, "dataset": name,
             "trained_at": datetime.now(timezone.utc).isoformat(), "sklearn_version": sklearn.__version__},
            C.MODELS_DIR / "account_model.joblib")
oof.rename("risk_score").to_frame().assign(is_fraud_label=y).to_csv(C.REPORTS_DIR / "account_scores_oof.csv", index_label="account_id")
json.dump(nets, open(C.REPORTS_DIR / "suspicious_networks.json", "w"), indent=1)
json.dump({"dataset": name, "results": results, "best": best,
           "top_features": imp.head(15).round(5).to_dict(),
           "networks": {"count": len(nets), "patterns": by_pat, "accounts": len(members), "purity": purity, "fraud_coverage": coverage}},
          open(C.REPORTS_DIR / "account_model_metrics.json", "w"), indent=1)
print("\nSaved models/account_model.joblib, reports/account_model_metrics.json, reports/suspicious_networks.json, reports/account_scores_oof.csv")
