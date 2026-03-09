"""End-to-end tests for the Guidance & Intelligence service.

Hits the running service on http://127.0.0.1:8006.
Run after: uvicorn services.guidance.app.main:app --host 127.0.0.1 --port 8006
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e  # requires running service — skipped by default

BASE = "http://127.0.0.1:8006/api/v1/guidance"


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE, timeout=15)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SAMPLE_PROJECTIONS = [
    {"month": m, "year": 2026, "inflow": 15000.0, "outflow": 10000.0}
    for m in range(1, 13)
]


def _create_direct_guidance(client, *, profile_id: str = "e2e-prof-1", **overrides) -> dict:
    payload = {
        "profile_id": profile_id,
        "loan_purpose": "CROP_CULTIVATION",
        "projections": SAMPLE_PROJECTIONS,
        "risk_category": "MEDIUM",
        "risk_score": 450,
        "dti_ratio": 0.35,
        "existing_obligations": 2000.0,
        "tenure_months": 12,
        "interest_rate_annual": 9.0,
        **overrides,
    }
    resp = client.post("/generate/direct", json=payload)
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    return resp.json()


# ===========================================================================
# Health Check
# ===========================================================================
def test_health():
    r = httpx.get("http://127.0.0.1:8006/health")
    assert r.status_code == 200
    assert r.json()["service"] == "guidance"


# ===========================================================================
# Direct Guidance Generation
# ===========================================================================
class TestDirectGuidance:
    def test_generate_direct_guidance(self, client):
        data = _create_direct_guidance(client)
        assert data["profile_id"] == "e2e-prof-1"
        assert data["loan_purpose"] == "CROP_CULTIVATION"
        assert data["status"] == "ACTIVE"
        assert data["recommended_amount"]["min_amount"] > 0
        assert data["recommended_amount"]["max_amount"] >= data["recommended_amount"]["min_amount"]
        assert data["recommended_amount"]["currency"] == "INR"

    def test_guidance_has_timing(self, client):
        data = _create_direct_guidance(client, profile_id="e2e-timing-check")
        timing = data["optimal_timing"]
        assert timing["start_month"] >= 1
        assert timing["start_year"] >= 2026
        assert timing["suitability"] in ("OPTIMAL", "GOOD", "ACCEPTABLE", "POOR")
        assert len(timing["reason"]) > 0

    def test_guidance_has_terms(self, client):
        data = _create_direct_guidance(client, profile_id="e2e-terms-check")
        terms = data["suggested_terms"]
        assert terms["tenure_months"] > 0
        assert terms["interest_rate_max_pct"] > 0
        assert terms["emi_amount"] > 0
        assert terms["total_repayment"] > terms["emi_amount"]
        assert len(terms["source_recommendation"]) > 0

    def test_guidance_has_risk_summary(self, client):
        data = _create_direct_guidance(client, profile_id="e2e-risk-check")
        risk = data["risk_summary"]
        assert risk["risk_category"] == "MEDIUM"
        assert risk["risk_score"] == 450
        assert risk["dti_ratio"] == 0.35
        assert len(risk["key_risk_factors"]) > 0

    def test_guidance_has_alternatives(self, client):
        data = _create_direct_guidance(client, profile_id="e2e-alt-check")
        alts = data["alternative_options"]
        assert len(alts) >= 1
        for alt in alts:
            assert alt["option_type"]
            assert alt["description"]
            assert len(alt["advantages"]) > 0

    def test_guidance_has_explanation(self, client):
        data = _create_direct_guidance(client, profile_id="e2e-explain-check")
        expl = data["explanation"]
        assert len(expl["summary"]) > 0
        assert len(expl["reasoning_steps"]) >= 3
        assert expl["confidence"] in ("HIGH", "MEDIUM", "LOW")
        for step in expl["reasoning_steps"]:
            assert step["step_number"] > 0
            assert step["factor"]
            assert step["observation"]

    def test_high_risk_reduces_amount(self, client):
        low_risk = _create_direct_guidance(
            client, profile_id="e2e-low-risk", risk_category="LOW", risk_score=200,
        )
        high_risk = _create_direct_guidance(
            client, profile_id="e2e-high-risk", risk_category="HIGH", risk_score=700,
        )
        assert low_risk["recommended_amount"]["max_amount"] > high_risk["recommended_amount"]["max_amount"]

    def test_requested_amount_capped(self, client):
        data = _create_direct_guidance(
            client, profile_id="e2e-cap", requested_amount=10_000_000,
        )
        assert data["requested_amount"] == 10_000_000
        assert data["recommended_amount"]["max_amount"] < 10_000_000

    def test_various_loan_purposes(self, client):
        for purpose in ("LIVESTOCK_PURCHASE", "EQUIPMENT_PURCHASE", "IRRIGATION"):
            data = _create_direct_guidance(
                client, profile_id=f"e2e-purpose-{purpose.lower()}", loan_purpose=purpose,
            )
            assert data["loan_purpose"] == purpose


# ===========================================================================
# Guidance Retrieval
# ===========================================================================
class TestGuidanceRetrieval:
    def test_get_guidance_by_id(self, client):
        created = _create_direct_guidance(client, profile_id="e2e-get-by-id")
        guidance_id = created["guidance_id"]
        resp = client.get(f"/{guidance_id}")
        assert resp.status_code == 200
        assert resp.json()["guidance_id"] == guidance_id

    def test_get_guidance_not_found(self, client):
        resp = client.get("/nonexistent-guidance-id")
        assert resp.status_code == 404

    def test_explain_guidance(self, client):
        created = _create_direct_guidance(client, profile_id="e2e-explain")
        guidance_id = created["guidance_id"]
        resp = client.get(f"/{guidance_id}/explain")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["summary"]) > 0
        assert len(data["reasoning_steps"]) > 0
        assert data["confidence"] in ("HIGH", "MEDIUM", "LOW")

    def test_explain_not_found(self, client):
        resp = client.get("/nonexistent-id/explain")
        assert resp.status_code == 404


# ===========================================================================
# Guidance Lifecycle
# ===========================================================================
class TestGuidanceLifecycle:
    def test_supersede_guidance(self, client):
        created = _create_direct_guidance(client, profile_id="e2e-supersede")
        guidance_id = created["guidance_id"]
        resp = client.post(f"/{guidance_id}/supersede")
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUPERSEDED"

    def test_expire_guidance(self, client):
        created = _create_direct_guidance(client, profile_id="e2e-expire")
        guidance_id = created["guidance_id"]
        resp = client.post(f"/{guidance_id}/expire")
        assert resp.status_code == 200
        assert resp.json()["status"] == "EXPIRED"

    def test_supersede_nonexistent(self, client):
        resp = client.post("/nonexistent-id/supersede")
        assert resp.status_code == 404

    def test_expire_nonexistent(self, client):
        resp = client.post("/nonexistent-id/expire")
        assert resp.status_code == 404

    def test_full_lifecycle(self, client):
        # Create guidance
        created = _create_direct_guidance(client, profile_id="e2e-full-lc")
        guidance_id = created["guidance_id"]
        assert created["status"] == "ACTIVE"

        # Retrieve it
        resp = client.get(f"/{guidance_id}")
        assert resp.status_code == 200

        # Get explanation
        resp = client.get(f"/{guidance_id}/explain")
        assert resp.status_code == 200

        # Expire it
        resp = client.post(f"/{guidance_id}/expire")
        assert resp.status_code == 200
        assert resp.json()["status"] == "EXPIRED"


# ===========================================================================
# Profile Queries
# ===========================================================================
class TestProfileQueries:
    def test_get_guidance_history(self, client):
        profile_id = "e2e-history-prof"
        for _ in range(3):
            _create_direct_guidance(client, profile_id=profile_id)
        resp = client.get(f"/profile/{profile_id}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 3
        assert len(data["items"]) == data["count"]
        for item in data["items"]:
            assert item["profile_id"] == profile_id

    def test_get_active_guidance(self, client):
        profile_id = "e2e-active-prof"
        # Create two, expire one
        g1 = _create_direct_guidance(client, profile_id=profile_id)
        _create_direct_guidance(client, profile_id=profile_id)
        client.post(f"/{g1['guidance_id']}/expire")

        resp = client.get(f"/profile/{profile_id}/active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        for item in data["items"]:
            assert item["status"] == "ACTIVE"

    def test_history_empty_profile(self, client):
        resp = client.get("/profile/nonexistent-prof/history")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_active_empty_profile(self, client):
        resp = client.get("/profile/nonexistent-prof/active")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


# ===========================================================================
# Cross-Service Guidance (uses stubs)
# ===========================================================================
class TestCrossServiceGuidance:
    def test_generate_cross_service(self, client):
        resp = client.post("/generate", json={
            "profile_id": "e2e-cross-gen",
            "loan_purpose": "CROP_CULTIVATION",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["profile_id"] == "e2e-cross-gen"
        assert data["status"] == "ACTIVE"
        # Stubs return 4500/mo obligations against modest surpluses.
        # System correctly determines limited/zero capacity — that is valid guidance.
        assert data["recommended_amount"]["max_amount"] >= 0
        assert data["recommended_amount"]["currency"] == "INR"
        assert len(data["explanation"]["reasoning_steps"]) >= 3

    def test_timing_cross_service(self, client):
        resp = client.post("/timing", json={
            "profile_id": "e2e-cross-timing",
            "loan_amount": 50000.0,
            "tenure_months": 12,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile_id"] == "e2e-cross-timing"
        timing = data["timing"]
        assert timing["suitability"] in ("OPTIMAL", "GOOD", "ACCEPTABLE", "POOR")

    def test_amount_cross_service(self, client):
        resp = client.post("/amount", json={
            "profile_id": "e2e-cross-amount",
            "tenure_months": 12,
            "interest_rate_annual": 9.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile_id"] == "e2e-cross-amount"
        # Stub obligations (4500/mo) absorb most surplus — 0 is valid
        assert data["recommended_amount"]["min_amount"] >= 0
        assert data["recommended_amount"]["max_amount"] >= data["recommended_amount"]["min_amount"]


# ===========================================================================
# Validation Errors
# ===========================================================================
class TestValidation:
    def test_empty_profile_id(self, client):
        resp = client.post("/generate/direct", json={
            "profile_id": "",
            "loan_purpose": "CROP_CULTIVATION",
            "projections": SAMPLE_PROJECTIONS,
        })
        assert resp.status_code == 422

    def test_missing_projections(self, client):
        resp = client.post("/generate/direct", json={
            "profile_id": "e2e-no-proj",
            "loan_purpose": "CROP_CULTIVATION",
        })
        assert resp.status_code == 422

    def test_invalid_risk_score(self, client):
        resp = client.post("/generate/direct", json={
            "profile_id": "e2e-bad-risk",
            "loan_purpose": "CROP_CULTIVATION",
            "projections": SAMPLE_PROJECTIONS,
            "risk_score": 9999,
        })
        assert resp.status_code == 422

    def test_invalid_dti_ratio(self, client):
        resp = client.post("/generate/direct", json={
            "profile_id": "e2e-bad-dti",
            "loan_purpose": "CROP_CULTIVATION",
            "projections": SAMPLE_PROJECTIONS,
            "dti_ratio": 10.0,
        })
        assert resp.status_code == 422

    def test_empty_cross_service_profile_id(self, client):
        resp = client.post("/generate", json={
            "profile_id": "",
            "loan_purpose": "CROP_CULTIVATION",
        })
        assert resp.status_code == 422
