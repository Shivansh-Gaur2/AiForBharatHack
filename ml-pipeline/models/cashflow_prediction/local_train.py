"""Prophet cash-flow model – local training wrapper.

Usage:
    python -m ml_pipeline.models.cashflow_prediction.local_train \
        --data-dir ml-pipeline/data/output
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from models.cashflow_prediction.train_prophet import (
    DEFAULT_HYPERPARAMS,
    prepare_cluster_data,
    train_all_clusters,
    evaluate_backtest,
    save_models,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Prophet training")
    parser.add_argument("--data-dir", default="ml-pipeline/data/output")
    parser.add_argument("--model-dir", default="ml-pipeline/models/cashflow_prediction/artefacts")
    parser.add_argument("--n-clusters", type=int, default=10)
    args = parser.parse_args()

    data_path = pathlib.Path(args.data_dir)
    cashflow_path = data_path / "cashflows"
    profile_path = data_path / "profiles"

    # Generate if not present
    if not cashflow_path.exists() or not any(cashflow_path.iterdir()):
        logger.info("No cashflow data found – generating synthetic data …")
        from data.synthetic.generate_synthetic_data import (
            generate_farmer_profiles,
            generate_cashflow_time_series,
        )

        cashflow_path.mkdir(parents=True, exist_ok=True)
        profile_path.mkdir(parents=True, exist_ok=True)

        profiles = generate_farmer_profiles(n=2_000)
        profiles.to_csv(profile_path / "profiles.csv", index=False)

        cashflows = generate_cashflow_time_series(profiles, months=36)
        cashflows.to_csv(cashflow_path / "cashflows.csv", index=False)
        logger.info("Generated %d cashflow rows", len(cashflows))
    else:
        csvs = list(cashflow_path.glob("*.csv"))
        cashflows = pd.concat([pd.read_csv(f) for f in csvs], ignore_index=True)
        profile_csvs = list(profile_path.glob("*.csv"))
        profiles = pd.concat([pd.read_csv(f) for f in profile_csvs], ignore_index=True) if profile_csvs else pd.DataFrame()

    logger.info("Cashflow rows: %d, Profiles: %d", len(cashflows), len(profiles))

    params = DEFAULT_HYPERPARAMS.copy()
    params["n_clusters"] = args.n_clusters

    cluster_data = prepare_cluster_data(cashflows, profiles, params["n_clusters"])
    models = train_all_clusters(cluster_data, params)

    metrics = {}
    for cid, model in models.items():
        if cid in cluster_data:
            metrics[cid] = evaluate_backtest(model, cluster_data[cid])

    save_models(models, args.model_dir, params, metrics)
    logger.info("Local training complete – artefacts at %s", args.model_dir)


if __name__ == "__main__":
    main()
