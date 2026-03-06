"""FastAPI application + Mangum handler for the Security & Privacy Service.

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

from services.shared.events import AsyncInMemoryEventPublisher
from services.shared.auth.middleware import configure_auth
from services.shared.observability import configure_logging
from services.shared.observability.middleware import (
    ErrorHandlingMiddleware,
    RequestTracingMiddleware,
)

from .api.auth_routes import router as auth_router, set_auth_service
from .api.routes import router, set_security_service
from .config import Settings
from .domain.auth_service import AuthService
from .domain.services import SecurityService
from .infrastructure.dynamodb_repo import DynamoDBSecurityRepository
from .infrastructure.memory_repo import InMemorySecurityRepository

# ---------------------------------------------------------------------------
# Settings & Logging
# ---------------------------------------------------------------------------
settings = Settings.from_env()

configure_logging(
    service_name="security",
    level=settings.log_level,
    json_output=settings.environment != "local",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Rural Credit Advisor - Security & Privacy Service",
    description="Consent management, audit logging, data lineage, retention policies, and authentication.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

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
    repo = DynamoDBSecurityRepository(ddb, settings.dynamodb_table_name)
    logger.info("Using DynamoDBSecurityRepository (table=%s)", settings.dynamodb_table_name)
else:
    repo = InMemorySecurityRepository()
    logger.info("Using InMemorySecurityRepository (STORAGE_BACKEND=memory)")

# Event publisher
if settings.sns_topic_arn and settings.storage_backend == "dynamodb":
    from .infrastructure.sqs_events import create_security_event_publisher

    event_publisher = create_security_event_publisher(
        settings.sns_topic_arn, settings.aws_region,
    )
    logger.info("Using SNS event publisher: %s", settings.sns_topic_arn)
else:
    event_publisher = AsyncInMemoryEventPublisher()
    logger.info("Using AsyncInMemoryEventPublisher (memory mode or no SNS topic)")

# Assemble service — the DynamoDB repo implements all four repository interfaces
security_service = SecurityService(
    consent_repo=repo,
    audit_repo=repo,
    lineage_repo=repo,
    retention_repo=repo,
    events=event_publisher,
)
set_security_service(security_service)

# Authentication service — re-uses the same DynamoDB repo
auth_service = AuthService(user_repo=repo)
set_auth_service(auth_service)

# Auth
configure_auth()

# Middleware (order matters: outermost first)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(ErrorHandlingMiddleware, service_name="security")

app.include_router(auth_router)
app.include_router(router)

logger.info("Security service bootstrapped (env=%s)", settings.environment)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "security"}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------
handler = Mangum(app)
