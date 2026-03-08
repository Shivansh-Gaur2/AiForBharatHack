"""SageMaker Feature Store – Feature group definitions and setup.

Creates feature groups for:
  - Risk features (18 dims)
  - Cash flow features (20 dims)
  - Early warning features (22 dims)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import boto3
import sagemaker
from sagemaker.feature_store.feature_definition import (
    FeatureDefinition,
    FeatureTypeEnum,
)
from sagemaker.feature_store.feature_group import FeatureGroup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature group definitions
# ---------------------------------------------------------------------------

RISK_FEATURE_GROUP = {
    "name": "rural-credit-risk-features",
    "record_identifier": "profile_id",
    "event_time": "event_time",
    "features": [
        ("profile_id", FeatureTypeEnum.STRING),
        ("event_time", FeatureTypeEnum.STRING),
        ("income_volatility_cv", FeatureTypeEnum.FRACTIONAL),
        ("annual_income", FeatureTypeEnum.FRACTIONAL),
        ("months_below_average", FeatureTypeEnum.INTEGRAL),
        ("debt_to_income_ratio", FeatureTypeEnum.FRACTIONAL),
        ("total_outstanding", FeatureTypeEnum.FRACTIONAL),
        ("active_loan_count", FeatureTypeEnum.INTEGRAL),
        ("credit_utilisation", FeatureTypeEnum.FRACTIONAL),
        ("on_time_repayment_ratio", FeatureTypeEnum.FRACTIONAL),
        ("has_defaults", FeatureTypeEnum.FRACTIONAL),
        ("seasonal_variance", FeatureTypeEnum.FRACTIONAL),
        ("crop_diversification_index", FeatureTypeEnum.FRACTIONAL),
        ("weather_risk_score", FeatureTypeEnum.FRACTIONAL),
        ("market_risk_score", FeatureTypeEnum.FRACTIONAL),
        ("dependents", FeatureTypeEnum.INTEGRAL),
        ("age", FeatureTypeEnum.INTEGRAL),
        ("has_irrigation", FeatureTypeEnum.FRACTIONAL),
        ("land_holding_acres", FeatureTypeEnum.FRACTIONAL),
        ("soil_quality_score", FeatureTypeEnum.FRACTIONAL),
    ],
}

CASHFLOW_FEATURE_GROUP = {
    "name": "rural-credit-cashflow-features",
    "record_identifier": "profile_id",
    "event_time": "event_time",
    "features": [
        ("profile_id", FeatureTypeEnum.STRING),
        ("event_time", FeatureTypeEnum.STRING),
        ("monthly_income", FeatureTypeEnum.FRACTIONAL),
        ("monthly_expense", FeatureTypeEnum.FRACTIONAL),
        ("net_cashflow", FeatureTypeEnum.FRACTIONAL),
        ("income_lag_1", FeatureTypeEnum.FRACTIONAL),
        ("income_lag_3", FeatureTypeEnum.FRACTIONAL),
        ("income_lag_6", FeatureTypeEnum.FRACTIONAL),
        ("income_lag_12", FeatureTypeEnum.FRACTIONAL),
        ("income_rolling_mean_3", FeatureTypeEnum.FRACTIONAL),
        ("income_rolling_std_3", FeatureTypeEnum.FRACTIONAL),
        ("income_rolling_mean_6", FeatureTypeEnum.FRACTIONAL),
        ("is_kharif", FeatureTypeEnum.INTEGRAL),
        ("is_rabi", FeatureTypeEnum.INTEGRAL),
        ("is_zaid", FeatureTypeEnum.INTEGRAL),
        ("weather_index", FeatureTypeEnum.FRACTIONAL),
        ("msp_deviation", FeatureTypeEnum.FRACTIONAL),
        ("diesel_price_index", FeatureTypeEnum.FRACTIONAL),
        ("cluster_id", FeatureTypeEnum.INTEGRAL),
    ],
}

EARLY_WARNING_FEATURE_GROUP = {
    "name": "rural-credit-early-warning-features",
    "record_identifier": "profile_id",
    "event_time": "event_time",
    "features": [
        ("profile_id", FeatureTypeEnum.STRING),
        ("event_time", FeatureTypeEnum.STRING),
        ("income_deviation_3m", FeatureTypeEnum.FRACTIONAL),
        ("income_deviation_6m", FeatureTypeEnum.FRACTIONAL),
        ("missed_payments_ytd", FeatureTypeEnum.INTEGRAL),
        ("days_overdue_avg", FeatureTypeEnum.FRACTIONAL),
        ("dti_delta_3m", FeatureTypeEnum.FRACTIONAL),
        ("surplus_trend_slope", FeatureTypeEnum.FRACTIONAL),
        ("weather_shock_score", FeatureTypeEnum.FRACTIONAL),
        ("market_price_shock", FeatureTypeEnum.FRACTIONAL),
        ("crop_failure_probability", FeatureTypeEnum.FRACTIONAL),
        ("loan_count_increase", FeatureTypeEnum.INTEGRAL),
        ("credit_utilisation_delta", FeatureTypeEnum.FRACTIONAL),
        ("has_informal_debt", FeatureTypeEnum.FRACTIONAL),
        ("seasonal_stress_flag", FeatureTypeEnum.FRACTIONAL),
        ("risk_category_current", FeatureTypeEnum.INTEGRAL),
        ("repayment_months_remaining", FeatureTypeEnum.INTEGRAL),
        ("income_sources_count", FeatureTypeEnum.INTEGRAL),
        ("land_holding_acres", FeatureTypeEnum.FRACTIONAL),
        ("has_irrigation", FeatureTypeEnum.FRACTIONAL),
        ("household_size", FeatureTypeEnum.INTEGRAL),
        ("district_drought_index", FeatureTypeEnum.FRACTIONAL),
        ("prev_alert_severity", FeatureTypeEnum.INTEGRAL),
        ("days_since_last_alert", FeatureTypeEnum.INTEGRAL),
    ],
}


# ---------------------------------------------------------------------------
# Setup functions
# ---------------------------------------------------------------------------

def create_feature_group(
    definition: dict[str, Any],
    role: str,
    bucket: str,
    session: sagemaker.Session | None = None,
) -> FeatureGroup:
    """Create or update a SageMaker Feature Store feature group."""
    session = session or sagemaker.Session()

    fg = FeatureGroup(name=definition["name"], sagemaker_session=session)

    feature_definitions = [
        FeatureDefinition(feature_name=name, feature_type=ftype)
        for name, ftype in definition["features"]
    ]
    fg.feature_definitions = feature_definitions

    s3_prefix = f"s3://{bucket}/feature-store/{definition['name']}"

    try:
        fg.create(
            s3_uri=s3_prefix,
            record_identifier_name=definition["record_identifier"],
            event_time_feature_name=definition["event_time"],
            role_arn=role,
            enable_online_store=True,
        )
        logger.info("Created feature group: %s", definition["name"])

        # Wait for creation
        _wait_for_feature_group(fg)

    except Exception as e:
        if "ResourceInUse" in str(e):
            logger.info("Feature group '%s' already exists", definition["name"])
        else:
            raise

    return fg


def _wait_for_feature_group(fg: FeatureGroup, timeout: int = 300) -> None:
    """Wait for feature group to become available."""
    start = time.time()
    while time.time() - start < timeout:
        status = fg.describe().get("FeatureGroupStatus")
        if status == "Created":
            return
        if status in ("CreateFailed", "DeleteFailed"):
            raise RuntimeError(f"Feature group failed: {status}")
        time.sleep(5)
    raise TimeoutError(f"Feature group creation timed out after {timeout}s")


def setup_all_feature_groups(
    role: str,
    bucket: str,
    session: sagemaker.Session | None = None,
) -> dict[str, FeatureGroup]:
    """Create all three feature groups."""
    groups = {}
    for defn in [RISK_FEATURE_GROUP, CASHFLOW_FEATURE_GROUP, EARLY_WARNING_FEATURE_GROUP]:
        fg = create_feature_group(defn, role, bucket, session)
        groups[defn["name"]] = fg
    return groups


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    role = sagemaker.get_execution_role()
    bucket = sagemaker.Session().default_bucket()
    setup_all_feature_groups(role, bucket)
    logger.info("All feature groups created ✓")
