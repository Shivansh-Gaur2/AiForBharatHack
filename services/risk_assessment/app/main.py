"""FastAPI application + Mangum handler for the Risk Assessment service.

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

from .api.routes import router, set_risk_service
from .config import Settings
from .domain.services import RiskAssessmentService
from .infrastructure.data_providers import StubLoanDataProvider, StubProfileDataProvider
from .infrastructure.dynamodb_repo import DynamoDBRiskRepository
from .infrastructure.memory_repo import InMemoryRiskRepository

# ---------------------------------------------------------------------------
# Settings & Logging
# ---------------------------------------------------------------------------
settings = Settings.from_env()

configure_logging(
    service_name="risk-assessment",
    level=settings.log_level,
    json_output=settings.environment != "local",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Rural Credit Advisor — Risk Assessment Service",
    description="Generates comprehensive risk scores for rural borrowers.",
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
    repo = DynamoDBRiskRepository(ddb, settings.dynamodb_table_name)
    logger.info("Using DynamoDBRiskRepository (table=%s)", settings.dynamodb_table_name)
else:
    repo = InMemoryRiskRepository()
    logger.info("Using InMemoryRiskRepository (STORAGE_BACKEND=memory)")

# Data providers — use HTTP adapters when service URLs are configured,
# otherwise fall back to stubs for local dev/testing
if settings.profile_service_url:
    from .infrastructure.http_providers import HttpProfileDataProvider
    profile_provider = HttpProfileDataProvider(settings.profile_service_url)
    logger.info("Using HttpProfileDataProvider → %s", settings.profile_service_url)
else:
    profile_provider = StubProfileDataProvider()
    logger.info("Using StubProfileDataProvider (no PROFILE_SERVICE_URL)")

if settings.loan_service_url:
    from .infrastructure.http_providers import HttpLoanDataProvider
    loan_provider = HttpLoanDataProvider(settings.loan_service_url)
    logger.info("Using HttpLoanDataProvider → %s", settings.loan_service_url)
else:
    loan_provider = StubLoanDataProvider()
    logger.info("Using StubLoanDataProvider (no LOAN_SERVICE_URL)")

event_publisher = AsyncInMemoryEventPublisher()

risk_service = RiskAssessmentService(
    repo=repo,
    profile_provider=profile_provider,
    loan_provider=loan_provider,
    events=event_publisher,
)
set_risk_service(risk_service)

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
app.add_middleware(ErrorHandlingMiddleware, service_name="risk-assessment")

app.include_router(router)

logger.info("Risk Assessment service bootstrapped (env=%s)", settings.environment)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "risk-assessment"}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------
handler = Mangum(app)
