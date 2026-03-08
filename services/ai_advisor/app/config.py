"""Configuration for the AI Advisor Service - loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    # LLM settings
    bedrock_model_id: str | None = None
    bedrock_region: str = "us-east-1"
    use_stub_llm: bool = True  # Use stub when no Bedrock/Groq configured

    # Groq settings
    groq_api_key: str | None = None
    groq_model_id: str = "llama-3.3-70b-versatile"
    llm_provider: str = "stub"  # "stub" | "groq" | "bedrock"

    # Cross-service URLs
    profile_service_url: str | None = None
    risk_service_url: str | None = None
    cashflow_service_url: str | None = None
    loan_service_url: str | None = None
    early_warning_service_url: str | None = None
    guidance_service_url: str | None = None

    # DynamoDB
    dynamodb_table_name: str = "rural-credit-conversations"
    dynamodb_endpoint_url: str | None = None
    storage_backend: str = "memory"  # "memory" | "dynamodb"

    # General
    aws_region: str = "ap-south-1"
    skip_auth: bool = True
    environment: str = "local"
    log_level: str = "INFO"

    @staticmethod
    def from_env() -> Settings:
        return Settings(
            bedrock_model_id=os.getenv("BEDROCK_MODEL_ID"),
            bedrock_region=os.getenv("BEDROCK_REGION", "us-east-1"),
            use_stub_llm=os.getenv("USE_STUB_LLM", "true").lower() == "true",
            groq_api_key=os.getenv("GROQ_API_KEY"),
            groq_model_id=os.getenv("GROQ_MODEL_ID", "llama-3.3-70b-versatile"),
            llm_provider=os.getenv("LLM_PROVIDER", "stub"),
            profile_service_url=os.getenv("PROFILE_SERVICE_URL", "http://127.0.0.1:8001"),
            risk_service_url=os.getenv("RISK_SERVICE_URL", "http://127.0.0.1:8003"),
            cashflow_service_url=os.getenv("CASHFLOW_SERVICE_URL", "http://127.0.0.1:8004"),
            loan_service_url=os.getenv("LOAN_SERVICE_URL", "http://127.0.0.1:8002"),
            early_warning_service_url=os.getenv("EARLY_WARNING_SERVICE_URL", "http://127.0.0.1:8005"),
            guidance_service_url=os.getenv("GUIDANCE_SERVICE_URL", "http://127.0.0.1:8006"),
            dynamodb_table_name=os.getenv("DYNAMODB_TABLE_NAME", "rural-credit-conversations"),
            dynamodb_endpoint_url=os.getenv("DYNAMODB_ENDPOINT_URL"),
            storage_backend=os.getenv("STORAGE_BACKEND", "memory"),
            aws_region=os.getenv("AWS_REGION", "ap-south-1"),
            skip_auth=os.getenv("SKIP_AUTH", "true").lower() == "true",
            environment=os.getenv("ENVIRONMENT", "local"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
