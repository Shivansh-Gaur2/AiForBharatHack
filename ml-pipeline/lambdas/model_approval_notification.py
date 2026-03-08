"""Lambda: Model approval notification.

Invoked when a model package status changes in SageMaker Model Registry.
Sends notifications via SNS for model approval workflows.
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
SNS_TOPIC_ARN = os.environ.get("MODEL_APPROVAL_SNS_TOPIC", "")
APPROVAL_ENDPOINT = os.environ.get("APPROVAL_API_ENDPOINT", "")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle SageMaker Model Registry status change events.

    EventBridge event:
        source: aws.sagemaker
        detail-type: SageMaker Model Package State Change
        detail:
            ModelPackageGroupName: ...
            ModelApprovalStatus: PendingManualApproval | Approved | Rejected
    """
    detail = event.get("detail", {})
    group_name = detail.get("ModelPackageGroupName", "unknown")
    approval_status = detail.get("ModelApprovalStatus", "unknown")
    model_arn = detail.get("ModelPackageArn", "unknown")

    logger.info(
        "Model status change – group=%s, status=%s, arn=%s",
        group_name, approval_status, model_arn,
    )

    # Build notification message
    message = {
        "event": "model_status_change",
        "model_package_group": group_name,
        "approval_status": approval_status,
        "model_arn": model_arn,
        "action_required": approval_status == "PendingManualApproval",
    }

    if approval_status == "PendingManualApproval":
        message["review_url"] = f"{APPROVAL_ENDPOINT}?model_arn={model_arn}"
        message["instructions"] = (
            "A new model version is pending approval. "
            "Review the evaluation metrics and approve or reject."
        )

    # Send SNS notification
    if SNS_TOPIC_ARN:
        try:
            sns = boto3.client("sns", region_name=REGION)
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"[ML Model] {group_name} – {approval_status}",
                Message=json.dumps(message, indent=2),
                MessageAttributes={
                    "model_group": {"DataType": "String", "StringValue": group_name},
                    "status": {"DataType": "String", "StringValue": approval_status},
                },
            )
            logger.info("SNS notification sent to %s", SNS_TOPIC_ARN)
        except Exception:
            logger.exception("Failed to send SNS notification")

    return {
        "statusCode": 200,
        "body": json.dumps(message, default=str),
    }
