"""Application services for Security & Privacy.

Orchestrates consent management, audit logging, data lineage tracking,
and retention policy enforcement.
"""

from __future__ import annotations

import logging

from services.shared.events import AsyncEventPublisher, DomainEvent
from services.shared.models import ProfileId

from .interfaces import (
    AuditRepository,
    ConsentRepository,
    DataLineageRepository,
    RetentionPolicyRepository,
)
from .models import (
    AuditAction,
    AuditEntry,
    Consent,
    ConsentPurpose,
    DataCategory,
    DataLineageRecord,
    DataUsageSummary,
    RetentionPolicy,
    build_data_usage_summary,
    build_default_retention_policies,
    create_audit_entry,
    create_consent,
    create_lineage_record,
)
from .validators import validate_consent_request, validate_lineage_query

logger = logging.getLogger(__name__)


class SecurityService:
    """Application service — orchestrates security & privacy workflows."""

    def __init__(
        self,
        consent_repo: ConsentRepository,
        audit_repo: AuditRepository,
        lineage_repo: DataLineageRepository,
        retention_repo: RetentionPolicyRepository,
        events: AsyncEventPublisher,
    ) -> None:
        self._consent = consent_repo
        self._audit = audit_repo
        self._lineage = lineage_repo
        self._retention = retention_repo
        self._events = events

    # ------------------------------------------------------------------
    # Consent Management (Req 9.3)
    # ------------------------------------------------------------------

    async def grant_consent(
        self,
        profile_id: ProfileId,
        purpose: str,
        granted_by: str = "",
        duration_days: int = 365,
    ) -> Consent:
        """Grant consent for a specific data-use purpose."""
        validate_consent_request(profile_id, purpose, duration_days)
        consent_purpose = ConsentPurpose(purpose)

        # Check for existing active consent
        existing = await self._consent.find_active_consent(profile_id, consent_purpose)
        if existing and existing.is_active():
            # Renew instead of duplicating
            existing.renew(duration_days)
            await self._consent.update_consent(existing)
            await self._log_audit(
                actor_id=granted_by or "SYSTEM",
                action=AuditAction.CONSENT_GRANTED,
                resource_type="consent",
                resource_id=existing.consent_id,
                profile_id=profile_id,
                details={"purpose": purpose, "renewed": True, "version": existing.version},
            )
            return existing

        consent = create_consent(profile_id, consent_purpose, granted_by, duration_days)
        await self._consent.save_consent(consent)

        await self._log_audit(
            actor_id=granted_by or "SYSTEM",
            action=AuditAction.CONSENT_GRANTED,
            resource_type="consent",
            resource_id=consent.consent_id,
            profile_id=profile_id,
            details={"purpose": purpose},
        )
        await self._events.publish(DomainEvent(
            event_type="consent.granted",
            aggregate_id=consent.consent_id,
            payload={"profile_id": profile_id, "purpose": purpose},
        ))
        logger.info("Consent granted for %s: %s", profile_id, purpose)
        return consent

    async def revoke_consent(
        self,
        consent_id: str,
        reason: str = "",
        revoked_by: str = "",
    ) -> Consent:
        """Revoke a previously granted consent."""
        consent = await self._consent.find_consent_by_id(consent_id)
        if consent is None:
            raise ValueError(f"Consent {consent_id} not found")

        consent.revoke(reason)
        await self._consent.update_consent(consent)

        await self._log_audit(
            actor_id=revoked_by or "SYSTEM",
            action=AuditAction.CONSENT_REVOKED,
            resource_type="consent",
            resource_id=consent_id,
            profile_id=consent.profile_id,
            details={"reason": reason},
        )
        await self._events.publish(DomainEvent(
            event_type="consent.revoked",
            aggregate_id=consent_id,
            payload={"profile_id": consent.profile_id, "reason": reason},
        ))
        logger.info("Consent revoked: %s", consent_id)
        return consent

    async def check_consent(
        self,
        profile_id: ProfileId,
        purpose: str,
    ) -> bool:
        """Check if active consent exists for a specific purpose."""
        consent_purpose = ConsentPurpose(purpose)
        consent = await self._consent.find_active_consent(profile_id, consent_purpose)
        return consent is not None and consent.is_active()

    async def get_consent(self, consent_id: str) -> Consent | None:
        return await self._consent.find_consent_by_id(consent_id)

    async def get_profile_consents(self, profile_id: ProfileId) -> list[Consent]:
        return await self._consent.find_consents_by_profile(profile_id)

    # ------------------------------------------------------------------
    # Audit Logging
    # ------------------------------------------------------------------

    async def _log_audit(
        self,
        actor_id: str,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        profile_id: str,
        *,
        details: dict | None = None,
        ip_address: str = "",
        success: bool = True,
    ) -> AuditEntry:
        entry = create_audit_entry(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            profile_id=profile_id,
            details=details,
            ip_address=ip_address,
            success=success,
        )
        await self._audit.save_entry(entry)
        return entry

    async def log_data_access(
        self,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        profile_id: str,
        *,
        details: dict | None = None,
        ip_address: str = "",
    ) -> AuditEntry:
        """Log a data access event (Req 9.4 — visibility)."""
        return await self._log_audit(
            actor_id=actor_id,
            action=AuditAction.DATA_ACCESS,
            resource_type=resource_type,
            resource_id=resource_id,
            profile_id=profile_id,
            details=details,
            ip_address=ip_address,
        )

    async def get_audit_log(
        self,
        profile_id: str,
        limit: int = 50,
    ) -> list[AuditEntry]:
        return await self._audit.find_entries_by_profile(profile_id, limit)

    # ------------------------------------------------------------------
    # Data Lineage (Req 9.4)
    # ------------------------------------------------------------------

    async def record_data_access(
        self,
        profile_id: ProfileId,
        data_category: str,
        source_service: str,
        target_service: str,
        action: str,
        *,
        fields_accessed: list[str] | None = None,
        purpose: str = "",
        consent_id: str = "",
        actor_id: str = "",
    ) -> DataLineageRecord:
        """Record a data lineage event — who accessed what, from where."""
        validate_lineage_query(profile_id, data_category)
        record = create_lineage_record(
            profile_id=profile_id,
            data_category=DataCategory(data_category),
            source_service=source_service,
            target_service=target_service,
            action=action,
            fields_accessed=fields_accessed,
            purpose=purpose,
            consent_id=consent_id,
            actor_id=actor_id,
        )
        await self._lineage.save_record(record)
        logger.debug("Lineage recorded: %s -> %s (%s)", source_service, target_service, action)
        return record

    async def get_data_lineage(
        self,
        profile_id: ProfileId,
        category: str | None = None,
    ) -> list[DataLineageRecord]:
        """Get data lineage records for a profile."""
        validate_lineage_query(profile_id, category)
        if category:
            return await self._lineage.find_records_by_category(
                profile_id, DataCategory(category),
            )
        return await self._lineage.find_records_by_profile(profile_id)

    # ------------------------------------------------------------------
    # Data Usage Summary — borrower visibility (Req 9.4)
    # ------------------------------------------------------------------

    async def get_data_usage_summary(
        self,
        profile_id: ProfileId,
    ) -> DataUsageSummary:
        """Generate a complete summary of how a borrower's data is used."""
        consents = await self._consent.find_consents_by_profile(profile_id)
        lineage = await self._lineage.find_records_by_profile(profile_id)
        policies = await self._retention.find_all_policies()
        return build_data_usage_summary(profile_id, consents, lineage, policies)

    # ------------------------------------------------------------------
    # Retention Policies (Req 9.5)
    # ------------------------------------------------------------------

    async def get_retention_policies(self) -> list[RetentionPolicy]:
        return await self._retention.find_all_policies()

    async def initialize_default_policies(self) -> list[RetentionPolicy]:
        """Seed the default retention policies if not already present."""
        existing = await self._retention.find_all_policies()
        if existing:
            return existing
        policies = build_default_retention_policies()
        for p in policies:
            await self._retention.save_policy(p)
        logger.info("Initialized %d default retention policies", len(policies))
        return policies

    async def check_retention_expired(
        self,
        profile_id: ProfileId,
        data_category: str,
        data_created_at_iso: str,
    ) -> dict:
        """Check if data has exceeded its retention period."""
        from datetime import datetime

        cat = DataCategory(data_category)
        policy = await self._retention.find_policy_by_category(cat)
        if policy is None:
            return {"expired": False, "reason": "No retention policy found"}

        created_at = datetime.fromisoformat(data_created_at_iso)
        expired = policy.is_expired(created_at)
        return {
            "expired": expired,
            "data_category": data_category,
            "retention_days": policy.retention_days,
            "action": policy.action.value,
            "reason": f"Data {'has' if expired else 'has not'} exceeded {policy.retention_days}-day retention",
        }

    async def delete_profile_data(self, profile_id: ProfileId) -> int:
        """Delete consent grants and lineage records for a profile.

        Audit logs are intentionally preserved as an immutable audit trail.
        Returns total number of records deleted.
        """
        consent_count = await self._consent.delete_by_profile(profile_id)
        lineage_count = await self._lineage.delete_by_profile(profile_id)
        return consent_count + lineage_count
