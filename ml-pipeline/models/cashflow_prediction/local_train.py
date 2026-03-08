"""Train population-level seasonal cash-flow model on synthetic data.

The model captures the *shape* of the Indian agricultural income/expense
cycle (Kharif/Rabi/Zaid pattern) from a population of synthetic profiles.

At inference time the per-profile average is used to scale the seasonal
multipliers to each borrower's own income level.

Usage:
    python ml-pipeline/models/cashflow_prediction/local_train.py

Outputs saved to ml-pipeline/saved_models/:
    cashflow_inflow_model.joblib    — Ridge pipeline (seasonal → INR inflow)
    cashflow_outflow_model.joblib   — Ridge pipeline (seasonal → INR outflow)
    cashflow_features.joblib        — ordered feature list
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DATA_DIR     = ROOT / "ml-pipeline" / "data"  / "synthetic"
SAVED_MODELS = ROOT / "ml-pipeline" / "saved_models"
SAVED_MODELS.mkdir(parents=True, exist_ok=True)

FEATURES = [
    "month_sin",
    "month_cos",
    "is_kharif",
    "is_rabi",
    "is_zaid",
    "has_irrigation",
]


def train() -> None:
    data_path = DATA_DIR / "cashflow_training_data.csv"
    if not data_path.exists():
        print(f"Training data not found at {data_path}")
        print("Run: python ml-pipeline/data/synthetic/generate_synthetic_data.py")
        sys.exit(1)

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df):,} monthly cashflow records from {df['profile_id'].nunique()} profiles.")

    X        = df[FEATURES].values.astype(np.float32)
    y_inflow  = df["inflow"].values
    y_outflow = df["outflow"].values

    # ── Split by profile_id to avoid leakage ──────────────────────────────────
    all_pids          = df["profile_id"].unique()
    train_pids, test_pids = train_test_split(all_pids, test_size=0.20, random_state=42)
    train_mask = df["profile_id"].isin(train_pids)

    X_train, X_test   = X[train_mask], X[~train_mask]
    yi_train, yi_test = y_inflow[train_mask],  y_inflow[~train_mask]
    yo_train, yo_test = y_outflow[train_mask], y_outflow[~train_mask]

    # ── Train inflow model ─────────────────────────────────────────────────────
    model_inflow = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge",  Ridge(alpha=1.0)),
    ])
    model_inflow.fit(X_train, yi_train)

    mape_in = mean_absolute_percentage_error(yi_test, model_inflow.predict(X_test))
    print(f"Inflow  MAPE: {mape_in:.2%}")

    # ── Train outflow model ────────────────────────────────────────────────────
    model_outflow = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge",  Ridge(alpha=1.0)),
    ])
    model_outflow.fit(X_train, yo_train)

    mape_out = mean_absolute_percentage_error(yo_test, model_outflow.predict(X_test))
    print(f"Outflow MAPE: {mape_out:.2%}")

    # ── Save ───────────────────────────────────────────────────────────────────
    joblib.dump(model_inflow,  SAVED_MODELS / "cashflow_inflow_model.joblib")
    joblib.dump(model_outflow, SAVED_MODELS / "cashflow_outflow_model.joblib")
    joblib.dump(FEATURES,      SAVED_MODELS / "cashflow_features.joblib")

    print(f"\nSaved cashflow model artefacts to {SAVED_MODELS}/")
    print("  cashflow_inflow_model.joblib")
    print("  cashflow_outflow_model.joblib")
    print("  cashflow_features.joblib")


if __name__ == "__main__":
    train()
