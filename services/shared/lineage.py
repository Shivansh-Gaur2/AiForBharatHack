"""Cross-service data lineage client.

When a backend service accesses borrower profile data (the ``profile_id``
owner), it should record that access for audit and compliance purposes
(Req 9 — Data Privacy & Security).

This module provides a lightweight, fire-and-forget client that calls the
Security service's lineage API.  If the Security service is unreachable
or lineage recording is disabled, calls are silently dropped.

Usage::

    from services.shared.lineage import record_data_access

    await record_data_access(
        profile_id="prof_123",
        accessed_by="risk-assessment",
        access_type="READ",
        fields_accessed=["income_records", "personal_info"],
        purpose="risk scoring",
    )
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# The security service URL — resolved from env or defaults to localhost:8007
_SECURITY_URL: str = os.environ.get(
    "SECURITY_SERVICE_URL", "http://127.0.0.1:8007"
).rstrip("/")


async def record_data_access(
    profile_id: str,
    accessed_by: str,
    access_type: str = "READ",
    fields_accessed: list[str] | None = None,
    purpose: str = "",
    *,
    security_url: str | None = None,
) -> bool:
    """Record a data-lineage entry via the Security service.

    Returns True on success, False on failure (never raises).
    """
    base = security_url or _SECURITY_URL
    try:
        import httpx

        payload: dict[str, Any] = {
            "profile_id": profile_id,
            "source_service": accessed_by,
            "destination_service": accessed_by,
            "data_fields": fields_accessed or [],
            "purpose": purpose,
            "access_type": access_type,
        }
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(f"{base}/api/v1/security/lineage", json=payload)
            if r.status_code in (200, 201):
                return True
            logger.debug(
                "Lineage record failed: %s %s", r.status_code, r.text[:200],
            )
            return False
    except Exception:
        logger.debug(
            "Lineage recording unavailable (security service at %s)", base,
            exc_info=True,
        )
        return False


async def record_batch_access(
    profile_ids: list[str],
    accessed_by: str,
    access_type: str = "READ",
    fields_accessed: list[str] | None = None,
    purpose: str = "",
) -> int:
    """Record lineage for multiple profiles. Returns count of successes."""
    ok = 0
    for pid in profile_ids:
        if await record_data_access(
            pid, accessed_by, access_type, fields_accessed, purpose,
        ):
            ok += 1
    return ok
