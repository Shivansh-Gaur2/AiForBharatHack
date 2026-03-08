"""End-to-end API tests for Loan Tracker and Risk Assessment services."""

import json
import sys

import httpx

LOAN_BASE = "http://localhost:8002/api/v1/loans"
RISK_BASE = "http://localhost:8003/api/v1/risk"

passed = 0
failed = 0


def test(name, func):
    global passed, failed
    try:
        func()
        print(f"  PASS: {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {name} — {e}")
        failed += 1


def main() -> None:
    # ===========================================================================
    # LOAN TRACKER SERVICE TESTS
    # ===========================================================================
    print("\n=== LOAN TRACKER SERVICE ===\n")

    # Health check
    def test_loan_health():
        r = httpx.get("http://localhost:8002/health", timeout=5)
        assert r.status_code == 200
        assert r.json()["service"] == "loan-tracker"

    test("Health check", test_loan_health)

    # Create loan
    created_loan = {}

    def test_create_loan():
        r = httpx.post(LOAN_BASE, json={
            "profile_id": "test-profile-001",
            "lender_name": "State Bank of India",
            "source_type": "FORMAL",
            "terms": {
                "principal": 100000,
                "interest_rate_annual": 9.5,
                "tenure_months": 24,
                "emi_amount": 4568
            },
            "disbursement_date": "2026-01-15T00:00:00",
            "purpose": "Crop cultivation",
            "notes": "Kharif season loan",
        }, timeout=10)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["lender_name"] == "State Bank of India"
        assert data["terms"]["principal"] == 100000
        assert data["outstanding_balance"] == 100000
        assert data["status"] == "ACTIVE"
        created_loan.update(data)
        print(f"    tracking_id={data['tracking_id']}")

    test("Create formal loan", test_create_loan)

    # Get loan by ID
    def test_get_loan():
        tid = created_loan["tracking_id"]
        r = httpx.get(f"{LOAN_BASE}/{tid}", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["tracking_id"] == tid
        assert data["lender_name"] == "State Bank of India"

    test("Get loan by ID", test_get_loan)

    # Record repayment
    def test_record_repayment():
        tid = created_loan["tracking_id"]
        r = httpx.post(f"{LOAN_BASE}/{tid}/repayments", json={
            "date": "2026-02-15T00:00:00",
            "amount": 4568,
            "is_late": False,
            "days_overdue": 0,
        }, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["outstanding_balance"] == 100000 - 4568
        assert data["repayment_count"] == 1
        print(f"    outstanding after repayment: {data['outstanding_balance']}")

    test("Record repayment", test_record_repayment)

    # Create informal loan
    def test_create_informal_loan():
        r = httpx.post(LOAN_BASE, json={
            "profile_id": "test-profile-001",
            "lender_name": "Local Moneylender",
            "source_type": "INFORMAL",
            "terms": {
                "principal": 30000,
                "interest_rate_annual": 24.0,
                "tenure_months": 6,
                "emi_amount": 5500,
            },
            "disbursement_date": "2026-02-01T00:00:00",
        }, timeout=10)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["source_type"] == "INFORMAL"
        assert data["terms"]["principal"] == 30000
        print(f"    tracking_id={data['tracking_id']}")

    test("Create informal loan", test_create_informal_loan)

    # Get borrower's loans
    def test_borrower_loans():
        r = httpx.get(f"{LOAN_BASE}/borrower/test-profile-001", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 2, f"Expected at least 2 loans, got {data['count']}"
        sources = [item["source_type"] for item in data["items"]]
        assert "FORMAL" in sources
        assert "INFORMAL" in sources
        print(f"    {data['count']} loans found")

    test("Get borrower loans", test_borrower_loans)

    # Get debt exposure
    def test_debt_exposure():
        r = httpx.get(
            f"{LOAN_BASE}/borrower/test-profile-001/exposure?annual_income=240000",
            timeout=10,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        exp = r.json()
        assert exp["active_loan_count"] >= 2
        assert exp["total_outstanding"] > 0
        assert exp["debt_to_income_ratio"] > 0
        sources = [s["source_type"] for s in exp["by_source"]]
        assert "FORMAL" in sources
        assert "INFORMAL" in sources
        print(f"    DTI={exp['debt_to_income_ratio']:.4f}, outstanding={exp['total_outstanding']}, active={exp['active_loan_count']}")

    test("Get debt exposure", test_debt_exposure)

    # Update loan status
    def test_update_status():
        tid = created_loan["tracking_id"]
        r = httpx.patch(f"{LOAN_BASE}/{tid}/status", json={
            "status": "RESTRUCTURED"
        }, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["status"] == "RESTRUCTURED"

    test("Update loan status", test_update_status)

    # Get non-existent loan
    def test_loan_not_found():
        r = httpx.get(f"{LOAN_BASE}/nonexistent-id", timeout=10)
        assert r.status_code == 404

    test("Loan not found returns 404", test_loan_not_found)

    # ===========================================================================
    # RISK ASSESSMENT SERVICE TESTS
    # ===========================================================================
    print("\n=== RISK ASSESSMENT SERVICE ===\n")

    # Health check
    def test_risk_health():
        r = httpx.get("http://localhost:8003/health", timeout=5)
        assert r.status_code == 200
        assert r.json()["service"] == "risk-assessment"

    test("Health check", test_risk_health)

    # Direct risk scoring
    scored_assessment = {}

    def test_direct_risk_score():
        r = httpx.post(f"{RISK_BASE}/score", json={
            "profile_id": "test-profile-001",
            "annual_income": 120000,
            "income_volatility_cv": 0.35,
            "months_below_average": 4,
            "seasonal_variance": 200,
            "debt_to_income_ratio": 0.35,
            "total_outstanding": 50000,
            "active_loan_count": 2,
            "credit_utilisation": 0.5,
            "on_time_repayment_ratio": 0.8,
            "has_defaults": False,
            "age": 40,
            "dependents": 3,
            "crop_diversification_index": 0.4,
            "has_irrigation": False,
            "weather_risk_score": 30.0,
            "market_risk_score": 40.0,
        }, timeout=10)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert 0 <= data["risk_score"] <= 1000
        assert data["risk_category"] in ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
        assert len(data["factors"]) == 8
        scored_assessment.update(data)
        print(f"    score={data['risk_score']}, category={data['risk_category']}")
        print(f"    confidence={data['confidence_level']}")

    test("Direct risk scoring", test_direct_risk_score)

    # Get assessment by ID
    def test_get_assessment():
        aid = scored_assessment["assessment_id"]
        r = httpx.get(f"{RISK_BASE}/{aid}", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["assessment_id"] == aid
        assert data["risk_score"] == scored_assessment["risk_score"]

    test("Get assessment by ID", test_get_assessment)

    # Get risk explanation
    def test_explain_risk():
        aid = scored_assessment["assessment_id"]
        r = httpx.get(f"{RISK_BASE}/{aid}/explain", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "risk_score" in data
        assert "top_factors" in data
        assert len(data["recommendations"]) > 0
        print(f"    recommendations: {data['recommendations'][:2]}")

    test("Get risk explanation", test_explain_risk)

    # Get risk profile history
    def test_risk_profile():
        r = httpx.get(f"{RISK_BASE}/profile/test-profile-001", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["risk_score"] == scored_assessment["risk_score"]

    test("Get latest risk for profile", test_risk_profile)

    # Cross-service assess (will use stub data providers)
    def test_cross_service_assess():
        r = httpx.post(f"{RISK_BASE}/assess", json={
            "profile_id": "test-profile-001",
        }, timeout=10)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert 0 <= data["risk_score"] <= 1000
        print(f"    cross-service score={data['risk_score']}, category={data['risk_category']}")

    test("Cross-service risk assessment", test_cross_service_assess)

    # Assessment history
    def test_assessment_history():
        r = httpx.get(f"{RISK_BASE}/profile/test-profile-001/history", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 2  # At least 2 assessments
        print(f"    {len(data)} assessments in history")

    test("Assessment history", test_assessment_history)

    # ===========================================================================
    # SUMMARY
    # ===========================================================================
    print(f"\n{'='*50}")
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*50}\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
