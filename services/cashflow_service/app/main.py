"""FastAPI application + Mangum handler for the Cash Flow service.

Composition root — wires dependencies together.
"""

from __future__ import annotations

import logging

import boto3
from fastapi import FastAPI
from mangum import Mangum

from services.shared.events import AsyncInMemoryEventPublisher

from .api.routes import router, set_cashflow_service
from .config import Settings
from .domain.services import CashFlowService
from .infrastructure.data_providers import (
    StubLoanDataProvider,
    StubMarketDataProvider,
    StubProfileDataProvider,
    StubWeatherDataProvider,
)
from .infrastructure.dynamodb_repo import DynamoDBCashFlowRepository
from .infrastructure.sqs_events import create_cashflow_event_publisher

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
    title="Rural Credit Advisor — Cash Flow Service",
    description="Seasonal cash-flow prediction, repayment capacity, and credit timing alignment.",
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
repo = DynamoDBCashFlowRepository(ddb, settings.dynamodb_table_name)

# Weather provider — use HTTP adapter when API key is configured
if settings.weather_api_key:
    from .infrastructure.external_data import HttpWeatherDataProvider
    weather_provider = HttpWeatherDataProvider(api_key=settings.weather_api_key)
    logger.info("Using HttpWeatherDataProvider (OpenWeather)")
else:
    weather_provider = StubWeatherDataProvider()
    logger.info("Using StubWeatherDataProvider (no WEATHER_API_KEY)")

# Market provider — use HTTP adapter when URL is configured
if settings.market_api_url:
    from .infrastructure.external_data import HttpMarketDataProvider
    market_provider = HttpMarketDataProvider(base_url=settings.market_api_url)
    logger.info("Using HttpMarketDataProvider → %s", settings.market_api_url)
else:
    market_provider = StubMarketDataProvider()
    logger.info("Using StubMarketDataProvider (no MARKET_API_URL)")

# Profile provider — use HTTP adapter when URL is configured
if settings.profile_service_url:
    from .infrastructure.external_data import HttpProfileDataProvider
    profile_provider = HttpProfileDataProvider(settings.profile_service_url)
    logger.info("Using HttpProfileDataProvider → %s", settings.profile_service_url)
else:
    profile_provider = StubProfileDataProvider()
    logger.info("Using StubProfileDataProvider (no PROFILE_SERVICE_URL)")

# Loan provider — use HTTP adapter when URL is configured
if settings.loan_service_url:
    from .infrastructure.external_data import HttpLoanDataProvider
    loan_provider = HttpLoanDataProvider(settings.loan_service_url)
    logger.info("Using HttpLoanDataProvider → %s", settings.loan_service_url)
else:
    loan_provider = StubLoanDataProvider()
    logger.info("Using StubLoanDataProvider (no LOAN_SERVICE_URL)")

# Event publisher
if settings.sns_topic_arn:
    event_publisher = create_cashflow_event_publisher(
        settings.sns_topic_arn, settings.aws_region,
    )
    logger.info("Using SNS event publisher: %s", settings.sns_topic_arn)
else:
    event_publisher = AsyncInMemoryEventPublisher()
    logger.info("Using AsyncInMemoryEventPublisher (no SNS topic)")

# Assemble service
cashflow_service = CashFlowService(
    repo=repo,
    weather_provider=weather_provider,
    market_provider=market_provider,
    profile_provider=profile_provider,
    loan_provider=loan_provider,
    events=event_publisher,
)
set_cashflow_service(cashflow_service)

app.include_router(router)

logger.info("Cash Flow service bootstrapped (env=%s)", settings.environment)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "cashflow"}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------
handler = Mangum(app)
