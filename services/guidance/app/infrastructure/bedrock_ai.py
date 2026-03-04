"""Amazon Bedrock AI provider for guidance explanation enrichment.

Calls Amazon Bedrock InvokeModel to generate a farmer-friendly natural-language
summary for the credit guidance output.  Degrades gracefully to None when
Bedrock is unavailable or not configured — the template-based summary is used
as fallback in that case.

Supported model families (auto-detected from BEDROCK_MODEL_ID env var):
  - ``amazon.nova-*`` / ``us.amazon.nova-*``  — Amazon Nova Micro/Lite
  - ``anthropic.claude-*`` / ``us.anthropic.claude-*`` — Claude 3 Haiku/Sonnet
  - ``amazon.titan-text-*`` — Amazon Titan Text (legacy)

How to get set up
-----------------
1. Open AWS Console → Amazon Bedrock → Model Access
2. Enable the model you want (e.g. Amazon Nova Micro)
3. Create an IAM user/role with policy ``AmazonBedrockFullAccess``
4. Generate Access Keys and put them in your .env:
       AWS_ACCESS_KEY_ID=...
       AWS_SECRET_ACCESS_KEY=...
       BEDROCK_MODEL_ID=us.amazon.nova-micro-v1:0
       BEDROCK_REGION=us-east-1
"""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a friendly rural credit advisor helping small farmers in India "
    "understand their loan options. Use simple, clear language. "
    "Do not use bullet points or headers. Write only a single paragraph."
)

_USER_TEMPLATE = """\
Based on this financial analysis, write a 3-4 sentence plain-English summary
a rural farmer can easily understand:

- Loan purpose: {purpose}
- Recommended amount: Rs {min_amount:,.0f} to Rs {max_amount:,.0f}
- Best time to borrow: {timing}
- Risk level: {risk} (score {score:.0f}/1000)
- Debt-to-income ratio: {dti:.0%}
- Monthly repayment capacity: Rs {capacity:,.0f}
- Confidence: {confidence}

If the risk is HIGH or VERY_HIGH, include a gentle caution. Otherwise be encouraging.
Write only the summary paragraph.
"""


def _build_prompt(context: dict[str, Any]) -> str:
    return _USER_TEMPLATE.format(**context)


# ---------------------------------------------------------------------------
# Model request / response helpers
# ---------------------------------------------------------------------------

def _build_nova_body(prompt: str) -> bytes:
    """Build request body for Amazon Nova models (direct and cross-region profiles)."""
    body = {
        "messages": [
            {"role": "user", "content": [{"text": f"{_SYSTEM_PROMPT}\n\n{prompt}"}]}
        ],
        "inferenceConfig": {
            "maxTokens": 250,
            "temperature": 0.4,
            "topP": 0.9,
        },
    }
    return json.dumps(body).encode()


def _parse_nova_response(response_body: dict) -> str:
    try:
        return response_body["output"]["message"]["content"][0]["text"].strip()
    except (KeyError, IndexError):
        return ""


def _build_titan_body(prompt: str) -> bytes:
    """Build request body for Amazon Titan Text models."""
    body = {
        "inputText": f"{_SYSTEM_PROMPT}\n\n{prompt}",
        "textGenerationConfig": {
            "maxTokenCount": 250,
            "temperature": 0.4,
            "topP": 0.9,
        },
    }
    return json.dumps(body).encode()


def _parse_titan_response(response_body: dict) -> str:
    results = response_body.get("results", [])
    if results:
        return results[0].get("outputText", "").strip()
    return ""


def _build_claude_body(prompt: str) -> bytes:
    """Build request body for Anthropic Claude models via Bedrock."""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 250,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    return json.dumps(body).encode()


def _parse_claude_response(response_body: dict) -> str:
    content = response_body.get("content", [])
    if content and isinstance(content, list):
        return content[0].get("text", "").strip()
    return ""


# ---------------------------------------------------------------------------
# BedrockAIProvider
# ---------------------------------------------------------------------------

class BedrockAIProvider:
    """Generates AI-enriched guidance summaries via Amazon Bedrock.

    Parameters
    ----------
    model_id:
        Bedrock model ID or cross-region inference profile, e.g.
        ``us.amazon.nova-micro-v1:0`` or
        ``anthropic.claude-3-haiku-20240307-v1:0``.
    region:
        AWS region where the model is available.
    """

    def __init__(self, model_id: str, region: str = "us-east-1") -> None:
        self._model_id = model_id
        # Detect model family (handle both direct IDs and cross-region us./global. prefixes)
        base = model_id.split("/")[-1]  # strip ARN path if present
        self._is_claude = "anthropic." in base
        self._is_nova = "amazon.nova" in base
        try:
            self._client = boto3.client("bedrock-runtime", region_name=region)
            logger.info("BedrockAIProvider initialised (model=%s, region=%s)", model_id, region)
        except Exception as exc:
            logger.warning("Failed to initialise Bedrock client: %s", exc)
            self._client = None

    async def generate_summary(self, context: dict[str, Any]) -> str | None:
        """Generate an AI narrative summary.

        Returns ``None`` on any failure so callers can fall back gracefully.
        """
        if self._client is None:
            return None

        prompt = _build_prompt(context)
        if self._is_claude:
            body = _build_claude_body(prompt)
        elif self._is_nova:
            body = _build_nova_body(prompt)
        else:
            body = _build_titan_body(prompt)

        try:
            response = self._client.invoke_model(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            response_body = json.loads(response["body"].read())

            text = (
                _parse_claude_response(response_body)
                if self._is_claude
                else _parse_nova_response(response_body)
                if self._is_nova
                else _parse_titan_response(response_body)
            )

            if text:
                logger.debug("Bedrock generated summary (%d chars)", len(text))
                return text

            logger.warning("Bedrock returned empty text")
            return None

        except (BotoCoreError, ClientError) as exc:
            logger.warning("Bedrock InvokeModel failed: %s", exc)
            return None
        except Exception as exc:
            logger.warning("Unexpected Bedrock error: %s", exc)
            return None