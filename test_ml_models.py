"""
End-to-end ML Model Simulation Test
====================================
Tests all 3 trained ML models via the microservice APIs:
1. Risk Assessment (XGBoost) — port 8003
2. Cashflow Prediction (Prophet) — port 8004
3. Early Warning (IsolationForest + LightGBM) — port 8005

Also tests scenario simulation on port 8005.
"""
import json
import requests
import sys
from datetime import datetime

RISK_URL = "http://127.0.0.1:8003/api/v1/risk"
CASHFLOW_URL = "http://127.0.0.1:8004/api/v1/cashflow"
WARNING_URL = "http://127.0.0.1:8005/api/v1/early-warning"
PROFILE_URL = "http://127.0.0.1:8001/api/v1/profiles"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

def header(title):
    print(f"\n{BOLD}{CYAN}{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}{RESET}\n")

def result(label, status, detail=""):
    icon = f"{GREEN}PASS" if status else f"{RED}FAIL"
    print(f"  [{icon}{RESET}] {label}")
    if detail:
        print(f"        {detail}")

def get_profiles():
    r = requests.get(f"{PROFILE_URL}?limit=50")
    return r.json()["items"]


# ======================================================================
# 1. RISK ASSESSMENT MODEL
# ======================================================================
def test_risk_scoring():
    header("1. RISK SCORING MODEL (XGBoost)")

    profiles = get_profiles()
    if not profiles:
        print(f"  {RED}No profiles found! Seed profiles first.{RESET}")
        return False

    all_ok = True

    # Test A: Direct scoring with explicit features
    print(f"  {YELLOW}Test A: Direct scoring with explicit features{RESET}")
    payload = {
        "profile_id": profiles[0]["profile_id"],
        "income_volatility_cv": 0.35,
        "annual_income": 180000.0,
        "months_below_average": 3,
        "debt_to_income_ratio": 0.4,
        "total_outstanding": 50000.0,
        "active_loan_count": 2,
        "credit_utilisation": 0.6,
        "on_time_repayment_ratio": 0.85,
        "has_defaults": False,
        "seasonal_variance": 0.2,
        "crop_diversification_index": 0.5,
        "weather_risk_score": 25.0,
        "market_risk_score": 30.0,
        "dependents": 3,
        "age": 35,
        "has_irrigation": True,
    }
    r = requests.post(f"{RISK_URL}/score", json=payload)
    ok = r.status_code in (200, 201)
    if ok:
        data = r.json()
        score = data.get("risk_score", data.get("score", "?"))
        cat = data.get("risk_category", data.get("category", "?"))
        conf = data.get("confidence_level", data.get("confidence", "?"))
        model = data.get("model_version", "?")
        result("Direct score", True, f"Score={score}, Category={cat}, Confidence={conf}, Model={model}")
    else:
        result("Direct score", False, f"HTTP {r.status_code}: {r.text[:200]}")
        all_ok = False

    # Test B: Profile-based assessment (cross-service)
    print(f"\n  {YELLOW}Test B: Profile-based assessment for each profile{RESET}")
    for p in profiles[:3]:
        r = requests.post(f"{RISK_URL}/assess", json={"profile_id": p["profile_id"]})
        ok = r.status_code in (200, 201)
        if ok:
            data = r.json()
            score = data.get("risk_score", data.get("score", "?"))
            cat = data.get("risk_category", data.get("category", "?"))
            result(f"{p['name']}", True, f"Score={score}, Category={cat}")
        else:
            result(f"{p['name']}", False, f"HTTP {r.status_code}: {r.text[:200]}")
            all_ok = False

    # Test C: Retrieve assessment
    print(f"\n  {YELLOW}Test C: Retrieve stored assessment{RESET}")
    r = requests.get(f"{RISK_URL}/profile/{profiles[0]['profile_id']}")
    ok = r.status_code == 200
    if ok:
        data = r.json()
        result("Get latest assessment", True, f"Assessment ID={data.get('assessment_id', '?')}")
    else:
        result("Get latest assessment", False, f"HTTP {r.status_code}: {r.text[:200]}")
        all_ok = False

    return all_ok


