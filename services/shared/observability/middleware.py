"""FastAPI middleware for request correlation, timing, and error handling.

Provides production-grade middleware that a staff engineer would expect:

1. **RequestTracingMiddleware** — Attaches a unique ``X-Request-ID`` to
   every request/response.  Downstream logs include the same ID for
   distributed tracing.

2. **ErrorHandlingMiddleware** — Catches unhandled exceptions and returns
   a consistent RFC-7807-style ``application/problem+json`` body instead
   of leaking stack traces to callers.

Usage in a service ``main.py``::

    from services.shared.observability.middleware import (
        RequestTracingMiddleware,
        ErrorHandlingMiddleware,
    )

    app.add_middleware(RequestTracingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware, service_name="profile-service")
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import set_request_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1.  Request Tracing
# ---------------------------------------------------------------------------
class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Propagate or generate a unique request ID for every HTTP call.

    If the caller supplies ``X-Request-ID``, the same value is forwarded;
    otherwise a new UUID-4 is minted.  The ID is also stored in a
    module-global so the :class:`JSONFormatter` can embed it in every
    subsequent log line without explicit threading of context.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        set_request_id(request_id)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1_000

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "%s %s → %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            extra={"duration_ms": round(elapsed_ms, 1)},
        )
        return response


# ---------------------------------------------------------------------------
# 2.  Structured Error Handling
# ---------------------------------------------------------------------------
class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions and return RFC-7807 Problem Details.

    Domain-level ``ValueError`` / ``KeyError`` are mapped to 4xx;
    anything else becomes a 500 with a safe public message.
    """

    def __init__(self, app: Any, service_name: str = "unknown") -> None:
        super().__init__(app)
        self._service = service_name

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        try:
            return await call_next(request)
        except ValueError as exc:
            logger.warning(
                "Validation error on %s %s: %s",
                request.method,
                request.url.path,
                exc,
            )
            return _problem_response(
                status=422,
                title="Validation Error",
                detail=str(exc),
                instance=str(request.url.path),
            )
        except KeyError as exc:
            logger.warning(
                "Resource not found on %s %s: %s",
                request.method,
                request.url.path,
                exc,
            )
            return _problem_response(
                status=404,
                title="Not Found",
                detail=f"Resource not found: {exc}",
                instance=str(request.url.path),
            )
        except Exception:
            logger.exception(
                "Unhandled error on %s %s",
                request.method,
                request.url.path,
            )
            return _problem_response(
                status=500,
                title="Internal Server Error",
                detail="An unexpected error occurred. Please try again later.",
                instance=str(request.url.path),
            )


def _problem_response(
    *,
    status: int,
    title: str,
    detail: str,
    instance: str,
) -> JSONResponse:
    """Build an RFC-7807 ``application/problem+json`` response."""
    return JSONResponse(
        status_code=status,
        content={
            "type": f"about:blank",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": instance,
        },
        media_type="application/problem+json",
    )
