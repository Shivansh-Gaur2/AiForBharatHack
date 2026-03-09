"""End-to-end tests for the Security & Privacy service.

Hits the running service on http://127.0.0.1:8007.
Run after: uvicorn services.security.app.main:app --host 127.0.0.1 --port 8007
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e  # requires running service — skipped by default

BASE = "http://127.0.0.1:8007/api/v1/security"


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE, timeout=15)


# ===========================================================================
# Health Check
# ===========================================================================
def test_health(client):
    resp = httpx.get("http://127.0.0.1:8007/health", timeout=10)
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "security"
    assert body["status"] == "healthy"


# ===========================================================================
# Consent Management
# ===========================================================================
class TestConsentE2E:
    def test_grant_consent(self, client):
        resp = client.post("/consent", json={
            "profile_id": "e2e-sec-001",
            "purpose": "CREDIT_ASSESSMENT",
            "granted_by": "agent-e2e",
            "duration_days": 180,
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["profile_id"] == "e2e-sec-001"
        assert body["purpose"] == "CREDIT_ASSESSMENT"
        assert body["status"] == "GRANTED"
        assert body["version"] >= 1

    def test_get_consent(self, client):
        # Grant first
        resp = client.post("/consent", json={
            "profile_id": "e2e-sec-002",
            "purpose": "RISK_SCORING",
            "duration_days": 365,
        })
        consent_id = resp.json()["consent_id"]

        # Get it back
        resp = client.get(f"/consent/{consent_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["consent_id"] == consent_id
        assert body["purpose"] == "RISK_SCORING"

    def test_get_profile_consents(self, client):
        profile = "e2e-sec-003"
        client.post("/consent", json={
            "profile_id": profile, "purpose": "CREDIT_ASSESSMENT", "duration_days": 365,
        })
        client.post("/consent", json={
            "profile_id": profile, "purpose": "MARKETING", "duration_days": 90,
        })
        resp = client.get(f"/consent/profile/{profile}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 2

    def test_revoke_consent(self, client):
        resp = client.post("/consent", json={
            "profile_id": "e2e-sec-004",
            "purpose": "MARKETING",
            "duration_days": 365,
        })
        consent_id = resp.json()["consent_id"]

        resp = client.post(f"/consent/{consent_id}/revoke", json={
            "reason": "changed my mind",
            "revoked_by": "borrower-e2e",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "REVOKED"

    def test_check_consent_active(self, client):
        profile = "e2e-sec-005"
        client.post("/consent", json={
            "profile_id": profile, "purpose": "RISK_SCORING", "duration_days": 365,
        })
        resp = client.post("/consent/check", json={
            "profile_id": profile,
            "purpose": "RISK_SCORING",
        })
        assert resp.status_code == 200
        assert resp.json()["has_consent"] is True

    def test_check_consent_not_granted(self, client):
        resp = client.post("/consent/check", json={
            "profile_id": "e2e-sec-never",
            "purpose": "MARKETING",
        })
        assert resp.status_code == 200
        assert resp.json()["has_consent"] is False

    def test_renew_existing_consent(self, client):
        profile = "e2e-sec-006"
        r1 = client.post("/consent", json={
            "profile_id": profile, "purpose": "CREDIT_ASSESSMENT", "duration_days": 30,
        })
        v1 = r1.json()["version"]
        r2 = client.post("/consent", json={
            "profile_id": profile, "purpose": "CREDIT_ASSESSMENT", "duration_days": 365,
        })
        v2 = r2.json()["version"]
        assert v2 == v1 + 1

    def test_consent_invalid_purpose(self, client):
        resp = client.post("/consent", json={
            "profile_id": "e2e-sec-007",
            "purpose": "INVALID_PURPOSE",
            "duration_days": 365,
        })
        assert resp.status_code in (400, 422)

    def test_consent_not_found(self, client):
        resp = client.get("/consent/nonexistent-id-xyz")
        assert resp.status_code == 404


# ===========================================================================
# Audit Logging
# ===========================================================================
class TestAuditE2E:
    def test_log_data_access(self, client):
        resp = client.post("/audit/access", json={
            "actor_id": "agent-e2e",
            "resource_type": "profile",
            "resource_id": "P-e2e-001",
            "profile_id": "e2e-sec-audit-001",
            "details": {"fields": ["name", "phone"]},
            "ip_address": "10.0.0.1",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["action"] == "DATA_ACCESS"
        assert body["actor_id"] == "agent-e2e"

    def test_get_audit_log(self, client):
        profile = "e2e-sec-audit-002"
        client.post("/audit/access", json={
            "actor_id": "a1", "resource_type": "loan", "resource_id": "L-1",
            "profile_id": profile,
        })
        client.post("/audit/access", json={
            "actor_id": "a2", "resource_type": "risk", "resource_id": "R-1",
            "profile_id": profile,
        })
        resp = client.get(f"/audit/profile/{profile}?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 2


# ===========================================================================
# Data Lineage
# ===========================================================================
class TestLineageE2E:
    def test_record_lineage(self, client):
        resp = client.post("/lineage", json={
            "profile_id": "e2e-sec-lin-001",
            "data_category": "FINANCIAL",
            "source_service": "profile_service",
            "target_service": "risk_assessment",
            "action": "read",
            "fields_accessed": ["income", "expenses"],
            "purpose": "credit scoring",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["data_category"] == "FINANCIAL"
        assert body["source_service"] == "profile_service"

    def test_get_lineage(self, client):
        profile = "e2e-sec-lin-002"
        client.post("/lineage", json={
            "profile_id": profile, "data_category": "FINANCIAL",
            "source_service": "a", "target_service": "b", "action": "read",
        })
        client.post("/lineage", json={
            "profile_id": profile, "data_category": "PERSONAL_IDENTITY",
            "source_service": "c", "target_service": "d", "action": "read",
        })
        resp = client.get(f"/lineage/profile/{profile}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 2

    def test_get_lineage_by_category(self, client):
        profile = "e2e-sec-lin-003"
        client.post("/lineage", json={
            "profile_id": profile, "data_category": "FINANCIAL",
            "source_service": "a", "target_service": "b", "action": "read",
        })
        client.post("/lineage", json={
            "profile_id": profile, "data_category": "ALERT",
            "source_service": "c", "target_service": "d", "action": "read",
        })
        resp = client.get(f"/lineage/profile/{profile}?category=FINANCIAL")
        assert resp.status_code == 200
        body = resp.json()
        for record in body["items"]:
            assert record["data_category"] == "FINANCIAL"


# ===========================================================================
# Data Usage Summary
# ===========================================================================
class TestUsageSummaryE2E:
    def test_usage_summary(self, client):
        profile = "e2e-sec-usage-001"
        client.post("/consent", json={
            "profile_id": profile, "purpose": "CREDIT_ASSESSMENT", "duration_days": 365,
        })
        client.post("/lineage", json={
            "profile_id": profile, "data_category": "FINANCIAL",
            "source_service": "profile", "target_service": "risk", "action": "read",
        })
        resp = client.get(f"/usage/{profile}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["profile_id"] == profile
        assert body["active_consent_count"] >= 1
        assert body["total_data_accesses"] >= 1


# ===========================================================================
# Retention Policies
# ===========================================================================
class TestRetentionE2E:
    def test_initialize_policies(self, client):
        resp = client.post("/retention/initialize")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 7

    def test_get_policies(self, client):
        client.post("/retention/initialize")
        resp = client.get("/retention/policies")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 7

    def test_check_retention_not_expired(self, client):
        client.post("/retention/initialize")
        from datetime import UTC, datetime
        resp = client.post("/retention/check", json={
            "profile_id": "e2e-sec-ret-001",
            "data_category": "ALERT",
            "data_created_at": datetime.now(UTC).isoformat(),
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["expired"] is False

    def test_check_retention_expired(self, client):
        client.post("/retention/initialize")
        from datetime import UTC, datetime, timedelta
        old_date = (datetime.now(UTC) - timedelta(days=400)).isoformat()
        resp = client.post("/retention/check", json={
            "profile_id": "e2e-sec-ret-002",
            "data_category": "ALERT",
            "data_created_at": old_date,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["expired"] is True
        assert body["action"] == "DELETE"


# ===========================================================================
# Validation Errors
# ===========================================================================
class TestValidationErrorsE2E:
    def test_consent_empty_profile(self, client):
        resp = client.post("/consent", json={
            "profile_id": "",
            "purpose": "CREDIT_ASSESSMENT",
            "duration_days": 365,
        })
        assert resp.status_code == 422  # Pydantic min_length=1

    def test_consent_duration_too_long(self, client):
        resp = client.post("/consent", json={
            "profile_id": "e2e-sec-val-001",
            "purpose": "CREDIT_ASSESSMENT",
            "duration_days": 5000,
        })
        assert resp.status_code == 422  # Pydantic le=3650

    def test_lineage_invalid_category(self, client):
        resp = client.post("/lineage", json={
            "profile_id": "e2e-sec-val-002",
            "data_category": "BOGUS_CATEGORY",
            "source_service": "a",
            "target_service": "b",
            "action": "read",
        })
        assert resp.status_code in (400, 422)
