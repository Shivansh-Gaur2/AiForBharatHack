"""FastAPI application + Mangum handler for the AI Advisor Service.

Composition root - wires all dependencies together.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from mangum import Mangum

load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)

from fastapi.middleware.cors import CORSMiddleware

from services.shared.auth.middleware import configure_auth
from services.shared.observability import configure_logging
from services.shared.observability.middleware import (
    ErrorHandlingMiddleware,
    RequestTracingMiddleware,
)

import boto3

from .api.routes import router, set_advisor_service
from .config import Settings
from .domain.services import AIAdvisorService
from .infrastructure.data_aggregator import HttpDataAggregator, StubDataAggregator
from .infrastructure.dynamodb_repo import DynamoDBConversationRepository
from .infrastructure.memory_repo import InMemoryConversationRepository

# ---------------------------------------------------------------------------
# Settings & Logging
# ---------------------------------------------------------------------------
settings = Settings.from_env()

configure_logging(
    service_name="ai-advisor",
    level=settings.log_level,
    json_output=settings.environment != "local",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Rural Credit Advisor - AI Advisor Service",
    description=(
        "Conversational AI advisor powered by Groq (Llama 3.3 70B). "
        "Aggregates data from all micro-services to provide "
        "personalised credit guidance for rural borrowers."
    ),
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# Wire Dependencies
# ---------------------------------------------------------------------------

# LLM Provider
if settings.llm_provider == "groq" and settings.groq_api_key:
    from .infrastructure.groq_llm import GroqLLMProvider
    llm_provider = GroqLLMProvider(
        api_key=settings.groq_api_key,
        model_id=settings.groq_model_id,
    )
    logger.info(
        "Using GroqLLMProvider (model=%s)",
        settings.groq_model_id,
    )
elif settings.llm_provider == "bedrock" and settings.bedrock_model_id:
    from .infrastructure.bedrock_llm import BedrockLLMProvider
    llm_provider = BedrockLLMProvider(
        model_id=settings.bedrock_model_id,
        region=settings.bedrock_region,
    )
    logger.info(
        "Using BedrockLLMProvider (model=%s, region=%s)",
        settings.bedrock_model_id, settings.bedrock_region,
    )
else:
    from .infrastructure.bedrock_llm import StubLLMProvider
    llm_provider = StubLLMProvider()
    logger.info("Using StubLLMProvider (local development mode — set LLM_PROVIDER=groq to use real AI)")

# Data Aggregator
if settings.environment == "local" and not settings.profile_service_url:
    data_aggregator = StubDataAggregator()
    logger.info("Using StubDataAggregator (no service URLs configured)")
else:
    data_aggregator = HttpDataAggregator(
        profile_url=settings.profile_service_url,
        risk_url=settings.risk_service_url,
        cashflow_url=settings.cashflow_service_url,
        loan_url=settings.loan_service_url,
        alert_url=settings.early_warning_service_url,
        guidance_url=settings.guidance_service_url,
    )
    logger.info("Using HttpDataAggregator (cross-service mode)")

# Conversation Repository
def _create_dynamodb_resource():
    kwargs = {"region_name": settings.aws_region}
    if settings.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
    return boto3.resource("dynamodb", **kwargs)


if settings.storage_backend == "dynamodb":
    ddb = _create_dynamodb_resource()
    conversation_repo = DynamoDBConversationRepository(ddb, settings.dynamodb_table_name)
    logger.info("Using DynamoDBConversationRepository (table=%s)", settings.dynamodb_table_name)
else:
    conversation_repo = InMemoryConversationRepository()
    logger.info("Using InMemoryConversationRepository (STORAGE_BACKEND=memory)")

# Assemble the service
advisor_service = AIAdvisorService(
    llm=llm_provider,
    aggregator=data_aggregator,
    repo=conversation_repo,
)
set_advisor_service(advisor_service)

# Auth
configure_auth()

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware (order matters: outermost first)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(ErrorHandlingMiddleware, service_name="ai-advisor")

app.include_router(router)

logger.info("AI Advisor service bootstrapped (env=%s)", settings.environment)


# ---------------------------------------------------------------------------
# Root health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ai-advisor"}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------
handler = Mangum(app)
