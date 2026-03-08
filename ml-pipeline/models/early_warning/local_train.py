"""Early warning model – local training wrapper.

Usage:
    python -m ml_pipeline.models.early_warning.local_train
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local early-warning model training")
    parser.add_argument("--data-dir", default="ml-pipeline/data/output/events")
    parser.add_argument("--model-dir", default="ml-pipeline/models/early_warning/artefacts")
    args = parser.parse_args()

    data_path = pathlib.Path(args.data_dir)

    if not data_path.exists() or not any(data_path.glob("*")):
        logger.info("No event data found – generating synthetic data …")
        from data.synthetic.generate_synthetic_data import (
            generate_farmer_profiles,
            generate_cashflow_time_series,
            generate_early_warning_events,
        )

        data_path.mkdir(parents=True, exist_ok=True)
        profiles = generate_farmer_profiles(n=5_000)
        cashflows = generate_cashflow_time_series(profiles, months=24)
        events = generate_early_warning_events(profiles, cashflows)
        events.to_csv(data_path / "events.csv", index=False)
        logger.info("Generated %d events", len(events))

    from data.feature_engineering.early_warning_features import (
        extract_early_warning_features_batch,
        extract_severity_labels,
    )
    from models.early_warning.train_isolation_forest import (
        train_isolation_forest,
        compute_anomaly_scores,
        evaluate_if,
        save_model as save_if_model,
        DEFAULT_HYPERPARAMS as IF_PARAMS,
    )
    from models.early_warning.train_lightgbm_classifier import (
        train_lightgbm_classifier,
        cross_validate,
        save_model as save_lgb_model,
        DEFAULT_HYPERPARAMS as LGB_PARAMS,
    )

    # Load data
    csvs = list(data_path.glob("*.csv"))
    df = pd.concat([pd.read_csv(f) for f in csvs], ignore_index=True)
    features = extract_early_warning_features_batch(df)
    labels = extract_severity_labels(df) if "severity" in df.columns else None

    # Phase A: Isolation Forest
    logger.info("Phase A: Training Isolation Forest …")
    if_model, scaler = train_isolation_forest(features, IF_PARAMS)
    if_metrics = evaluate_if(if_model, scaler, features, labels)
    logger.info("IF metrics: %s", if_metrics)

    if_dir = pathlib.Path(args.model_dir) / "isolation_forest"
    save_if_model(if_model, scaler, str(if_dir), IF_PARAMS, if_metrics)

    # Phase B: LightGBM with anomaly scores
    anomaly_scores = compute_anomaly_scores(if_model, scaler, features)
    features_with_scores = features.copy()
    features_with_scores["anomaly_score"] = anomaly_scores

    if labels is not None:
        logger.info("Phase B: Training LightGBM severity classifier …")
        cv_metrics = cross_validate(features_with_scores, labels, LGB_PARAMS, n_folds=3)
        logger.info("CV: %s", cv_metrics)

        lgb_model = train_lightgbm_classifier(features_with_scores, labels, LGB_PARAMS)
        lgb_dir = pathlib.Path(args.model_dir) / "lightgbm"
        save_lgb_model(lgb_model, str(lgb_dir), LGB_PARAMS, cv_metrics)

    logger.info("Local training complete – artefacts at %s", args.model_dir)


if __name__ == "__main__":
    main()
