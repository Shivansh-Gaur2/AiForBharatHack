"""FastAPI application + Mangum handler for the Security & Privacy Service.

Composition root — wires dependencies together.
"""

from __future__ import annotations

import logging

import boto3
from fastapi import FastAPI
from mangum import Mangum

from services.shared.events import AsyncInMemoryEventPublisher

from .api.routes import router, set_security_service
from .config import Settings
from .domain.services import SecurityService
from .infrastructure.dynamodb_repo import DynamoDBSecurityRepository

# ---------------------------------------------------------------------------
# Settings & Logging
# ---------------------------------------------------------------------------
settings = Settings.from_env()

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Rural Credit Advisor - Security & Privacy Service",
    description="Consent management, audit logging, data lineage, and retention policies.",
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
repo = DynamoDBSecurityRepository(ddb, settings.dynamodb_table_name)

# Event publisher
if settings.sns_topic_arn:
    from .infrastructure.sqs_events import create_security_event_publisher

    event_publisher = create_security_event_publisher(
        settings.sns_topic_arn, settings.aws_region,
    )
    logger.info("Using SNS event publisher: %s", settings.sns_topic_arn)
else:
    event_publisher = AsyncInMemoryEventPublisher()
    logger.info("Using AsyncInMemoryEventPublisher (no SNS topic)")

# Assemble service — the DynamoDB repo implements all four repository interfaces
security_service = SecurityService(
    consent_repo=repo,
    audit_repo=repo,
    lineage_repo=repo,
    retention_repo=repo,
    events=event_publisher,
)
set_security_service(security_service)

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
