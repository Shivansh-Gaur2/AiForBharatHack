"""Unit tests for Security & Privacy application service (async orchestration)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from services.security.app.domain.models import (
    AuditAction,
    AuditEntry,
    Consent,
    ConsentPurpose,
    ConsentStatus,
    DataCategory,
    DataLineageRecord,
    RetentionPolicy,
)
from services.security.app.domain.services import SecurityService
from services.shared.events import AsyncInMemoryEventPublisher


# ---------------------------------------------------------------------------
# In-memory test doubles
# ---------------------------------------------------------------------------
class InMemoryConsentRepository:
    def __init__(self):
        self._store: dict[str, Consent] = {}

    async def save_consent(self, consent: Consent) -> None:
        self._store[consent.consent_id] = consent

    async def find_consent_by_id(self, consent_id: str) -> Consent | None:
        return self._store.get(consent_id)

    async def find_consents_by_profile(self, profile_id: str) -> list[Consent]:
        return [c for c in self._store.values() if c.profile_id == profile_id]

    async def find_active_consent(
        self, profile_id: str, purpose: ConsentPurpose,
    ) -> Consent | None:
        for c in self._store.values():
            if (
                c.profile_id == profile_id
                and c.purpose == purpose
                and c.is_active()
            ):
                return c
        return None

    async def update_consent(self, consent: Consent) -> None:
        self._store[consent.consent_id] = consent


class InMemoryAuditRepository:
    def __init__(self):
        self._store: list[AuditEntry] = []

    async def save_entry(self, entry: AuditEntry) -> None:
        self._store.append(entry)

    async def find_entries_by_profile(
        self, profile_id: str, limit: int = 50,
    ) -> list[AuditEntry]:
        entries = [e for e in self._store if e.profile_id == profile_id]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    async def find_entries_by_actor(
        self, actor_id: str, limit: int = 50,
    ) -> list[AuditEntry]:
        entries = [e for e in self._store if e.actor_id == actor_id]
        return entries[:limit]

    async def find_entries_by_action(
        self, action: str, limit: int = 50,
    ) -> list[AuditEntry]:
        entries = [e for e in self._store if e.action == action]
        return entries[:limit]


class InMemoryLineageRepository:
    def __init__(self):
        self._store: list[DataLineageRecord] = []

    async def save_record(self, record: DataLineageRecord) -> None:
        self._store.append(record)

    async def find_records_by_profile(
        self, profile_id: str, limit: int = 100,
    ) -> list[DataLineageRecord]:
        records = [r for r in self._store if r.profile_id == profile_id]
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records[:limit]

    async def find_records_by_category(
        self, profile_id: str, category: DataCategory,
    ) -> list[DataLineageRecord]:
        return [
            r for r in self._store
            if r.profile_id == profile_id and r.data_category == category
        ]


class InMemoryRetentionRepository:
    def __init__(self):
        self._store: dict[str, RetentionPolicy] = {}

    async def save_policy(self, policy: RetentionPolicy) -> None:
        self._store[policy.policy_id] = policy

    async def find_all_policies(self) -> list[RetentionPolicy]:
        return list(self._store.values())

    async def find_policy_by_category(
        self, category: DataCategory,
    ) -> RetentionPolicy | None:
        for p in self._store.values():
            if p.data_category == category:
                return p
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def consent_repo():
    return InMemoryConsentRepository()


@pytest.fixture()
def audit_repo():
    return InMemoryAuditRepository()


@pytest.fixture()
def lineage_repo():
    return InMemoryLineageRepository()


@pytest.fixture()
def retention_repo():
    return InMemoryRetentionRepository()


@pytest.fixture()
def events():
    return AsyncInMemoryEventPublisher()


@pytest.fixture()
def service(consent_repo, audit_repo, lineage_repo, retention_repo, events):
    return SecurityService(
        consent_repo=consent_repo,
        audit_repo=audit_repo,
        lineage_repo=lineage_repo,
        retention_repo=retention_repo,
        events=events,
    )


# ---------------------------------------------------------------------------
# Consent Management Tests
# ---------------------------------------------------------------------------
class TestGrantConsent:
    @pytest.mark.asyncio()
    async def test_grant_new_consent(self, service, consent_repo, events):
        consent = await service.grant_consent(
            profile_id="P-001",
            purpose="CREDIT_ASSESSMENT",
            granted_by="agent-1",
            duration_days=365,
        )
        assert consent.profile_id == "P-001"
        assert consent.purpose == ConsentPurpose.CREDIT_ASSESSMENT
        assert consent.status == ConsentStatus.GRANTED
        assert consent.version == 1
        # Persisted
        stored = await consent_repo.find_consent_by_id(consent.consent_id)
        assert stored is not None
        # Event published
        assert len(events.events) >= 1
        assert events.events[-1].event_type == "consent.granted"

    @pytest.mark.asyncio()
    async def test_renew_existing_consent(self, service, consent_repo):
        c1 = await service.grant_consent("P-001", "RISK_SCORING", "a-1", 365)
        c2 = await service.grant_consent("P-001", "RISK_SCORING", "a-1", 180)
        # Should be same consent, renewed
        assert c2.consent_id == c1.consent_id
        assert c2.version == 2
        assert c2.status == ConsentStatus.GRANTED

    @pytest.mark.asyncio()
    async def test_grant_different_purposes(self, service, consent_repo):
        c1 = await service.grant_consent("P-001", "CREDIT_ASSESSMENT")
        c2 = await service.grant_consent("P-001", "RISK_SCORING")
        assert c1.consent_id != c2.consent_id
        consents = await consent_repo.find_consents_by_profile("P-001")
        assert len(consents) == 2

    @pytest.mark.asyncio()
    async def test_grant_invalid_purpose_raises(self, service):
        with pytest.raises(ValueError, match="Invalid purpose"):
            await service.grant_consent("P-001", "BOGUS")

    @pytest.mark.asyncio()
    async def test_grant_empty_profile_raises(self, service):
        with pytest.raises(ValueError, match="profile_id"):
            await service.grant_consent("", "CREDIT_ASSESSMENT")


class TestRevokeConsent:
    @pytest.mark.asyncio()
    async def test_revoke_consent(self, service, events):
        consent = await service.grant_consent("P-001", "CREDIT_ASSESSMENT", "a-1")
        revoked = await service.revoke_consent(consent.consent_id, "no longer needed", "a-1")
        assert revoked.status == ConsentStatus.REVOKED
        assert revoked.revocation_reason == "no longer needed"
        # Event published
        revoke_events = [e for e in events.events if e.event_type == "consent.revoked"]
        assert len(revoke_events) == 1

    @pytest.mark.asyncio()
    async def test_revoke_nonexistent_raises(self, service):
        with pytest.raises(ValueError, match="not found"):
            await service.revoke_consent("nonexistent-id")

    @pytest.mark.asyncio()
    async def test_revoke_already_revoked_raises(self, service):
        consent = await service.grant_consent("P-001", "MARKETING")
        await service.revoke_consent(consent.consent_id)
        with pytest.raises(ValueError, match="already revoked"):
            await service.revoke_consent(consent.consent_id)


class TestCheckConsent:
    @pytest.mark.asyncio()
    async def test_active_consent_returns_true(self, service):
        await service.grant_consent("P-001", "CREDIT_ASSESSMENT")
        result = await service.check_consent("P-001", "CREDIT_ASSESSMENT")
        assert result is True

    @pytest.mark.asyncio()
    async def test_no_consent_returns_false(self, service):
        result = await service.check_consent("P-001", "CREDIT_ASSESSMENT")
        assert result is False

    @pytest.mark.asyncio()
    async def test_revoked_consent_returns_false(self, service):
        consent = await service.grant_consent("P-001", "MARKETING")
        await service.revoke_consent(consent.consent_id)
        result = await service.check_consent("P-001", "MARKETING")
        assert result is False


class TestGetConsent:
    @pytest.mark.asyncio()
    async def test_get_existing(self, service):
        consent = await service.grant_consent("P-001", "CREDIT_ASSESSMENT")
        result = await service.get_consent(consent.consent_id)
        assert result is not None
        assert result.consent_id == consent.consent_id

    @pytest.mark.asyncio()
    async def test_get_nonexistent(self, service):
        result = await service.get_consent("nonexistent")
        assert result is None

    @pytest.mark.asyncio()
    async def test_get_profile_consents(self, service):
        await service.grant_consent("P-001", "CREDIT_ASSESSMENT")
        await service.grant_consent("P-001", "RISK_SCORING")
        await service.grant_consent("P-002", "MARKETING")
        consents = await service.get_profile_consents("P-001")
        assert len(consents) == 2


# ---------------------------------------------------------------------------
# Audit Logging Tests
# ---------------------------------------------------------------------------
class TestAuditLogging:
    @pytest.mark.asyncio()
    async def test_log_data_access(self, service, audit_repo):
        entry = await service.log_data_access(
            actor_id="agent-1",
            resource_type="profile",
            resource_id="P-001",
            profile_id="P-001",
            details={"fields": ["name", "phone"]},
            ip_address="10.0.0.1",
        )
        assert entry.action == AuditAction.DATA_ACCESS
        assert entry.actor_id == "agent-1"
        # Persisted
        entries = await audit_repo.find_entries_by_profile("P-001", limit=10)
        assert len(entries) >= 1

    @pytest.mark.asyncio()
    async def test_consent_operations_logged(self, service, audit_repo):
        consent = await service.grant_consent("P-001", "CREDIT_ASSESSMENT", "a-1")
        await service.revoke_consent(consent.consent_id, "test", "a-1")
        entries = await audit_repo.find_entries_by_profile("P-001", limit=50)
        actions = [e.action for e in entries]
        assert AuditAction.CONSENT_GRANTED in actions
        assert AuditAction.CONSENT_REVOKED in actions

    @pytest.mark.asyncio()
    async def test_get_audit_log(self, service, audit_repo):
        await service.log_data_access("a-1", "profile", "P-001", "P-001")
        await service.log_data_access("a-2", "loan", "L-001", "P-001")
        log = await service.get_audit_log("P-001", limit=10)
        assert len(log) >= 2


# ---------------------------------------------------------------------------
# Data Lineage Tests
# ---------------------------------------------------------------------------
class TestDataLineage:
    @pytest.mark.asyncio()
    async def test_record_data_access(self, service, lineage_repo):
        record = await service.record_data_access(
            profile_id="P-001",
            data_category="FINANCIAL",
            source_service="profile_service",
            target_service="risk_assessment",
            action="read",
            fields_accessed=["income", "expenses"],
            purpose="credit scoring",
        )
        assert record.data_category == DataCategory.FINANCIAL
        assert record.source_service == "profile_service"
        assert record.target_service == "risk_assessment"
        # Persisted
        records = await lineage_repo.find_records_by_profile("P-001")
        assert len(records) == 1

    @pytest.mark.asyncio()
    async def test_get_lineage_all(self, service):
        await service.record_data_access(
            "P-001", "FINANCIAL", "a", "b", "read",
        )
        await service.record_data_access(
            "P-001", "PERSONAL_IDENTITY", "c", "d", "read",
        )
        records = await service.get_data_lineage("P-001")
        assert len(records) == 2

    @pytest.mark.asyncio()
    async def test_get_lineage_by_category(self, service):
        await service.record_data_access(
            "P-001", "FINANCIAL", "a", "b", "read",
        )
        await service.record_data_access(
            "P-001", "PERSONAL_IDENTITY", "c", "d", "read",
        )
        records = await service.get_data_lineage("P-001", category="FINANCIAL")
        assert len(records) == 1
        assert records[0].data_category == DataCategory.FINANCIAL

    @pytest.mark.asyncio()
    async def test_lineage_invalid_profile_raises(self, service):
        with pytest.raises(ValueError, match="profile_id"):
            await service.record_data_access(
                "", "FINANCIAL", "a", "b", "read",
            )

    @pytest.mark.asyncio()
    async def test_lineage_invalid_category_raises(self, service):
        with pytest.raises(ValueError, match="Invalid category"):
            await service.get_data_lineage("P-001", category="BOGUS")


# ---------------------------------------------------------------------------
# Data Usage Summary Tests
# ---------------------------------------------------------------------------
class TestDataUsageSummary:
    @pytest.mark.asyncio()
    async def test_empty_summary(self, service):
        summary = await service.get_data_usage_summary("P-001")
        assert summary.profile_id == "P-001"
        assert summary.total_data_accesses == 0
        assert summary.active_consents == []

    @pytest.mark.asyncio()
    async def test_full_summary(self, service):
        await service.grant_consent("P-001", "CREDIT_ASSESSMENT")
        await service.grant_consent("P-001", "RISK_SCORING")
        await service.record_data_access(
            "P-001", "FINANCIAL", "profile", "risk", "read",
        )
        await service.record_data_access(
            "P-001", "PERSONAL_IDENTITY", "profile", "guidance", "read",
        )
        summary = await service.get_data_usage_summary("P-001")
        assert len(summary.active_consents) == 2
        assert summary.total_data_accesses == 2
        assert "risk" in summary.services_with_access
        assert "guidance" in summary.services_with_access
        assert DataCategory.FINANCIAL in summary.data_categories_stored


# ---------------------------------------------------------------------------
# Retention Policy Tests
# ---------------------------------------------------------------------------
class TestRetentionPolicies:
    @pytest.mark.asyncio()
    async def test_initialize_default_policies(self, service, retention_repo):
        policies = await service.initialize_default_policies()
        assert len(policies) == 7
        # Persisted
        stored = await retention_repo.find_all_policies()
        assert len(stored) == 7

    @pytest.mark.asyncio()
    async def test_initialize_idempotent(self, service):
        p1 = await service.initialize_default_policies()
        p2 = await service.initialize_default_policies()
        assert len(p1) == len(p2)
        # Same policies returned, not doubled
        assert {p.policy_id for p in p1} == {p.policy_id for p in p2}

    @pytest.mark.asyncio()
    async def test_get_retention_policies(self, service):
        await service.initialize_default_policies()
        policies = await service.get_retention_policies()
        assert len(policies) == 7

    @pytest.mark.asyncio()
    async def test_check_retention_expired(self, service):
        await service.initialize_default_policies()
        old_date = (datetime.now(UTC) - timedelta(days=400)).isoformat()
        result = await service.check_retention_expired("P-001", "ALERT", old_date)
        assert result["expired"] is True
        assert result["action"] == "DELETE"

    @pytest.mark.asyncio()
    async def test_check_retention_not_expired(self, service):
        await service.initialize_default_policies()
        recent_date = datetime.now(UTC).isoformat()
        result = await service.check_retention_expired("P-001", "ALERT", recent_date)
        assert result["expired"] is False

    @pytest.mark.asyncio()
    async def test_check_retention_no_policy(self, service):
        # No policies initialized
        result = await service.check_retention_expired("P-001", "ALERT", datetime.now(UTC).isoformat())
        assert result["expired"] is False
        assert "No retention policy" in result["reason"]
