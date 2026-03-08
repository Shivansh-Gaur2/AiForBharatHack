"""Train XGBoost risk-scoring model on synthetic data.

Usage:
    python ml-pipeline/models/risk_scoring/local_train.py

Outputs saved to ml-pipeline/saved_models/:
    risk_model.joblib          — trained XGBClassifier
    risk_features.joblib       — ordered feature name list
    risk_label_names.joblib    — class name list (index = class int)
    risk_explainer.joblib      — SHAP TreeExplainer
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── path setup so we can run this file directly ──────────────────────────────
ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT))
# ─────────────────────────────────────────────────────────────────────────────

import joblib
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import label_binarize

DATA_DIR        = ROOT / "ml-pipeline" / "data"  / "synthetic"
SAVED_MODELS    = ROOT / "ml-pipeline" / "saved_models"
SAVED_MODELS.mkdir(parents=True, exist_ok=True)

FEATURES = [
    "income_volatility_cv",
    "annual_income",
    "months_below_average",
    "debt_to_income_ratio",
    "total_outstanding",
    "active_loan_count",
    "credit_utilisation",
    "on_time_repayment_ratio",
    "has_defaults",
    "seasonal_variance",
    "crop_diversification_index",
    "weather_risk_score",
    "market_risk_score",
    "dependents",
    "age",
    "has_irrigation",
    "land_holding_acres",
    "soil_quality_score",
]

LABEL_NAMES = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]


def train() -> None:
    data_path = DATA_DIR / "risk_training_data.csv"
    if not data_path.exists():
        print(f"Training data not found at {data_path}")
        print("Run: python ml-pipeline/data/synthetic/generate_synthetic_data.py")
        sys.exit(1)

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df):,} training samples. Class distribution:")
    print(df["risk_category"].value_counts().sort_index().to_dict())

    X = df[FEATURES].values.astype(np.float32)
    y = df["risk_category"].values.astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42,
    )

    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.80,
        colsample_bytree=0.80,
        objective="multi:softprob",
        num_class=4,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # ── Evaluation ────────────────────────────────────────────────────────────
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)

    print("\n── Classification Report ─────────────────────────────────")
    print(classification_report(y_test, y_pred, target_names=LABEL_NAMES))

    # Multi-class AUC (one-vs-rest)
    y_bin = label_binarize(y_test, classes=[0, 1, 2, 3])
    auc   = roc_auc_score(y_bin, y_proba, average="macro", multi_class="ovr")
    print(f"Macro AUC (OvR): {auc:.4f}")

    # ── Feature importance ────────────────────────────────────────────────────
    importances = model.feature_importances_
    fi = sorted(zip(FEATURES, importances), key=lambda x: x[1], reverse=True)
    print("\n── Top-10 Feature Importances ────────────────────────────")
    for feat, imp in fi[:10]:
        print(f"  {feat:<35} {imp:.4f}")

    # ── SHAP explainer ────────────────────────────────────────────────────────
    print("\nFitting SHAP TreeExplainer…")
    explainer = shap.TreeExplainer(model)

    # ── Save artefacts ────────────────────────────────────────────────────────
    joblib.dump(model,       SAVED_MODELS / "risk_model.joblib")
    joblib.dump(FEATURES,    SAVED_MODELS / "risk_features.joblib")
    joblib.dump(LABEL_NAMES, SAVED_MODELS / "risk_label_names.joblib")
    joblib.dump(explainer,   SAVED_MODELS / "risk_explainer.joblib")

    print(f"\nSaved model artefacts to {SAVED_MODELS}/")
    print("  risk_model.joblib")
    print("  risk_features.joblib")
    print("  risk_label_names.joblib")
    print("  risk_explainer.joblib")


if __name__ == "__main__":
    train()