# ======================================================================
# 2. CASHFLOW PREDICTION MODEL
# ======================================================================
def test_cashflow():
    header("2. CASHFLOW PREDICTION MODEL (Prophet)")

    profiles = get_profiles()
    if not profiles:
        print(f"  {RED}No profiles found!{RESET}")
        return False

    all_ok = True
    pid = profiles[0]["profile_id"]

    # Test A: Seed cashflow records
    print(f"  {YELLOW}Test A: Seeding 18 months of cashflow records for {profiles[0]['name']}{RESET}")
    records = []
    for year in [2024, 2025]:
        for month in range(1, 13):
            if year == 2025 and month > 6:
                break
            # Income varies by season
            if month in [7, 8, 9, 10]:  # Kharif
                income = 35000 + (month * 1000)
                season = "KHARIF"
            elif month in [11, 12, 1, 2, 3]:  # Rabi
                income = 25000 + (month * 500)
                season = "RABI"
            else:  # Zaid
                income = 10000
                season = "ZAID"

            records.append({
                "profile_id": pid,
                "category": "CROP_INCOME",
                "direction": "INFLOW",
                "amount": income,
                "month": month,
                "year": year,
                "season": season,
                "notes": f"Income {month}/{year}",
            })
            records.append({
                "profile_id": pid,
                "category": "HOUSEHOLD",
                "direction": "OUTFLOW",
                "amount": 8000 + (month * 200),
                "month": month,
                "year": year,
                "notes": f"Household {month}/{year}",
            })
            records.append({
                "profile_id": pid,
                "category": "SEED_FERTILIZER",
                "direction": "OUTFLOW",
                "amount": 5000 if month in [6, 7, 11] else 1000,
                "month": month,
                "year": year,
                "season": season,
                "notes": f"Farming cost {month}/{year}",
            })

    r = requests.post(f"{CASHFLOW_URL}/records/batch", json={"records": records})
    ok = r.status_code in (200, 201)
    result(f"Batch insert ({len(records)} records)", ok, f"HTTP {r.status_code}")
    if not ok:
        print(f"        {r.text[:300]}")
        all_ok = False

    # Test B: Direct forecast
    print(f"\n  {YELLOW}Test B: Direct cashflow forecast{RESET}")
    forecast_records = [
        {"profile_id": pid, "category": "CROP_INCOME", "direction": "INFLOW", "amount": a, "month": m, "year": y, "season": s}
        for m, y, a, s in [
            (1, 2025, 25000, "RABI"), (2, 2025, 26000, "RABI"), (3, 2025, 40000, "RABI"),
            (4, 2025, 10000, "ZAID"), (5, 2025, 10000, "ZAID"), (6, 2025, 10000, "ZAID"),
            (7, 2025, 35000, "KHARIF"), (8, 2025, 38000, "KHARIF"), (9, 2025, 42000, "KHARIF"),
            (10, 2025, 45000, "KHARIF"), (11, 2025, 28000, "RABI"), (12, 2025, 26000, "RABI"),
        ]
    ]
    r = requests.post(f"{CASHFLOW_URL}/forecast/direct", json={
        "profile_id": pid,
        "records": forecast_records,
        "horizon_months": 6,
        "start_month": 1,
        "start_year": 2026,
        "existing_monthly_obligations": 3000,
        "household_monthly_expense": 8000,
        "weather_adjustment": 1.0,
        "market_adjustment": 1.0,
        "loan_tenure_months": 12,
    })
    ok = r.status_code in (200, 201)
    if ok:
        data = r.json()
        forecast_id = data.get("forecast_id", "?")
        projections = data.get("monthly_projections", data.get("projections", []))
        n_months = len(projections)
        result("Direct forecast", True, f"Forecast ID={forecast_id}, {n_months} months projected")
        if projections:
            for proj in projections[:3]:
                inc = proj.get("predicted_income", proj.get("inflow", "?"))
                exp = proj.get("predicted_expense", proj.get("outflow", "?"))
                print(f"        Month {proj.get('month','?')}/{proj.get('year','?')}: Income={inc}, Expense={exp}")
            if n_months > 3:
                print(f"        ... and {n_months - 3} more months")
    else:
        result("Direct forecast", False, f"HTTP {r.status_code}: {r.text[:300]}")
        all_ok = False

    # Test C: Repayment capacity
    print(f"\n  {YELLOW}Test C: Repayment capacity{RESET}")
    r = requests.get(f"{CASHFLOW_URL}/capacity/{pid}")
    if r.status_code == 200:
        data = r.json()
        result("Repayment capacity", True, json.dumps(data, indent=2)[:300])
    else:
        result("Repayment capacity", False, f"HTTP {r.status_code}: {r.text[:200]}")

    return all_ok


