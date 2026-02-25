"""Unit tests for Guidance Service validators."""

from __future__ import annotations

import pytest

from services.guidance.app.domain.validators import (
    validate_amount_request,
    validate_direct_guidance_request,
    validate_guidance_request,
    validate_timing_request,
)


# ---------------------------------------------------------------------------
# Guidance Request Validation
# ---------------------------------------------------------------------------
class TestValidateGuidanceRequest:
    def test_valid_request(self):
        validate_guidance_request("prof-1", "CROP_CULTIVATION", 50000, 12, 9.0)

    def test_empty_profile(self):
        with pytest.raises(ValueError, match=r"profile_id must not be empty"):
            validate_guidance_request("", "CROP_CULTIVATION")

    def test_whitespace_profile(self):
        with pytest.raises(ValueError, match=r"profile_id must not be empty"):
            validate_guidance_request("   ", "CROP_CULTIVATION")

    def test_invalid_purpose(self):
        with pytest.raises(ValueError, match=r"Invalid loan_purpose"):
            validate_guidance_request("prof-1", "INVALID_PURPOSE")

    def test_negative_amount(self):
        with pytest.raises(ValueError, match=r"non-negative"):
            validate_guidance_request("prof-1", "CROP_CULTIVATION", requested_amount=-100)

    def test_amount_exceeds_max(self):
        with pytest.raises(ValueError, match=r"exceeds maximum"):
            validate_guidance_request("prof-1", "CROP_CULTIVATION", requested_amount=20_000_000)

    def test_tenure_too_low(self):
        with pytest.raises(ValueError, match=r"at least 1"):
            validate_guidance_request("prof-1", "CROP_CULTIVATION", tenure_months=0)

    def test_tenure_too_high(self):
        with pytest.raises(ValueError, match=r"not exceed 120"):
            validate_guidance_request("prof-1", "CROP_CULTIVATION", tenure_months=200)

    def test_rate_too_high(self):
        with pytest.raises(ValueError, match=r"not exceed 50"):
            validate_guidance_request("prof-1", "CROP_CULTIVATION", interest_rate_annual=60)

    def test_optional_params_none(self):
        validate_guidance_request("prof-1", "MEDICAL")  # No optional params


# ---------------------------------------------------------------------------
# Timing Request Validation
# ---------------------------------------------------------------------------
class TestValidateTimingRequest:
    def test_valid(self):
        validate_timing_request("prof-1", 50000, 12)

    def test_empty_profile(self):
        with pytest.raises(ValueError, match=r"profile_id"):
            validate_timing_request("", 50000)

    def test_zero_amount(self):
        with pytest.raises(ValueError, match=r"positive"):
            validate_timing_request("prof-1", 0)

    def test_negative_amount(self):
        with pytest.raises(ValueError, match=r"positive"):
            validate_timing_request("prof-1", -1000)

    def test_amount_too_large(self):
        with pytest.raises(ValueError, match=r"exceeds maximum"):
            validate_timing_request("prof-1", 20_000_000)


# ---------------------------------------------------------------------------
# Amount Request Validation
# ---------------------------------------------------------------------------
class TestValidateAmountRequest:
    def test_valid(self):
        validate_amount_request("prof-1", 12, 9.0)

    def test_empty_profile(self):
        with pytest.raises(ValueError, match=r"profile_id"):
            validate_amount_request("")

    def test_negative_rate(self):
        with pytest.raises(ValueError, match=r"non-negative"):
            validate_amount_request("prof-1", interest_rate_annual=-1)


# ---------------------------------------------------------------------------
# Direct Guidance Request Validation
# ---------------------------------------------------------------------------
class TestValidateDirectGuidanceRequest:
    def _projections(self):
        return [(m, 2026, 15000, 8000) for m in range(1, 7)]

    def test_valid(self):
        validate_direct_guidance_request(
            "prof-1", "CROP_CULTIVATION", self._projections(), "MEDIUM", 450, 0.3, 3000,
        )

    def test_empty_projections(self):
        with pytest.raises(ValueError, match=r"projections must not be empty"):
            validate_direct_guidance_request(
                "prof-1", "CROP_CULTIVATION", [], "MEDIUM", 450, 0.3, 3000,
            )

    def test_too_many_projections(self):
        projs = [(m % 12 + 1, 2026 + m // 12, 10000, 5000) for m in range(61)]
        with pytest.raises(ValueError, match=r"not exceed 60"):
            validate_direct_guidance_request(
                "prof-1", "CROP_CULTIVATION", projs, "MEDIUM", 450, 0.3, 3000,
            )

    def test_invalid_month(self):
        with pytest.raises(ValueError, match=r"Invalid month"):
            validate_direct_guidance_request(
                "prof-1", "CROP_CULTIVATION", [(13, 2026, 10000, 5000)],
                "MEDIUM", 450, 0.3, 3000,
            )

    def test_invalid_risk_category(self):
        with pytest.raises(ValueError, match=r"Invalid risk_category"):
            validate_direct_guidance_request(
                "prof-1", "CROP_CULTIVATION", self._projections(),
                "EXTREME", 450, 0.3, 3000,
            )

    def test_risk_score_out_of_range(self):
        with pytest.raises(ValueError, match=r"risk_score must be between"):
            validate_direct_guidance_request(
                "prof-1", "CROP_CULTIVATION", self._projections(),
                "MEDIUM", 1500, 0.3, 3000,
            )

    def test_dti_out_of_range(self):
        with pytest.raises(ValueError, match=r"dti_ratio must be between"):
            validate_direct_guidance_request(
                "prof-1", "CROP_CULTIVATION", self._projections(),
                "MEDIUM", 450, 6.0, 3000,
            )

    def test_negative_obligations(self):
        with pytest.raises(ValueError, match=r"non-negative"):
            validate_direct_guidance_request(
                "prof-1", "CROP_CULTIVATION", self._projections(),
                "MEDIUM", 450, 0.3, -100,
            )

    def test_negative_inflow(self):
        with pytest.raises(ValueError, match=r"non-negative"):
            validate_direct_guidance_request(
                "prof-1", "CROP_CULTIVATION", [(1, 2026, -5000, 3000)],
                "MEDIUM", 450, 0.3, 0,
            )
