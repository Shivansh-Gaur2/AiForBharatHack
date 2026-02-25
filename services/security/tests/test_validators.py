"""Unit tests for Security & Privacy validators."""

from __future__ import annotations

import pytest

from services.security.app.domain.validators import (
    validate_audit_query,
    validate_consent_request,
    validate_lineage_query,
)


# ---------------------------------------------------------------------------
# validate_consent_request
# ---------------------------------------------------------------------------
class TestValidateConsentRequest:
    def test_valid_request(self):
        validate_consent_request("P-001", "CREDIT_ASSESSMENT", 365)

    def test_all_valid_purposes(self):
        purposes = [
            "CREDIT_ASSESSMENT", "RISK_SCORING", "DATA_SHARING_LENDER",
            "DATA_SHARING_CREDIT_BUREAU", "MARKETING", "RESEARCH_ANONYMIZED",
            "GOVERNMENT_SCHEME_MATCHING", "EARLY_WARNING_ALERTS",
        ]
        for p in purposes:
            validate_consent_request("P-001", p, 365)

    def test_empty_profile_id(self):
        with pytest.raises(ValueError, match="profile_id is required"):
            validate_consent_request("", "CREDIT_ASSESSMENT", 365)

    def test_whitespace_only_profile_id(self):
        with pytest.raises(ValueError, match="profile_id is required"):
            validate_consent_request("   ", "CREDIT_ASSESSMENT", 365)

    def test_invalid_purpose(self):
        with pytest.raises(ValueError, match="Invalid purpose"):
            validate_consent_request("P-001", "INVALID_PURPOSE", 365)

    def test_duration_too_short(self):
        with pytest.raises(ValueError, match="at least 1"):
            validate_consent_request("P-001", "CREDIT_ASSESSMENT", 0)

    def test_duration_negative(self):
        with pytest.raises(ValueError, match="at least 1"):
            validate_consent_request("P-001", "CREDIT_ASSESSMENT", -10)

    def test_duration_too_long(self):
        with pytest.raises(ValueError, match="cannot exceed 3650"):
            validate_consent_request("P-001", "CREDIT_ASSESSMENT", 3651)

    def test_duration_boundary_min(self):
        validate_consent_request("P-001", "CREDIT_ASSESSMENT", 1)

    def test_duration_boundary_max(self):
        validate_consent_request("P-001", "CREDIT_ASSESSMENT", 3650)

    def test_multiple_errors(self):
        with pytest.raises(ValueError) as exc_info:
            validate_consent_request("", "INVALID", 0)
        msg = str(exc_info.value)
        assert "profile_id" in msg
        assert "Invalid purpose" in msg
        assert "at least 1" in msg


# ---------------------------------------------------------------------------
# validate_audit_query
# ---------------------------------------------------------------------------
class TestValidateAuditQuery:
    def test_valid_with_profile_id(self):
        validate_audit_query("P-001", None, 50)

    def test_valid_with_actor_id(self):
        validate_audit_query(None, "agent-1", 50)

    def test_valid_with_both(self):
        validate_audit_query("P-001", "agent-1", 50)

    def test_neither_raises(self):
        with pytest.raises(ValueError, match="Either profile_id or actor_id"):
            validate_audit_query(None, None, 50)

    def test_empty_strings_raises(self):
        with pytest.raises(ValueError, match="Either profile_id or actor_id"):
            validate_audit_query("", "", 50)

    def test_limit_too_low(self):
        with pytest.raises(ValueError, match="between 1 and 1000"):
            validate_audit_query("P-001", None, 0)

    def test_limit_too_high(self):
        with pytest.raises(ValueError, match="between 1 and 1000"):
            validate_audit_query("P-001", None, 1001)

    def test_limit_boundary_min(self):
        validate_audit_query("P-001", None, 1)

    def test_limit_boundary_max(self):
        validate_audit_query("P-001", None, 1000)


# ---------------------------------------------------------------------------
# validate_lineage_query
# ---------------------------------------------------------------------------
class TestValidateLineageQuery:
    def test_valid_without_category(self):
        validate_lineage_query("P-001", None)

    def test_valid_with_category(self):
        validate_lineage_query("P-001", "FINANCIAL")

    def test_all_valid_categories(self):
        categories = [
            "PERSONAL_IDENTITY", "FINANCIAL", "RISK_ASSESSMENT",
            "CASH_FLOW", "GUIDANCE", "ALERT", "LOCATION",
        ]
        for cat in categories:
            validate_lineage_query("P-001", cat)

    def test_empty_profile_id(self):
        with pytest.raises(ValueError, match="profile_id is required"):
            validate_lineage_query("", None)

    def test_whitespace_only_profile_id(self):
        with pytest.raises(ValueError, match="profile_id is required"):
            validate_lineage_query("   ", None)

    def test_invalid_category(self):
        with pytest.raises(ValueError, match="Invalid category"):
            validate_lineage_query("P-001", "BOGUS")
