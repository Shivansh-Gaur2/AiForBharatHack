"""Configuration for the Security & Privacy service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    environment: str = "local"
    aws_region: str = "ap-south-1"
    dynamodb_endpoint_url: str = ""
    dynamodb_table_name: str = "rural-credit-security"
    sns_topic_arn: str = ""
    log_level: str = "INFO"

    # Cognito settings (for auth middleware)
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""
    cognito_skip_verification: bool = True

    @staticmethod
    def from_env() -> Settings:
        return Settings(
            environment=os.getenv("ENVIRONMENT", "local"),
            aws_region=os.getenv("AWS_REGION", "ap-south-1"),
            dynamodb_endpoint_url=os.getenv("DYNAMODB_ENDPOINT_URL", ""),
            dynamodb_table_name=os.getenv(
                "DYNAMODB_TABLE_NAME", "rural-credit-security",
            ),
            sns_topic_arn=os.getenv("SNS_TOPIC_ARN", ""),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            cognito_user_pool_id=os.getenv("COGNITO_USER_POOL_ID", ""),
            cognito_app_client_id=os.getenv("COGNITO_APP_CLIENT_ID", ""),
            cognito_skip_verification=os.getenv(
                "COGNITO_SKIP_VERIFICATION", "true",
            ).lower() == "true",
        )
