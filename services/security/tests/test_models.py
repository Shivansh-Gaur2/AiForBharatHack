"""Unit tests for Security & Privacy domain models.

Tests pure business logic — no I/O, no infrastructure.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from services.security.app.domain.models import (
    AuditAction,
    Consent,
    ConsentPurpose,
    ConsentStatus,
    DataCategory,
    DataLineageRecord,
    RetentionAction,
    RetentionPolicy,
    build_data_usage_summary,
    build_default_retention_policies,
    create_audit_entry,
    create_consent,
    create_lineage_record,
    generate_id,
)


# ---------------------------------------------------------------------------
# generate_id
# ---------------------------------------------------------------------------
class TestGenerateId:
    def test_returns_string(self):
        assert isinstance(generate_id(), str)

    def test_unique(self):
        ids = {generate_id() for _ in range(100)}
        assert len(ids) == 100


# ---------------------------------------------------------------------------
# ConsentPurpose & ConsentStatus enums
# ---------------------------------------------------------------------------
class TestConsentPurpose:
    def test_all_values(self):
        assert len(ConsentPurpose) == 8

    def test_members(self):
        assert ConsentPurpose.CREDIT_ASSESSMENT == "CREDIT_ASSESSMENT"
        assert ConsentPurpose.GOVERNMENT_SCHEME_MATCHING == "GOVERNMENT_SCHEME_MATCHING"

    def test_str_enum(self):
        assert isinstance(ConsentPurpose.RISK_SCORING, str)


class TestConsentStatus:
    def test_all_values(self):
        assert len(ConsentStatus) == 3
        assert "GRANTED" in ConsentStatus.__members__
        assert "REVOKED" in ConsentStatus.__members__
        assert "EXPIRED" in ConsentStatus.__members__


# ---------------------------------------------------------------------------
# AuditAction
# ---------------------------------------------------------------------------
class TestAuditAction:
    def test_all_values(self):
        assert len(AuditAction) == 12

    def test_key_actions(self):
        assert AuditAction.DATA_ACCESS == "DATA_ACCESS"
        assert AuditAction.CONSENT_GRANTED == "CONSENT_GRANTED"
        assert AuditAction.RETENTION_PURGE == "RETENTION_PURGE"


# ---------------------------------------------------------------------------
# DataCategory
# ---------------------------------------------------------------------------
class TestDataCategory:
    def test_all_values(self):
        assert len(DataCategory) == 7

    def test_key_categories(self):
        assert DataCategory.PERSONAL_IDENTITY == "PERSONAL_IDENTITY"
        assert DataCategory.FINANCIAL == "FINANCIAL"
        assert DataCategory.LOCATION == "LOCATION"


# ---------------------------------------------------------------------------
# Consent Aggregate
# ---------------------------------------------------------------------------
class TestConsent:
    @pytest.fixture()
    def consent(self) -> Consent:
        return create_consent(
            profile_id="P-001",
            purpose=ConsentPurpose.CREDIT_ASSESSMENT,
            granted_by="agent-1",
            duration_days=365,
        )

    def test_create_consent_factory(self, consent: Consent):
        assert consent.profile_id == "P-001"
        assert consent.purpose == ConsentPurpose.CREDIT_ASSESSMENT
        assert consent.status == ConsentStatus.GRANTED
        assert consent.granted_by == "agent-1"
        assert consent.version == 1
        assert consent.revoked_at is None
        assert consent.expires_at > consent.granted_at

    def test_is_active_when_granted(self, consent: Consent):
        assert consent.is_active() is True

    def test_is_active_when_expired(self):
        consent = Consent(
            consent_id="c-1",
            profile_id="P-001",
            purpose=ConsentPurpose.RISK_SCORING,
            status=ConsentStatus.GRANTED,
            granted_at=datetime.now(UTC) - timedelta(days=400),
            expires_at=datetime.now(UTC) - timedelta(days=35),
        )
        assert consent.is_active() is False

    def test_is_active_when_revoked(self, consent: Consent):
        consent.revoke("no longer needed")
        assert consent.is_active() is False

    def test_revoke(self, consent: Consent):
        consent.revoke("privacy concern")
        assert consent.status == ConsentStatus.REVOKED
        assert consent.revoked_at is not None
        assert consent.revocation_reason == "privacy concern"

    def test_revoke_already_revoked_raises(self, consent: Consent):
        consent.revoke()
        with pytest.raises(ValueError, match="already revoked"):
            consent.revoke()

    def test_expire(self, consent: Consent):
        consent.expire()
        assert consent.status == ConsentStatus.EXPIRED

    def test_expire_revoked_does_not_change(self, consent: Consent):
        consent.revoke()
        consent.expire()
        assert consent.status == ConsentStatus.REVOKED  # stays revoked

    def test_renew(self, consent: Consent):
        consent.revoke("temp")
        consent.renew(duration_days=180)
        assert consent.status == ConsentStatus.GRANTED
        assert consent.version == 2
        assert consent.revoked_at is None
        assert consent.revocation_reason == ""
        assert consent.is_active() is True

    def test_renew_updates_expiry(self, consent: Consent):
        original_expires = consent.expires_at
        consent.renew(duration_days=90)
        assert consent.expires_at != original_expires
        assert consent.version == 2

    def test_consent_duration(self):
        consent = create_consent("P-002", ConsentPurpose.MARKETING, duration_days=30)
        delta = consent.expires_at - consent.granted_at
        assert 29 <= delta.days <= 30


# ---------------------------------------------------------------------------
# AuditEntry
# ---------------------------------------------------------------------------
class TestAuditEntry:
    def test_create_audit_entry_factory(self):
        entry = create_audit_entry(
            actor_id="agent-1",
            action=AuditAction.DATA_ACCESS,
            resource_type="profile",
            resource_id="P-001",
            profile_id="P-001",
            details={"fields": ["name", "phone"]},
            ip_address="10.0.0.1",
        )
        assert entry.actor_id == "agent-1"
        assert entry.action == AuditAction.DATA_ACCESS
        assert entry.resource_type == "profile"
        assert entry.resource_id == "P-001"
        assert entry.profile_id == "P-001"
        assert entry.details == {"fields": ["name", "phone"]}
        assert entry.ip_address == "10.0.0.1"
        assert entry.success is True
        assert isinstance(entry.entry_id, str)
        assert isinstance(entry.timestamp, datetime)

    def test_defaults(self):
        entry = create_audit_entry(
            actor_id="sys",
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="session",
            resource_id="s-1",
            profile_id="P-001",
        )
        assert entry.details == {}
        assert entry.ip_address == ""
        assert entry.user_agent == ""

    def test_failed_action(self):
        entry = create_audit_entry(
            actor_id="attacker",
            action=AuditAction.UNAUTHORIZED_ACCESS_ATTEMPT,
            resource_type="admin_panel",
            resource_id="admin-1",
            profile_id="",
            success=False,
        )
        assert entry.success is False


# ---------------------------------------------------------------------------
# DataLineageRecord
# ---------------------------------------------------------------------------
class TestDataLineageRecord:
    def test_create_lineage_record(self):
        record = create_lineage_record(
            profile_id="P-001",
            data_category=DataCategory.FINANCIAL,
            source_service="profile_service",
            target_service="risk_assessment",
            action="read",
            fields_accessed=["income", "expenses"],
            purpose="credit scoring",
            consent_id="c-1",
            actor_id="agent-1",
        )
        assert record.profile_id == "P-001"
        assert record.data_category == DataCategory.FINANCIAL
        assert record.source_service == "profile_service"
        assert record.target_service == "risk_assessment"
        assert record.action == "read"
        assert record.fields_accessed == ["income", "expenses"]
        assert record.purpose == "credit scoring"
        assert record.consent_id == "c-1"
        assert isinstance(record.record_id, str)

    def test_defaults(self):
        record = create_lineage_record(
            profile_id="P-001",
            data_category=DataCategory.ALERT,
            source_service="early_warning",
            target_service="guidance",
            action="transform",
        )
        assert record.fields_accessed == []
        assert record.purpose == ""
        assert record.consent_id == ""
        assert record.actor_id == ""


# ---------------------------------------------------------------------------
# RetentionPolicy
# ---------------------------------------------------------------------------
class TestRetentionPolicy:
    @pytest.fixture()
    def policy(self) -> RetentionPolicy:
        return RetentionPolicy(
            policy_id="rp-1",
            data_category=DataCategory.PERSONAL_IDENTITY,
            retention_days=2555,
            action=RetentionAction.DELETE,
            description="KYC data",
        )

    def test_not_expired(self, policy: RetentionPolicy):
        recent = datetime.now(UTC) - timedelta(days=100)
        assert policy.is_expired(recent) is False

    def test_expired(self, policy: RetentionPolicy):
        old = datetime.now(UTC) - timedelta(days=3000)
        assert policy.is_expired(old) is True

    def test_boundary_not_expired(self, policy: RetentionPolicy):
        boundary = datetime.now(UTC) - timedelta(days=2555)
        assert policy.is_expired(boundary) is False

    def test_boundary_expired(self, policy: RetentionPolicy):
        boundary = datetime.now(UTC) - timedelta(days=2556)
        assert policy.is_expired(boundary) is True


class TestBuildDefaultRetentionPolicies:
    def test_creates_seven_policies(self):
        policies = build_default_retention_policies()
        assert len(policies) == 7

    def test_covers_all_categories(self):
        policies = build_default_retention_policies()
        categories = {p.data_category for p in policies}
        assert categories == set(DataCategory)

    def test_unique_ids(self):
        policies = build_default_retention_policies()
        ids = {p.policy_id for p in policies}
        assert len(ids) == 7

    def test_identity_retention_seven_years(self):
        policies = build_default_retention_policies()
        identity_policy = next(
            p for p in policies if p.data_category == DataCategory.PERSONAL_IDENTITY
        )
        assert identity_policy.retention_days == 2555
        assert identity_policy.action == RetentionAction.DELETE

    def test_financial_retention_anonymize(self):
        policies = build_default_retention_policies()
        fin_policy = next(
            p for p in policies if p.data_category == DataCategory.FINANCIAL
        )
        assert fin_policy.retention_days == 2555
        assert fin_policy.action == RetentionAction.ANONYMIZE

    def test_alert_retention_one_year(self):
        policies = build_default_retention_policies()
        alert_policy = next(
            p for p in policies if p.data_category == DataCategory.ALERT
        )
        assert alert_policy.retention_days == 365
        assert alert_policy.action == RetentionAction.DELETE


# ---------------------------------------------------------------------------
# DataUsageSummary
# ---------------------------------------------------------------------------
class TestBuildDataUsageSummary:
    def test_empty_data(self):
        summary = build_data_usage_summary("P-001", [], [], [])
        assert summary.profile_id == "P-001"
        assert summary.active_consents == []
        assert summary.total_data_accesses == 0
        assert summary.services_with_access == []
        assert summary.data_categories_stored == []
        assert summary.last_accessed_at is None
        assert summary.pending_deletion_categories == []

    def test_with_active_consents(self):
        c1 = create_consent("P-001", ConsentPurpose.CREDIT_ASSESSMENT)
        c2 = create_consent("P-001", ConsentPurpose.RISK_SCORING)
        c2.revoke()
        summary = build_data_usage_summary("P-001", [c1, c2], [], [])
        assert len(summary.active_consents) == 1
        assert summary.active_consents[0].purpose == ConsentPurpose.CREDIT_ASSESSMENT

    def test_services_and_categories(self):
        r1 = create_lineage_record(
            "P-001", DataCategory.FINANCIAL, "profile", "risk", "read",
        )
        r2 = create_lineage_record(
            "P-001", DataCategory.PERSONAL_IDENTITY, "profile", "guidance", "read",
        )
        summary = build_data_usage_summary("P-001", [], [r1, r2], [])
        assert "guidance" in summary.services_with_access
        assert "risk" in summary.services_with_access
        assert DataCategory.FINANCIAL in summary.data_categories_stored

    def test_last_accessed_at(self):
        r1 = create_lineage_record(
            "P-001", DataCategory.FINANCIAL, "a", "b", "read",
        )
        summary = build_data_usage_summary("P-001", [], [r1], [])
        assert summary.last_accessed_at is not None

    def test_pending_deletion(self):
        old_record = DataLineageRecord(
            record_id="r-1",
            timestamp=datetime.now(UTC) - timedelta(days=400),
            profile_id="P-001",
            data_category=DataCategory.ALERT,
            source_service="early_warning",
            target_service="guidance",
            action="read",
        )
        policy = RetentionPolicy(
            policy_id="rp-1",
            data_category=DataCategory.ALERT,
            retention_days=365,
            action=RetentionAction.DELETE,
        )
        summary = build_data_usage_summary("P-001", [], [old_record], [policy])
        assert DataCategory.ALERT in summary.pending_deletion_categories

    def test_no_pending_deletion_when_within_retention(self):
        recent_record = create_lineage_record(
            "P-001", DataCategory.ALERT, "a", "b", "read",
        )
        policy = RetentionPolicy(
            policy_id="rp-1",
            data_category=DataCategory.ALERT,
            retention_days=365,
            action=RetentionAction.DELETE,
        )
        summary = build_data_usage_summary("P-001", [], [recent_record], [policy])
        assert summary.pending_deletion_categories == []
