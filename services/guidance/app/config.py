"""Configuration for the Guidance Service - loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    dynamodb_table_name: str = "rural-credit-guidance"
    dynamodb_endpoint_url: str | None = None
    sns_topic_arn: str | None = None
    aws_region: str = "ap-south-1"
    risk_service_url: str | None = None
    cashflow_service_url: str | None = None
    loan_service_url: str | None = None
    profile_service_url: str | None = None
    early_warning_service_url: str | None = None
    # Amazon Bedrock AI (optional — enriches guidance summaries)
    bedrock_model_id: str | None = None      # e.g. amazon.nova-micro-v1:0
    bedrock_region: str = "us-east-1"
    skip_auth: bool = False
    environment: str = "local"
    log_level: str = "INFO"

    @staticmethod
    def from_env() -> Settings:
        return Settings(
            dynamodb_table_name=os.getenv("DYNAMODB_TABLE_NAME", "rural-credit-guidance"),
            dynamodb_endpoint_url=os.getenv("DYNAMODB_ENDPOINT_URL"),
            sns_topic_arn=os.getenv("SNS_TOPIC_ARN"),
            aws_region=os.getenv("AWS_REGION", "ap-south-1"),
            risk_service_url=os.getenv("RISK_SERVICE_URL"),
            cashflow_service_url=os.getenv("CASHFLOW_SERVICE_URL"),
            loan_service_url=os.getenv("LOAN_SERVICE_URL"),
            profile_service_url=os.getenv("PROFILE_SERVICE_URL"),
            early_warning_service_url=os.getenv("EARLY_WARNING_SERVICE_URL"),
            bedrock_model_id=os.getenv("BEDROCK_MODEL_ID"),
            bedrock_region=os.getenv("BEDROCK_REGION", "us-east-1"),
            skip_auth=os.getenv("SKIP_AUTH", "false").lower() == "true",
            environment=os.getenv("ENVIRONMENT", "local"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
