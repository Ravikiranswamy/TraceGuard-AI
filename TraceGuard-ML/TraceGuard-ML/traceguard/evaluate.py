"""Evaluation helpers. Headline metric is PR-AUC (average precision) because fraud is rare;
accuracy is deliberately NOT reported as a headline number."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (average_precision_score, confusion_matrix, f1_score, precision_recall_curve,
                             precision_score, recall_score, roc_auc_score)


def best_f1_threshold(y_true, score) -> float:
    p, r, thr = precision_recall_curve(y_true, score)
    f1 = 2 * p[:-1] * r[:-1] / np.clip(p[:-1] + r[:-1], 1e-12, None)
    return float(thr[int(np.nanargmax(f1))])


def threshold_for_recall(y_true, score, target_recall: float = 0.90) -> float:
    """Highest threshold that still reaches `target_recall` (used as the 'review' tier)."""
    p, r, thr = precision_recall_curve(y_true, score)
    ok = np.where(r[:-1] >= target_recall)[0]
    return float(thr[ok[-1]]) if len(ok) else float(thr[0])


def threshold_for_precision(y_true, score, min_precision: float = 0.5) -> float:
    """Lowest threshold whose precision is still >= `min_precision` (widest net that stays useful)."""
    p, r, thr = precision_recall_curve(y_true, score)
    ok = np.where(p[:-1] >= min_precision)[0]
    return float(thr[ok[0]]) if len(ok) else float(thr[-1])


def precision_at_k(y_true, score, k: int) -> float:
    idx = np.argsort(-np.asarray(score))[:k]
    return float(np.asarray(y_true)[idx].mean())


def report(y_true, score, threshold: float) -> dict:
    y_true = np.asarray(y_true); score = np.asarray(score)
    pred = (score >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    k = max(1, int(round(y_true.mean() * len(y_true))))        # k = number of true positives
    return {
        "n": int(len(y_true)), "positives": int(y_true.sum()), "prevalence": float(y_true.mean()),
        "threshold": float(threshold),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, score)),
        "roc_auc": float(roc_auc_score(y_true, score)),
        "precision_at_k_true_count": precision_at_k(y_true, score, k),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "alert_rate": float(pred.mean()),
    }


def fmt(name: str, r: dict) -> str:
    c = r["confusion"]
    return (f"{name:<26} PR-AUC={r['pr_auc']:.3f} ROC-AUC={r['roc_auc']:.3f} | thr={r['threshold']:.3f} "
            f"P={r['precision']:.3f} R={r['recall']:.3f} F1={r['f1']:.3f} | TP={c['tp']} FP={c['fp']} FN={c['fn']} TN={c['tn']}")
