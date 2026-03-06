"""FastAPI application + Mangum handler for the Guidance Service.

Composition root - wires dependencies together.
"""

from __future__ import annotations

import logging
from pathlib import Path

import boto3
from dotenv import load_dotenv
from fastapi import FastAPI
from mangum import Mangum

load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)

from fastapi.middleware.cors import CORSMiddleware

from services.shared.auth.middleware import configure_auth, require_auth
from services.shared.events import AsyncInMemoryEventPublisher
from services.shared.observability import configure_logging
from services.shared.observability.middleware import (
    ErrorHandlingMiddleware,
    RequestTracingMiddleware,
)

from .api.routes import router, set_guidance_service
from .config import Settings
from .domain.services import GuidanceService
from .infrastructure.data_providers import (
    StubAIProvider,
    StubAlertDataProvider,
    StubCashFlowDataProvider,
    StubLoanDataProvider,
    StubProfileDataProvider,
    StubRiskDataProvider,
)
from .infrastructure.dynamodb_repo import DynamoDBGuidanceRepository
from .infrastructure.memory_repo import InMemoryGuidanceRepository
from .infrastructure.sqs_events import create_guidance_event_publisher

# ---------------------------------------------------------------------------
# Settings & Logging
# ---------------------------------------------------------------------------
settings = Settings.from_env()

configure_logging(
    service_name="guidance",
    level=settings.log_level,
    json_output=settings.environment != "local",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Rural Credit Advisor - Guidance Service",
    description="Personalized credit guidance, timing optimization, and amount recommendations.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# Wire dependencies
# ---------------------------------------------------------------------------


def _create_dynamodb_resource():
    kwargs = {"region_name": settings.aws_region}
    if settings.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
    return boto3.resource("dynamodb", **kwargs)


if settings.storage_backend == "dynamodb":
    ddb = _create_dynamodb_resource()
    repo = DynamoDBGuidanceRepository(ddb, settings.dynamodb_table_name)
    logger.info("Using DynamoDBGuidanceRepository (table=%s)", settings.dynamodb_table_name)
else:
    repo = InMemoryGuidanceRepository()
    logger.info("Using InMemoryGuidanceRepository (STORAGE_BACKEND=memory)")

# Risk provider
if settings.risk_service_url:
    from .infrastructure.external_data import HttpRiskDataProvider
    risk_provider = HttpRiskDataProvider(settings.risk_service_url)
    logger.info("Using HttpRiskDataProvider -> %s", settings.risk_service_url)
else:
    risk_provider = StubRiskDataProvider()
    logger.info("Using StubRiskDataProvider (no RISK_SERVICE_URL)")

# CashFlow provider
if settings.cashflow_service_url:
    from .infrastructure.external_data import HttpCashFlowDataProvider
    cashflow_provider = HttpCashFlowDataProvider(settings.cashflow_service_url)
    logger.info("Using HttpCashFlowDataProvider -> %s", settings.cashflow_service_url)
else:
    cashflow_provider = StubCashFlowDataProvider()
    logger.info("Using StubCashFlowDataProvider (no CASHFLOW_SERVICE_URL)")

# Loan provider
if settings.loan_service_url:
    from .infrastructure.external_data import HttpLoanDataProvider
    loan_provider = HttpLoanDataProvider(settings.loan_service_url)
    logger.info("Using HttpLoanDataProvider -> %s", settings.loan_service_url)
else:
    loan_provider = StubLoanDataProvider()
    logger.info("Using StubLoanDataProvider (no LOAN_SERVICE_URL)")

# Profile provider
if settings.profile_service_url:
    from .infrastructure.external_data import HttpProfileDataProvider
    profile_provider = HttpProfileDataProvider(settings.profile_service_url)
    logger.info("Using HttpProfileDataProvider -> %s", settings.profile_service_url)
else:
    profile_provider = StubProfileDataProvider()
    logger.info("Using StubProfileDataProvider (no PROFILE_SERVICE_URL)")

# Alert provider
if settings.early_warning_service_url:
    from .infrastructure.external_data import HttpAlertDataProvider
    alert_provider = HttpAlertDataProvider(settings.early_warning_service_url)
    logger.info("Using HttpAlertDataProvider -> %s", settings.early_warning_service_url)
else:
    alert_provider = StubAlertDataProvider()
    logger.info("Using StubAlertDataProvider (no EARLY_WARNING_SERVICE_URL)")

# AI explanation provider (Amazon Bedrock) — optional, enhances guidance summaries
if settings.bedrock_model_id:
    from .infrastructure.bedrock_ai import BedrockAIProvider
    ai_provider = BedrockAIProvider(
        model_id=settings.bedrock_model_id,
        region=settings.bedrock_region,
    )
    logger.info(
        "Using BedrockAIProvider (model=%s, region=%s)",
        settings.bedrock_model_id, settings.bedrock_region,
    )
else:
    ai_provider = StubAIProvider()
    logger.info("Using StubAIProvider (no BEDROCK_MODEL_ID)")

# Event publisher
if settings.sns_topic_arn and settings.storage_backend == "dynamodb":
    event_publisher = create_guidance_event_publisher(
        settings.sns_topic_arn, settings.aws_region,
    )
    logger.info("Using SNS event publisher: %s", settings.sns_topic_arn)
else:
    event_publisher = AsyncInMemoryEventPublisher()
    logger.info("Using AsyncInMemoryEventPublisher (memory mode or no SNS topic)")

# Assemble service
guidance_service = GuidanceService(
    repo=repo,
    risk_provider=risk_provider,
    cashflow_provider=cashflow_provider,
    loan_provider=loan_provider,
    profile_provider=profile_provider,
    alert_provider=alert_provider,
    events=event_publisher,
    ai_provider=ai_provider,
)
set_guidance_service(guidance_service)

# Auth
configure_auth()

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware (order matters: outermost first)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(ErrorHandlingMiddleware, service_name="guidance")

app.include_router(router)

logger.info("Guidance service bootstrapped (env=%s)", settings.environment)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "guidance"}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------
handler = Mangum(app)
