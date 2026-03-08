"""Configuration — reads from environment variables.

Supports both Lambda (production) and local development modes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Application settings loaded from environment."""

    # DynamoDB
    dynamodb_table_name: str = "rural-credit-profiles"
    dynamodb_endpoint_url: str | None = None  # Set for DynamoDB Local

    # SNS
    sns_topic_arn: str = ""
    sns_endpoint_url: str | None = None  # Set for LocalStack

    # AWS
    aws_region: str = "ap-south-1"  # Mumbai region

    # Auth
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""
    skip_auth: bool = False  # True for local dev

    # Storage
    storage_backend: str = "memory"  # "memory" | "dynamodb"

    # Seeding
    auto_seed: bool = True  # Auto-populate demo profiles when table is empty

    # App
    environment: str = "local"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            dynamodb_table_name=os.getenv("DYNAMODB_TABLE_NAME", "rural-credit-profiles"),
            dynamodb_endpoint_url=os.getenv("DYNAMODB_ENDPOINT_URL"),
            sns_topic_arn=os.getenv("SNS_TOPIC_ARN", ""),
            sns_endpoint_url=os.getenv("SNS_ENDPOINT_URL"),
            aws_region=os.getenv("AWS_REGION", "ap-south-1"),
            cognito_user_pool_id=os.getenv("COGNITO_USER_POOL_ID", ""),
            cognito_app_client_id=os.getenv("COGNITO_APP_CLIENT_ID", ""),
            skip_auth=os.getenv("SKIP_AUTH", "true").lower() == "true",
            storage_backend=os.getenv("STORAGE_BACKEND", "memory"),
            auto_seed=os.getenv("AUTO_SEED", "true").lower() == "true",
            environment=os.getenv("ENVIRONMENT", "local"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    @property
    def is_local(self) -> bool:
        return self.environment == "development"
