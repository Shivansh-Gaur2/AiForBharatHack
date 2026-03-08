"""Lambda: Trigger model retraining on data drift or schedule.

Invoked by:
  - EventBridge cron (weekly / bi-weekly)
  - S3 event (new training data uploaded)
  - CloudWatch alarm (model drift detected)

Starts the appropriate SageMaker Pipeline execution.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "ap-south-1")
PIPELINES = {
    "risk": os.environ.get("RISK_PIPELINE_NAME", "rural-credit-risk-scoring"),
    "cashflow": os.environ.get("CASHFLOW_PIPELINE_NAME", "rural-credit-cashflow-prediction"),
    "early_warning": os.environ.get("EARLY_WARNING_PIPELINE_NAME", "rural-credit-early-warning"),
}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for triggering SageMaker Pipeline executions.

    Event format:
        {
            "model_type": "risk" | "cashflow" | "early_warning" | "all",
            "trigger_source": "schedule" | "data_upload" | "drift_alert",
            "parameters": {}  # Optional pipeline parameter overrides
        }
    """
    model_type = event.get("model_type", "all")
    trigger_source = event.get("trigger_source", "unknown")
    parameters = event.get("parameters", {})

    logger.info(
        "Retraining triggered – model=%s, source=%s", model_type, trigger_source,
    )

    sm_client = boto3.client("sagemaker", region_name=REGION)
    results: dict[str, Any] = {}

    pipeline_names = (
        list(PIPELINES.values())
        if model_type == "all"
        else [PIPELINES.get(model_type, "")]
    )

    for pipeline_name in pipeline_names:
        if not pipeline_name:
            continue

        try:
            # Convert parameters to SageMaker format
            sm_params = [
                {"Name": k, "Value": str(v)}
                for k, v in parameters.items()
            ]

            response = sm_client.start_pipeline_execution(
                PipelineName=pipeline_name,
                PipelineExecutionDisplayName=f"{trigger_source}-triggered",
                PipelineParameters=sm_params,
                PipelineExecutionDescription=f"Triggered by {trigger_source}",
            )

            execution_arn = response["PipelineExecutionArn"]
            results[pipeline_name] = {
                "status": "started",
                "execution_arn": execution_arn,
            }
            logger.info("Started pipeline: %s → %s", pipeline_name, execution_arn)

        except Exception as e:
            logger.exception("Failed to start pipeline: %s", pipeline_name)
            results[pipeline_name] = {
                "status": "failed",
                "error": str(e),
            }

    return {
        "statusCode": 200,
        "body": json.dumps(results, default=str),
    }
