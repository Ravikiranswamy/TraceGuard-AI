"""Model factories (scikit-learn only)."""
from __future__ import annotations

from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C


def logistic_baseline():
    """Scaled logistic regression with class weights - the simple, explainable baseline."""
    return make_pipeline(
        SimpleImputer(strategy="median", add_indicator=False),
        StandardScaler(),
        LogisticRegression(max_iter=2000, class_weight="balanced", random_state=C.RANDOM_STATE),
    )


def gradient_boosting():
    """Histogram gradient boosting: handles NaN natively, fast on 100k+ rows."""
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40,
        l2_regularization=1.0, class_weight="balanced", early_stopping=True,
        validation_fraction=0.15, n_iter_no_change=20, random_state=C.RANDOM_STATE,
    )


def isolation_forest():
    """Unsupervised reference (no labels used for fitting) - shows what anomaly detection alone achieves."""
    return make_pipeline(SimpleImputer(strategy="median"), IsolationForest(n_estimators=300, random_state=C.RANDOM_STATE, n_jobs=-1))
