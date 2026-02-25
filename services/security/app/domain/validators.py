"""Input validators for the Security & Privacy service."""

from __future__ import annotations

from .models import ConsentPurpose, DataCategory


def validate_consent_request(
    profile_id: str,
    purpose: str,
    duration_days: int,
) -> None:
    """Validate a consent grant request."""
    errors: list[str] = []
    if not profile_id or not profile_id.strip():
        errors.append("profile_id is required")
    if purpose not in ConsentPurpose.__members__:
        errors.append(
            f"Invalid purpose '{purpose}'. "
            f"Must be one of: {', '.join(ConsentPurpose.__members__)}"
        )
    if duration_days < 1:
        errors.append("duration_days must be at least 1")
    if duration_days > 3650:
        errors.append("duration_days cannot exceed 3650 (10 years)")
    if errors:
        raise ValueError("; ".join(errors))


def validate_audit_query(
    profile_id: str | None,
    actor_id: str | None,
    limit: int,
) -> None:
    """Validate an audit log query."""
    if not profile_id and not actor_id:
        raise ValueError("Either profile_id or actor_id must be specified")
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")


def validate_lineage_query(
    profile_id: str,
    category: str | None,
) -> None:
    """Validate a lineage query."""
    if not profile_id or not profile_id.strip():
        raise ValueError("profile_id is required")
    if category is not None and category not in DataCategory.__members__:
        raise ValueError(
            f"Invalid category '{category}'. "
            f"Must be one of: {', '.join(DataCategory.__members__)}"
        )
