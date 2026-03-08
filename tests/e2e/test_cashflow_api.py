"""End-to-end API tests for the Cash Flow service.

Run with:
    python tests/e2e/test_cashflow_api.py

Requires the Cash Flow service running on http://localhost:8004
"""

import sys

import httpx

BASE = "http://localhost:8004/api/v1/cashflow"

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
    # CASH FLOW SERVICE TESTS
    # ===========================================================================
    print("\n=== CASH FLOW SERVICE ===\n")

    # -- Health check -----------------------------------------------------------
    def test_health():
        r = httpx.get("http://localhost:8004/health", timeout=5)
        assert r.status_code == 200
        assert r.json()["service"] == "cashflow"

    test("Health check", test_health)

    # -- Record a single cash flow entry ---------------------------------------
    created_record = {}

    def test_record_single():
        r = httpx.post(f"{BASE}/records", json={
            "profile_id": "e2e-farmer-001",
            "category": "CROP_INCOME",
            "direction": "INFLOW",
            "amount": 45000,
            "month": 10,
            "year": 2025,
            "season": "KHARIF",
            "notes": "Rice harvest sale",
        }, timeout=10)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["profile_id"] == "e2e-farmer-001"
        assert data["category"] == "CROP_INCOME"
        assert data["direction"] == "INFLOW"
        assert data["amount"] == 45000
        assert data["month"] == 10
        assert data["year"] == 2025
        assert "record_id" in data
        assert "recorded_at" in data
        created_record.update(data)
        print(f"    record_id={data['record_id']}")

    test("Record single cash flow", test_record_single)

    # -- Record batch -----------------------------------------------------------
    def test_record_batch():
        records = [
            # Income records — diverse months for seasonal pattern
            {"profile_id": "e2e-farmer-001", "category": "CROP_INCOME", "direction": "INFLOW",
             "amount": 50000, "month": 11, "year": 2024, "season": "KHARIF", "notes": "Rice 2024"},
            {"profile_id": "e2e-farmer-001", "category": "CROP_INCOME", "direction": "INFLOW",
             "amount": 30000, "month": 4, "year": 2025, "season": "RABI", "notes": "Wheat 2025"},
            {"profile_id": "e2e-farmer-001", "category": "LIVESTOCK_INCOME", "direction": "INFLOW",
             "amount": 8000, "month": 6, "year": 2025, "notes": "Milk sales"},
            {"profile_id": "e2e-farmer-001", "category": "LABOUR_INCOME", "direction": "INFLOW",
             "amount": 5000, "month": 1, "year": 2025, "notes": "Off-season labour"},
            {"profile_id": "e2e-farmer-001", "category": "GOVERNMENT_SUBSIDY", "direction": "INFLOW",
             "amount": 6000, "month": 7, "year": 2025, "notes": "PM-KISAN"},
            # Expense records
            {"profile_id": "e2e-farmer-001", "category": "SEED_FERTILIZER", "direction": "OUTFLOW",
             "amount": 15000, "month": 6, "year": 2025, "notes": "Kharif inputs"},
            {"profile_id": "e2e-farmer-001", "category": "SEED_FERTILIZER", "direction": "OUTFLOW",
             "amount": 10000, "month": 11, "year": 2024, "notes": "Rabi inputs"},
            {"profile_id": "e2e-farmer-001", "category": "HOUSEHOLD", "direction": "OUTFLOW",
             "amount": 8000, "month": 1, "year": 2025, "notes": "Monthly household"},
            {"profile_id": "e2e-farmer-001", "category": "HOUSEHOLD", "direction": "OUTFLOW",
             "amount": 8000, "month": 4, "year": 2025, "notes": "Monthly household"},
            {"profile_id": "e2e-farmer-001", "category": "HOUSEHOLD", "direction": "OUTFLOW",
             "amount": 8000, "month": 6, "year": 2025, "notes": "Monthly household"},
            {"profile_id": "e2e-farmer-001", "category": "HOUSEHOLD", "direction": "OUTFLOW",
             "amount": 8000, "month": 10, "year": 2025, "notes": "Monthly household"},
            {"profile_id": "e2e-farmer-001", "category": "EDUCATION", "direction": "OUTFLOW",
             "amount": 12000, "month": 7, "year": 2025, "notes": "School fees"},
        ]
        r = httpx.post(f"{BASE}/records/batch", json={"records": records}, timeout=10)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["count"] == 12, f"Expected 12 records, got {data['count']}"
        assert len(data["items"]) == 12
        print(f"    batch recorded {data['count']} items")

    test("Record batch cash flows", test_record_batch)

    # -- Get records for a profile ----------------------------------------------
    def test_get_records():
        r = httpx.get(f"{BASE}/records/e2e-farmer-001", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 13  # 1 single + 12 batch
        assert len(data["items"]) >= 13
        print(f"    {data['count']} total records for profile")

    test("Get records for profile", test_get_records)

    # -- Direct forecast (no cross-service calls) --------------------------------
    forecast_data = {}

    def test_direct_forecast():
        records = [
            # At least 3 records required by validation
            {"profile_id": "e2e-farmer-001", "category": "CROP_INCOME", "direction": "INFLOW",
             "amount": 50000, "month": 10, "year": 2025, "season": "KHARIF"},
            {"profile_id": "e2e-farmer-001", "category": "CROP_INCOME", "direction": "INFLOW",
             "amount": 35000, "month": 4, "year": 2025, "season": "RABI"},
            {"profile_id": "e2e-farmer-001", "category": "LIVESTOCK_INCOME", "direction": "INFLOW",
             "amount": 8000, "month": 7, "year": 2025},
            {"profile_id": "e2e-farmer-001", "category": "LABOUR_INCOME", "direction": "INFLOW",
             "amount": 5000, "month": 1, "year": 2025},
            {"profile_id": "e2e-farmer-001", "category": "SEED_FERTILIZER", "direction": "OUTFLOW",
             "amount": 15000, "month": 6, "year": 2025},
            {"profile_id": "e2e-farmer-001", "category": "HOUSEHOLD", "direction": "OUTFLOW",
             "amount": 8000, "month": 1, "year": 2025},
            {"profile_id": "e2e-farmer-001", "category": "HOUSEHOLD", "direction": "OUTFLOW",
             "amount": 8000, "month": 4, "year": 2025},
            {"profile_id": "e2e-farmer-001", "category": "HOUSEHOLD", "direction": "OUTFLOW",
             "amount": 8000, "month": 7, "year": 2025},
            {"profile_id": "e2e-farmer-001", "category": "HOUSEHOLD", "direction": "OUTFLOW",
             "amount": 8000, "month": 10, "year": 2025},
        ]
        r = httpx.post(f"{BASE}/forecast/direct", json={
            "profile_id": "e2e-farmer-001",
            "records": records,
            "horizon_months": 12,
            "start_month": 1,
            "start_year": 2026,
            "household_monthly_expense": 8000,
            "existing_monthly_obligations": 0,
            "weather_adjustment": 1.0,
            "market_adjustment": 1.0,
            "loan_tenure_months": 12,
        }, timeout=30)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert "forecast_id" in data
        assert data["profile_id"] == "e2e-farmer-001"
        assert len(data["monthly_projections"]) == 12
        assert len(data["seasonal_patterns"]) > 0
        assert len(data["uncertainty_bands"]) == 12
        assert data["repayment_capacity"]["profile_id"] == "e2e-farmer-001"
        assert data["repayment_capacity"]["recommended_emi"] >= 0
        assert data["total_projected_inflow"] > 0
        assert data["total_projected_outflow"] > 0
        forecast_data.update(data)
        print(f"    forecast_id={data['forecast_id']}")
        print(f"    projections={len(data['monthly_projections'])} months")
        print(f"    recommended_emi=₹{data['repayment_capacity']['recommended_emi']:,.0f}")
        if data.get("best_timing_window"):
            bw = data["best_timing_window"]
            print(f"    best_timing={bw['start_month']}/{bw['start_year']} score={bw['suitability_score']}")

    test("Direct forecast generation", test_direct_forecast)

    # -- Get forecast by ID -----------------------------------------------------
    def test_get_forecast():
        fid = forecast_data["forecast_id"]
        r = httpx.get(f"{BASE}/forecast/{fid}", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["forecast_id"] == fid
        assert data["profile_id"] == "e2e-farmer-001"
        assert len(data["monthly_projections"]) == 12

    test("Get forecast by ID", test_get_forecast)

    # -- Get forecast by profile -------------------------------------------------
    def test_get_forecast_by_profile():
        r = httpx.get(f"{BASE}/forecast/profile/e2e-farmer-001", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["forecast_id"] == forecast_data["forecast_id"]
        assert data["profile_id"] == "e2e-farmer-001"

    test("Get forecast by profile", test_get_forecast_by_profile)

    # -- Repayment capacity endpoint----------------------------------------------
    def test_repayment_capacity():
        r = httpx.get(f"{BASE}/capacity/e2e-farmer-001", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["profile_id"] == "e2e-farmer-001"
        assert data["recommended_emi"] >= 0
        assert data["max_affordable_emi"] >= 0
        assert data["emergency_reserve"] >= 0
        assert data["debt_service_coverage_ratio"] > 0
        print(f"    max_emi=₹{data['max_affordable_emi']:,.0f}")
        print(f"    recommended_emi=₹{data['recommended_emi']:,.0f}")
        print(f"    DSCR={data['debt_service_coverage_ratio']:.2f}")

    test("Repayment capacity", test_repayment_capacity)

    # -- Timing recommendations ---------------------------------------------------
    def test_timing_recommendations():
        r = httpx.get(f"{BASE}/timing/e2e-farmer-001", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Each window should have required fields
        for tw in data:
            assert "start_month" in tw
            assert "suitability_score" in tw
            assert 0 <= tw["suitability_score"] <= 100
        # Print top windows
        sorted_tw = sorted(data, key=lambda x: x["suitability_score"], reverse=True)
        for tw in sorted_tw[:3]:
            print(f"    month {tw['start_month']}/{tw['start_year']} → score={tw['suitability_score']}")

    test("Timing recommendations", test_timing_recommendations)

    # -- Second forecast for history test -----------------------------------------
    def test_direct_forecast_second():
        records = [
            {"profile_id": "e2e-farmer-001", "category": "CROP_INCOME", "direction": "INFLOW",
             "amount": 55000, "month": 10, "year": 2025},
            {"profile_id": "e2e-farmer-001", "category": "CROP_INCOME", "direction": "INFLOW",
             "amount": 40000, "month": 4, "year": 2025},
            {"profile_id": "e2e-farmer-001", "category": "LIVESTOCK_INCOME", "direction": "INFLOW",
             "amount": 9000, "month": 7, "year": 2025},
            {"profile_id": "e2e-farmer-001", "category": "HOUSEHOLD", "direction": "OUTFLOW",
             "amount": 9000, "month": 1, "year": 2025},
            {"profile_id": "e2e-farmer-001", "category": "HOUSEHOLD", "direction": "OUTFLOW",
             "amount": 9000, "month": 4, "year": 2025},
            {"profile_id": "e2e-farmer-001", "category": "SEED_FERTILIZER", "direction": "OUTFLOW",
             "amount": 12000, "month": 6, "year": 2025},
        ]
        r = httpx.post(f"{BASE}/forecast/direct", json={
            "profile_id": "e2e-farmer-001",
            "records": records,
            "horizon_months": 6,
            "loan_tenure_months": 6,
        }, timeout=30)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert len(data["monthly_projections"]) == 6
        print(f"    second forecast_id={data['forecast_id']}")

    test("Second direct forecast (for history)", test_direct_forecast_second)

    # -- Forecast history ---------------------------------------------------------
    def test_forecast_history():
        r = httpx.get(f"{BASE}/forecast/profile/e2e-farmer-001/history", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 2, f"Expected ≥2 forecasts in history, got {data['count']}"
        assert len(data["items"]) >= 2
        print(f"    {data['count']} forecasts in history")

    test("Forecast history", test_forecast_history)

    # -- Validation: invalid record -----------------------------------------------
    def test_validation_invalid_amount():
        r = httpx.post(f"{BASE}/records", json={
            "profile_id": "e2e-farmer-001",
            "category": "CROP_INCOME",
            "direction": "INFLOW",
            "amount": -100,  # negative amount
            "month": 10,
            "year": 2025,
        }, timeout=10)
        assert r.status_code == 422, f"Expected 422, got {r.status_code}"

    test("Validation: negative amount rejected", test_validation_invalid_amount)

    def test_validation_invalid_month():
        r = httpx.post(f"{BASE}/records", json={
            "profile_id": "e2e-farmer-001",
            "category": "CROP_INCOME",
            "direction": "INFLOW",
            "amount": 1000,
            "month": 13,  # invalid month
            "year": 2025,
        }, timeout=10)
        assert r.status_code == 422, f"Expected 422, got {r.status_code}"

    test("Validation: invalid month rejected", test_validation_invalid_month)

    def test_validation_too_few_records():
        r = httpx.post(f"{BASE}/forecast/direct", json={
            "profile_id": "e2e-farmer-001",
            "records": [
                {"profile_id": "e2e-farmer-001", "category": "CROP_INCOME",
                 "direction": "INFLOW", "amount": 1000, "month": 1, "year": 2025},
                {"profile_id": "e2e-farmer-001", "category": "HOUSEHOLD",
                 "direction": "OUTFLOW", "amount": 500, "month": 2, "year": 2025},
            ],
            "horizon_months": 12,
        }, timeout=10)
        assert r.status_code == 422, f"Expected 422 for too few records, got {r.status_code}"

    test("Validation: too few records for forecast rejected", test_validation_too_few_records)

    # -- 404: nonexistent forecast -------------------------------------------------
    def test_forecast_not_found():
        r = httpx.get(f"{BASE}/forecast/nonexistent-id-999", timeout=10)
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"

    test("404 for nonexistent forecast", test_forecast_not_found)

    # ===========================================================================
    # SUMMARY
    # ===========================================================================
    print(f"\n{'='*50}")
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*50}\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