# ======================================================================
# 3. EARLY WARNING MODEL
# ======================================================================
def test_early_warning():
    header("3. EARLY WARNING MODEL (IsolationForest + LightGBM)")

    profiles = get_profiles()
    if not profiles:
        print(f"  {RED}No profiles found!{RESET}")
        return False

    all_ok = True
    pid = profiles[0]["profile_id"]

    # Test A: Direct alert generation (stressed borrower scenario)
    print(f"  {YELLOW}Test A: Direct alert — stressed borrower scenario{RESET}")
    r = requests.post(f"{WARNING_URL}/alerts/direct", json={
        "profile_id": pid,
        "dti_ratio": 0.65,
        "missed_payments": 3,
        "days_overdue_avg": 25.0,
        "recent_surplus_trend": [5000, 2000, -1000, -4000, -6000],
        "expected_incomes": [
            {"month": 10, "year": 2025, "amount": 50000},
            {"month": 11, "year": 2025, "amount": 45000},
            {"month": 12, "year": 2025, "amount": 30000},
        ],
        "actual_incomes": [
            {"month": 10, "year": 2025, "amount": 25000},
            {"month": 11, "year": 2025, "amount": 20000},
            {"month": 12, "year": 2025, "amount": 15000},
        ],
        "risk_category": "HIGH",
        "alert_type": "INCOME_DROP",
    })
    ok = r.status_code in (200, 201)
    if ok:
        data = r.json()
        severity = data.get("severity", "?")
        alert_type = data.get("alert_type", "?")
        alert_id = data.get("alert_id", "?")
        result("Stressed borrower alert", True, f"Alert ID={alert_id}, Severity={severity}, Type={alert_type}")
    else:
        result("Stressed borrower alert", False, f"HTTP {r.status_code}: {r.text[:300]}")
        all_ok = False

    # Test B: Direct alert — healthy borrower (should be low/info)
    print(f"\n  {YELLOW}Test B: Direct alert — healthy borrower scenario{RESET}")
    r = requests.post(f"{WARNING_URL}/alerts/direct", json={
        "profile_id": pid,
        "dti_ratio": 0.2,
        "missed_payments": 0,
        "days_overdue_avg": 0.0,
        "recent_surplus_trend": [8000, 9000, 10000, 11000],
        "expected_incomes": [
            {"month": 10, "year": 2025, "amount": 40000},
            {"month": 11, "year": 2025, "amount": 35000},
        ],
        "actual_incomes": [
            {"month": 10, "year": 2025, "amount": 42000},
            {"month": 11, "year": 2025, "amount": 36000},
        ],
        "risk_category": "LOW",
        "alert_type": "ROUTINE_CHECK",
    })
    ok = r.status_code in (200, 201)
    if ok:
        data = r.json()
        severity = data.get("severity", "?")
        result("Healthy borrower alert", True, f"Severity={severity} (expected: INFO/LOW)")
    else:
        result("Healthy borrower alert", False, f"HTTP {r.status_code}: {r.text[:200]}")
        all_ok = False

    # Test C: Scenario simulation — drought
    print(f"\n  {YELLOW}Test C: Scenario simulation — drought{RESET}")
    r = requests.post(f"{WARNING_URL}/scenarios/simulate/direct", json={
        "profile_id": pid,
        "scenario_type": "WEATHER_IMPACT",
        "name": "Severe drought",
        "description": "Simulates 40% income reduction from drought",
        "income_reduction_pct": 40.0,
        "weather_adjustment": 0.6,
        "market_price_change_pct": -15.0,
        "duration_months": 6,
        "baseline_projections": [
            {"month": 1, "year": 2026, "inflow": 25000, "outflow": 12000},
            {"month": 2, "year": 2026, "inflow": 26000, "outflow": 11000},
            {"month": 3, "year": 2026, "inflow": 40000, "outflow": 15000},
            {"month": 4, "year": 2026, "inflow": 10000, "outflow": 10000},
            {"month": 5, "year": 2026, "inflow": 8000, "outflow": 9000},
            {"month": 6, "year": 2026, "inflow": 50000, "outflow": 18000},
        ],
        "existing_monthly_obligations": 5000,
        "household_monthly_expense": 8000,
    })
    ok = r.status_code in (200, 201)
    if ok:
        data = r.json()
        sim_id = data.get("simulation_id", "?")
        pod = data.get("probability_of_default", data.get("default_probability", "?"))
        dscr = data.get("expected_dscr", data.get("dscr", "?"))
        result("Drought scenario", True, f"Sim ID={sim_id}, P(Default)={pod}, DSCR={dscr}")
        recs = data.get("recommendations", [])
        if recs:
            for rec in recs[:3]:
                if isinstance(rec, dict):
                    print(f"        Rec: {rec.get('text', rec.get('recommendation', str(rec)[:100]))}")
                else:
                    print(f"        Rec: {rec[:100]}")
    else:
        result("Drought scenario", False, f"HTTP {r.status_code}: {r.text[:300]}")
        all_ok = False

    # Test D: Get alerts for profile
    print(f"\n  {YELLOW}Test D: Retrieve alerts for profile{RESET}")
    r = requests.get(f"{WARNING_URL}/alerts/profile/{pid}")
    ok = r.status_code == 200
    if ok:
        data = r.json()
        alerts = data if isinstance(data, list) else data.get("alerts", data.get("items", []))
        result("Get profile alerts", True, f"{len(alerts)} alerts found")
    else:
        result("Get profile alerts", False, f"HTTP {r.status_code}: {r.text[:200]}")
        all_ok = False

    return all_ok


# ======================================================================
# MAIN
# ======================================================================
if __name__ == "__main__":
    print(f"\n{BOLD}{CYAN}{'#'*70}")
    print(f"  ML MODEL END-TO-END SIMULATION TEST")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*70}{RESET}")

    results = {}

    try:
        results["Risk Scoring"] = test_risk_scoring()
    except Exception as e:
        results["Risk Scoring"] = False
        print(f"  {RED}ERROR: {e}{RESET}")

    try:
        results["Cashflow Prediction"] = test_cashflow()
    except Exception as e:
        results["Cashflow Prediction"] = False
        print(f"  {RED}ERROR: {e}{RESET}")

    try:
        results["Early Warning"] = test_early_warning()
    except Exception as e:
        results["Early Warning"] = False
        print(f"  {RED}ERROR: {e}{RESET}")

    # Summary
    header("SUMMARY")
    for name, ok in results.items():
        icon = f"{GREEN}PASS" if ok else f"{RED}FAIL"
        print(f"  [{icon}{RESET}] {name}")

    all_pass = all(results.values())
    print(f"\n  {BOLD}{'All models working!' if all_pass else 'Some models need attention.'}{RESET}\n")

    sys.exit(0 if all_pass else 1)
