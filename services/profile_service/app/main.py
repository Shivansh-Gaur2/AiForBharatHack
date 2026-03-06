"""FastAPI application + Mangum handler for AWS Lambda.

This is the composition root — where we wire dependencies together:
- Domain services get their concrete infrastructure adapters injected
- FastAPI routers are registered
- Mangum wraps the ASGI app for Lambda invocation
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
from services.shared.events import InMemoryEventPublisher
from services.shared.observability import configure_logging
from services.shared.observability.middleware import (
    ErrorHandlingMiddleware,
    RequestTracingMiddleware,
)

from .api.routes import router, set_profile_service
from .config import Settings
from .domain.services import ProfileService
from .infrastructure.dynamodb_repo import DynamoDBProfileRepository
from .infrastructure.memory_repo import InMemoryProfileRepository
from .infrastructure.sqs_events import create_profile_event_publisher

# ---------------------------------------------------------------------------
# Settings & Logging
# ---------------------------------------------------------------------------
settings = Settings.from_env()

configure_logging(
    service_name="profile-service",
    level=settings.log_level,
    json_output=settings.environment != "local",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Rural Credit Advisor — Profile Service",
    description="Manages comprehensive borrower profiles for rural credit advisory.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# Wire dependencies (composition root)
# ---------------------------------------------------------------------------
def _create_dynamodb_resource():
    kwargs = {"region_name": settings.aws_region}
    if settings.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
    return boto3.resource("dynamodb", **kwargs)


def _create_sns_client():
    kwargs = {"region_name": settings.aws_region}
    if settings.sns_endpoint_url:
        kwargs["endpoint_url"] = settings.sns_endpoint_url
    return boto3.client("sns", **kwargs)


def _bootstrap() -> None:
    """Wire all dependencies and register routers."""
    # Repository adapter — memory by default, DynamoDB when explicitly requested
    if settings.storage_backend == "dynamodb":
        dynamodb = _create_dynamodb_resource()
        repository = DynamoDBProfileRepository(
            dynamodb_resource=dynamodb,
            table_name=settings.dynamodb_table_name,
        )
        logger.info("Using DynamoDBProfileRepository (table=%s)", settings.dynamodb_table_name)
    else:
        repository = InMemoryProfileRepository()
        logger.info("Using InMemoryProfileRepository (STORAGE_BACKEND=memory)")

    # Event publisher adapter
    if settings.sns_topic_arn and settings.storage_backend == "dynamodb":
        sns_client = _create_sns_client()
        event_publisher = create_profile_event_publisher(
            sns_client=sns_client,
            topic_arn=settings.sns_topic_arn,
        )
    else:
        # Local dev / memory mode — just log events
        event_publisher = InMemoryEventPublisher()
        logger.info("Using InMemoryEventPublisher (memory mode or no SNS topic)")

    # Domain service
    profile_service = ProfileService(
        repository=repository,
        event_publisher=event_publisher,
    )

    # Inject into routes
    set_profile_service(profile_service)
    logger.info("Profile service bootstrapped (env=%s)", settings.environment)


# Bootstrap on import (runs once per Lambda cold start)
_bootstrap()

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
app.add_middleware(ErrorHandlingMiddleware, service_name="profile-service")

# Register router
app.include_router(router)


# Health check
@app.get("/health")
def health():
    return {"status": "healthy", "service": "profile-service"}


# ---------------------------------------------------------------------------
# Lambda handler (via Mangum)
# ---------------------------------------------------------------------------
handler = Mangum(app, lifespan="off")
