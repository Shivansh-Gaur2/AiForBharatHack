"""Train early-warning models on synthetic data.

Two models:
  1. IsolationForest — unsupervised anomaly detector trained on NORMAL
     profiles only.  Anomaly score → raw stress indicator.
  2. LightGBM multi-class classifier — maps 12 features → severity
     (0=OK, 1=WARNING, 2=CRITICAL).  Uses all labelled data.

Usage:
    python ml-pipeline/models/early_warning/local_train.py

Outputs saved to ml-pipeline/saved_models/:
    ew_isolation_forest.joblib     — IsolationForest
    ew_lgbm_classifier.joblib      — LGBMClassifier
    ew_features.joblib             — feature list
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT))

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

DATA_DIR     = ROOT / "ml-pipeline" / "data"  / "synthetic"
SAVED_MODELS = ROOT / "ml-pipeline" / "saved_models"
SAVED_MODELS.mkdir(parents=True, exist_ok=True)

FEATURES = [
    "income_deviation_3m",
    "income_deviation_6m",
    "missed_payments_ytd",
    "days_overdue_avg",
    "dti_ratio",
    "dti_delta_3m",
    "surplus_trend_slope",
    "weather_shock_score",
    "market_price_shock",
    "seasonal_stress_flag",
    "risk_category_current",
    "days_since_last_alert",
]

SEVERITY_NAMES = ["OK", "WARNING", "CRITICAL"]


def train() -> None:
    data_path = DATA_DIR / "early_warning_training_data.csv"
    if not data_path.exists():
        print(f"Training data not found at {data_path}")
        print("Run: python ml-pipeline/data/synthetic/generate_synthetic_data.py")
        sys.exit(1)

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df):,} samples. Severity distribution:")
    print(df["severity"].value_counts().sort_index().to_dict())

    X = df[FEATURES].values.astype(np.float32)
    y = df["severity"].values.astype(int)

    # ── Stage 1: IsolationForest (unsupervised on normal class) ───────────────
    X_normal = df[df["severity"] == 0][FEATURES].values.astype(np.float32)
    print(f"\nFitting IsolationForest on {len(X_normal):,} normal samples…")

    iso = IsolationForest(
        n_estimators=200,
        contamination=0.20,     # expected fraction of outliers at inference
        random_state=42,
        n_jobs=-1,
    )
    iso.fit(X_normal)

    # Quick validation — anomaly score should be lower for WARNING/CRITICAL
    scores_by_class = {}
    for cls in [0, 1, 2]:
        mask = y == cls
        s    = iso.score_samples(X[mask])
        scores_by_class[SEVERITY_NAMES[cls]] = float(np.mean(s))
    print("Mean anomaly scores (more negative = more anomalous):", scores_by_class)

    joblib.dump(iso, SAVED_MODELS / "ew_isolation_forest.joblib")
    print("Saved ew_isolation_forest.joblib")

    # ── Stage 2: LightGBM severity classifier ─────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42,
    )

    clf = lgb.LGBMClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        num_leaves=31,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    print("\n── LightGBM Classification Report ────────────────────────")
    print(classification_report(y_test, y_pred, target_names=SEVERITY_NAMES))

    # Feature importances
    fi = sorted(zip(FEATURES, clf.feature_importances_), key=lambda x: x[1], reverse=True)
    print("Top feature importances:")
    for feat, imp in fi[:8]:
        print(f"  {feat:<35} {imp:.0f}")

    joblib.dump(clf,      SAVED_MODELS / "ew_lgbm_classifier.joblib")
    joblib.dump(FEATURES, SAVED_MODELS / "ew_features.joblib")
    print("\nSaved ew_lgbm_classifier.joblib  ew_features.joblib")


if __name__ == "__main__":
    train()
