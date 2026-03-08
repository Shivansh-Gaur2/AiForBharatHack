"""Configuration for the Risk Assessment service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    dynamodb_table_name: str = "rural-credit-risk"
    dynamodb_endpoint_url: str | None = None
    sns_topic_arn: str | None = None
    aws_region: str = "ap-south-1"
    profile_service_url: str | None = None
    loan_service_url: str | None = None
    weather_api_key: str | None = None
    market_api_key: str | None = None
    skip_auth: bool = True
    storage_backend: str = "memory"  # "memory" | "dynamodb"
    environment: str = "local"
    log_level: str = "INFO"

    @staticmethod
    def from_env() -> Settings:
        return Settings(
            dynamodb_table_name=os.getenv("DYNAMODB_TABLE_NAME", "rural-credit-risk"),
            dynamodb_endpoint_url=os.getenv("DYNAMODB_ENDPOINT_URL"),
            sns_topic_arn=os.getenv("SNS_TOPIC_ARN"),
            aws_region=os.getenv("AWS_REGION", "ap-south-1"),
            profile_service_url=os.getenv("PROFILE_SERVICE_URL"),
            loan_service_url=os.getenv("LOAN_SERVICE_URL"),
            weather_api_key=os.getenv("WEATHER_API_KEY"),
            market_api_key=os.getenv("MARKET_API_KEY"),
            skip_auth=os.getenv("SKIP_AUTH", "true").lower() == "true",
            storage_backend=os.getenv("STORAGE_BACKEND", "memory"),
            environment=os.getenv("ENVIRONMENT", "local"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
