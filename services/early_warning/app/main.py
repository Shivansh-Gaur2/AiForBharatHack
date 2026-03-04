"""FastAPI application + Mangum handler for the Early Warning service.

Composition root — wires dependencies together.
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

from .api.routes import router, set_early_warning_service
from .config import Settings
from .domain.services import EarlyWarningService
from .infrastructure.data_providers import (
    StubCashFlowDataProvider,
    StubLoanDataProvider,
    StubProfileDataProvider,
    StubRiskDataProvider,
)
from .infrastructure.dynamodb_repo import DynamoDBAlertRepository
from .infrastructure.sqs_events import create_early_warning_event_publisher

# ---------------------------------------------------------------------------
# Settings & Logging
# ---------------------------------------------------------------------------
settings = Settings.from_env()

configure_logging(
    service_name="early-warning",
    level=settings.log_level,
    json_output=settings.environment != "local",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Rural Credit Advisor — Early Warning & Scenarios",
    description="Alert generation, severity escalation, and scenario simulation for rural borrowers.",
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


ddb = _create_dynamodb_resource()
repo = DynamoDBAlertRepository(ddb, settings.dynamodb_table_name)

# Risk provider
if settings.risk_service_url:
    from .infrastructure.external_data import HttpRiskDataProvider
    risk_provider = HttpRiskDataProvider(settings.risk_service_url)
    logger.info("Using HttpRiskDataProvider → %s", settings.risk_service_url)
else:
    risk_provider = StubRiskDataProvider()
    logger.info("Using StubRiskDataProvider (no RISK_SERVICE_URL)")

# CashFlow provider
if settings.cashflow_service_url:
    from .infrastructure.external_data import HttpCashFlowDataProvider
    cashflow_provider = HttpCashFlowDataProvider(settings.cashflow_service_url)
    logger.info("Using HttpCashFlowDataProvider → %s", settings.cashflow_service_url)
else:
    cashflow_provider = StubCashFlowDataProvider()
    logger.info("Using StubCashFlowDataProvider (no CASHFLOW_SERVICE_URL)")

# Loan provider
if settings.loan_service_url:
    from .infrastructure.external_data import HttpLoanDataProvider
    loan_provider = HttpLoanDataProvider(settings.loan_service_url)
    logger.info("Using HttpLoanDataProvider → %s", settings.loan_service_url)
else:
    loan_provider = StubLoanDataProvider()
    logger.info("Using StubLoanDataProvider (no LOAN_SERVICE_URL)")

# Profile provider
if settings.profile_service_url:
    from .infrastructure.external_data import HttpProfileDataProvider
    profile_provider = HttpProfileDataProvider(settings.profile_service_url)
    logger.info("Using HttpProfileDataProvider → %s", settings.profile_service_url)
else:
    profile_provider = StubProfileDataProvider()
    logger.info("Using StubProfileDataProvider (no PROFILE_SERVICE_URL)")

# Event publisher
if settings.sns_topic_arn:
    event_publisher = create_early_warning_event_publisher(
        settings.sns_topic_arn, settings.aws_region,
    )
    logger.info("Using SNS event publisher: %s", settings.sns_topic_arn)
else:
    event_publisher = AsyncInMemoryEventPublisher()
    logger.info("Using AsyncInMemoryEventPublisher (no SNS topic)")

# Assemble service
early_warning_service = EarlyWarningService(
    repo=repo,
    risk_provider=risk_provider,
    cashflow_provider=cashflow_provider,
    loan_provider=loan_provider,
    profile_provider=profile_provider,
    events=event_publisher,
)
set_early_warning_service(early_warning_service)

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
app.add_middleware(ErrorHandlingMiddleware, service_name="early-warning")

app.include_router(router)

logger.info("Early Warning service bootstrapped (env=%s)", settings.environment)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "early-warning"}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------
handler = Mangum(app)
