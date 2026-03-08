"""XGBoost risk model – local training wrapper.

Runs the full pipeline locally (no SageMaker) for development and testing.
Usage:
    python -m ml_pipeline.models.risk_scoring.local_train \
        --data-dir ml-pipeline/data/output/profiles \
        --model-dir ml-pipeline/models/risk_scoring/artefacts
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys

import pandas as pd

# Ensure project root is on the path for local runs
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from data.feature_engineering.risk_features import (
    RISK_FEATURE_NAMES,
    RISK_TARGET_CLASSIFICATION,
    RISK_TARGET_REGRESSION,
    CATEGORY_ENCODING,
    extract_risk_features_batch,
    add_interaction_features,
)
from models.risk_scoring.train_risk_xgboost import (
    train_classifier,
    train_regressor,
    compute_shap_values,
    save_model,
    DEFAULT_HYPERPARAMS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local risk model training")
    parser.add_argument(
        "--data-dir",
        default="ml-pipeline/data/output/profiles",
        help="Directory containing profile CSV / Parquet files",
    )
    parser.add_argument(
        "--model-dir",
        default="ml-pipeline/models/risk_scoring/artefacts",
        help="Output directory for model artefacts",
    )
    parser.add_argument("--with-interactions", action="store_true", default=False)
    args = parser.parse_args()

    data_path = pathlib.Path(args.data_dir)
    if not data_path.exists():
        logger.info("No local data found – generating synthetic data …")
        from data.synthetic.generate_synthetic_data import (
            generate_farmer_profiles,
        )

        data_path.mkdir(parents=True, exist_ok=True)
        df = generate_farmer_profiles(n=10_000)
        df.to_csv(data_path / "profiles.csv", index=False)
        logger.info("Generated %d synthetic profiles", len(df))
    else:
        csvs = list(data_path.glob("*.csv"))
        parquets = list(data_path.glob("*.parquet"))
        if parquets:
            df = pd.concat([pd.read_parquet(p) for p in parquets], ignore_index=True)
        elif csvs:
            df = pd.concat([pd.read_csv(p) for p in csvs], ignore_index=True)
        else:
            raise FileNotFoundError(f"No data in {data_path}")

    logger.info("Loaded %d rows", len(df))

    # Feature extraction
    features = extract_risk_features_batch(df)
    if args.with_interactions:
        features = add_interaction_features(features)

    score_labels = df[RISK_TARGET_REGRESSION].clip(0, 1000)
    cat_labels = df[RISK_TARGET_CLASSIFICATION].map(CATEGORY_ENCODING).astype(int)

    params = DEFAULT_HYPERPARAMS.copy()

    # Train
    classifier = train_classifier(features, cat_labels, params)
    regressor = train_regressor(features, score_labels, params)

    # Explainability
    out_dir = pathlib.Path(args.model_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    compute_shap_values(classifier, features.sample(min(200, len(features))), str(out_dir))

    # Save
    save_model(classifier, regressor, args.model_dir, params)
    logger.info("Local training complete – artefacts at %s", args.model_dir)


if __name__ == "__main__":
    main()
