"""
Comprehensive DI Integration Test
Verifies that all 7 services work correctly with STORAGE_BACKEND=memory.
Run with: python test_di_integration.py
"""

import httpx
import sys
import json
from typing import Any

BASE = "http://127.0.0.1"
H = {"Content-Type": "application/json", "X-Skip-Auth": "true"}

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
INFO = "\033[94mINFO\033[0m"

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    tag = PASS if cond else FAIL
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    results.append((name, cond, detail))
    return cond


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── HEALTH CHECKS ──────────────────────────────────────────────────────────
section("1. Health Checks (all 7 services)")
services = {
    "Profile (8001)": 8001,
    "Loan (8002)": 8002,
    "Risk (8003)": 8003,
    "Cashflow (8004)": 8004,
    "Early Warning (8005)": 8005,
    "Guidance (8006)": 8006,
    "Security (8007)": 8007,
}
for name, port in services.items():
    try:
        r = httpx.get(f"{BASE}:{port}/health", headers=H, timeout=5)
        check(name, r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check(name, False, str(e))


# ── PROFILE SERVICE ────────────────────────────────────────────────────────
section("2. Profile Service (8001) — InMemoryProfileRepository")

profile_payload = {
    "personal_info": {
        "name": "Test Farmer DI",
        "age": 38,
        "gender": "M",
        "district": "Nashik",
        "state": "Maharashtra",
        "dependents": 2,
    },
    "livelihood_info": {
        "primary_occupation": "FARMER",
        "secondary_occupations": [],
        "land_holding": {
            "total_acres": 4.0,
            "irrigated_acres": 2.0,
            "rain_fed_acres": 2.0,
            "ownership_type": "OWNED",
        },
        "crop_patterns": [
            {
                "crop_name": "wheat",
                "season": "RABI",
                "area_acres": 3.0,
                "expected_yield_quintals": 50.0,
                "expected_price_per_quintal": 2150.0,
            }
        ],
        "livestock": [],
        "migration_patterns": [],
    },
    "income_records": [
        {"month": 1, "year": 2024, "amount": 12000, "source": "crop_sale"},
        {"month": 2, "year": 2024, "amount": 9000, "source": "crop_sale"},
        {"month": 3, "year": 2024, "amount": 11000, "source": "crop_sale"},
    ],
    "expense_records": [
        {"month": 1, "year": 2024, "amount": 7000, "category": "household"},
        {"month": 2, "year": 2024, "amount": 6500, "category": "household"},
    ],
    "seasonal_factors": [
        {"season": "KHARIF", "income_multiplier": 1.2, "expense_multiplier": 1.3, "notes": ""},
        {"season": "RABI", "income_multiplier": 1.0, "expense_multiplier": 1.0, "notes": ""},
        {"season": "ZAID", "income_multiplier": 0.7, "expense_multiplier": 0.7, "notes": ""},
    ],
}

profile_id: str | None = None

r = httpx.post(f"{BASE}:8001/api/v1/profiles", json=profile_payload, headers=H, timeout=10)
ok = check("Create profile", r.status_code in (200, 201), f"status={r.status_code}")
if ok:
    profile_id = r.json().get("profile_id")
    check("Profile ID returned", bool(profile_id), f"id={profile_id}")
else:
    print(f"    Error body: {r.text[:300]}")

if not profile_id:
    # Try to reuse an existing profile
    r2 = httpx.get(f"{BASE}:8001/api/v1/profiles", headers=H, timeout=5)
    profs = r2.json().get("profiles", []) if r2.status_code == 200 else []
    profile_id = profs[0]["profile_id"] if profs else None
    if profile_id:
        print(f"  [{INFO}] Reusing existing profile_id={profile_id}")
    else:
        print("  No profile available. Skipping downstream tests.")
        sys.exit(1)

# get by id
r = httpx.get(f"{BASE}:8001/api/v1/profiles/{profile_id}", headers=H, timeout=5)
check("Get profile by ID", r.status_code == 200, f"status={r.status_code}")
if r.status_code == 200:
    name_back = r.json().get("personal_info", {}).get("name", "")
    check("Profile data persisted", "DI" in name_back or len(name_back) > 0, f"name={name_back}")

# list profiles
r = httpx.get(f"{BASE}:8001/api/v1/profiles", headers=H, timeout=5)
check("List profiles", r.status_code == 200, f"status={r.status_code}")
if r.status_code == 200:
    count = len(r.json().get("profiles", []))
    check("At least one profile in list", count >= 1, f"count={count}")


# ── LOAN TRACKER ───────────────────────────────────────────────────────────
section("3. Loan Tracker (8002) — InMemoryLoanRepository")

loan_payload = {
    "profile_id": profile_id,
    "lender_name": "State Bank",
    "source_type": "FORMAL",
    "terms": {
        "principal": 75000,
        "interest_rate_annual": 9.0,
        "tenure_months": 12,
        "emi_amount": 7800.0,
    },
    "disbursement_date": "2024-01-15T00:00:00",
    "maturity_date": "2025-01-15T00:00:00",
    "purpose": "Wheat cultivation",
}

tracking_id: str | None = None

r = httpx.post(f"{BASE}:8002/api/v1/loans", json=loan_payload, headers=H, timeout=10)
ok = check("Create loan", r.status_code in (200, 201), f"status={r.status_code}")
if ok:
    tracking_id = r.json().get("tracking_id")
    check("Tracking ID returned", bool(tracking_id), f"id={tracking_id}")
else:
    print(f"    Error: {r.text[:300]}")

if tracking_id:
    r = httpx.get(f"{BASE}:8002/api/v1/loans/{tracking_id}", headers=H, timeout=5)
    check("Get loan by ID", r.status_code == 200, f"status={r.status_code}")

    r = httpx.get(f"{BASE}:8002/api/v1/loans/borrower/{profile_id}", headers=H, timeout=5)
    check("Get loans by profile", r.status_code == 200, f"status={r.status_code}")

    r = httpx.get(f"{BASE}:8002/api/v1/loans/borrower/{profile_id}/exposure", params={"annual_income": 120000}, headers=H, timeout=5)
    check("Get borrower exposure", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        exposure = r.json()
        check("Exposure non-zero", exposure.get("total_outstanding", 0) > 0, f"outstanding={exposure.get('total_outstanding')}")


# ── RISK ASSESSMENT ────────────────────────────────────────────────────────
section("4. Risk Assessment (8003) — InMemoryRiskRepository")

risk_payload = {
    "profile_id": profile_id,
    "requested_loan_amount": 75000,
    "loan_purpose": "CROP_LOAN",
    "tenure_months": 12,
}

assessment_id: str | None = None

r = httpx.post(f"{BASE}:8003/api/v1/risk/assess", json=risk_payload, headers=H, timeout=15)
ok = check("Trigger risk assessment", r.status_code in (200, 201), f"status={r.status_code}")
if ok:
    assessment_id = r.json().get("assessment_id")
    check("Assessment ID returned", bool(assessment_id), f"id={assessment_id}")
    risk_level = r.json().get("risk_level") or r.json().get("risk_category")
    check("Risk level present", bool(risk_level), f"risk_level={risk_level}")
else:
    print(f"    Error: {r.text[:300]}")

if assessment_id:
    r = httpx.get(f"{BASE}:8003/api/v1/risk/{assessment_id}", headers=H, timeout=5)
    check("Get assessment by ID", r.status_code == 200, f"status={r.status_code}")

r = httpx.get(f"{BASE}:8003/api/v1/risk/profile/{profile_id}", headers=H, timeout=5)
check("Get latest risk by profile", r.status_code == 200 or r.status_code == 404, f"status={r.status_code}")

r = httpx.get(f"{BASE}:8003/api/v1/risk/profile/{profile_id}/history", headers=H, timeout=5)
check("Get risk history", r.status_code == 200, f"status={r.status_code}")
if r.status_code == 200:
    body = r.json()
    hist = body if isinstance(body, list) else body.get("assessments", body.get("history", []))
    check("History has at least one entry", len(hist) >= 1, f"count={len(hist)}")


# ── CASHFLOW SERVICE ───────────────────────────────────────────────────────
section("5. Cashflow Service (8004) — InMemoryCashFlowRepository")

cashflow_payload = {
    "profile_id": profile_id,
    "records": [
        {"profile_id": profile_id, "category": "CROP_INCOME", "direction": "INFLOW", "amount": 12000, "month": 1, "year": 2024},
        {"profile_id": profile_id, "category": "CROP_INCOME", "direction": "INFLOW", "amount": 9000,  "month": 2, "year": 2024},
        {"profile_id": profile_id, "category": "CROP_INCOME", "direction": "INFLOW", "amount": 11000, "month": 3, "year": 2024},
        {"profile_id": profile_id, "category": "HOUSEHOLD",   "direction": "OUTFLOW","amount": 7000,  "month": 1, "year": 2024},
        {"profile_id": profile_id, "category": "HOUSEHOLD",   "direction": "OUTFLOW","amount": 6500,  "month": 2, "year": 2024},
        {"profile_id": profile_id, "category": "HOUSEHOLD",   "direction": "OUTFLOW","amount": 7500,  "month": 3, "year": 2024},
    ],
    "horizon_months": 6,
}

forecast_id: str | None = None

r = httpx.post(f"{BASE}:8004/api/v1/cashflow/forecast/direct", json=cashflow_payload, headers=H, timeout=15)
ok = check("Generate cashflow forecast", r.status_code in (200, 201), f"status={r.status_code}")
if ok:
    d = r.json()
    forecast_id = d.get("forecast_id")
    check("Forecast ID returned", bool(forecast_id), f"id={forecast_id}")
    projs = d.get("monthly_projections", [])
    check("Monthly projections present", len(projs) > 0, f"projections={len(projs)}")
else:
    print(f"    Error: {r.text[:300]}")

if forecast_id:
    r = httpx.get(f"{BASE}:8004/api/v1/cashflow/forecast/{forecast_id}", headers=H, timeout=5)
    check("Get forecast by ID", r.status_code == 200, f"status={r.status_code}")

r = httpx.get(f"{BASE}:8004/api/v1/cashflow/forecast/profile/{profile_id}", headers=H, timeout=5)
check("Get forecast by profile", r.status_code in (200, 404), f"status={r.status_code}")


# ── EARLY WARNING ──────────────────────────────────────────────────────────
section("6. Early Warning (8005) — InMemoryAlertRepository")

scenario_payload = {
    "profile_id": profile_id,
    "scenario_type": "WEATHER_IMPACT",
    "name": "Test — 30% income drop",
    "weather_adjustment": 0.7,
    "duration_months": 3,
    "existing_monthly_obligations": 3000,
    "household_monthly_expense": 6000,
}

simulation_id: str | None = None

r = httpx.post(f"{BASE}:8005/api/v1/early-warning/scenarios/simulate", json=scenario_payload, headers=H, timeout=15)
ok = check("Run scenario simulation", r.status_code in (200, 201), f"status={r.status_code}")
if ok:
    d = r.json()
    simulation_id = d.get("simulation_id")
    check("Simulation ID returned", bool(simulation_id), f"id={simulation_id}")
    check("Overall risk level present", bool(d.get("overall_risk_level")), f"risk={d.get('overall_risk_level')}")
    check("Recommendations present", len(d.get("recommendations", [])) > 0, f"count={len(d.get('recommendations',[]))}")
else:
    print(f"    Error: {r.text[:300]}")

# check alerts endpoint
r = httpx.get(f"{BASE}:8005/api/v1/early-warning/alerts/profile/{profile_id}", headers=H, timeout=5)
check("Get alerts by profile", r.status_code in (200, 404), f"status={r.status_code}")


# ── GUIDANCE SERVICE ───────────────────────────────────────────────────────
section("7. Guidance Service (8006) — InMemoryGuidanceRepository")

guidance_payload = {
    "profile_id": profile_id,
    "loan_purpose": "CROP_CULTIVATION",
    "requested_amount": 75000,
    "tenure_months": 12,
    "interest_rate_annual": 9.0,
    "projections": [
        {"month": 1, "year": 2024, "inflow": 12000, "outflow": 7000},
        {"month": 2, "year": 2024, "inflow": 9000,  "outflow": 6500},
        {"month": 3, "year": 2024, "inflow": 11000, "outflow": 7500},
    ],
}

guidance_id: str | None = None

r = httpx.post(f"{BASE}:8006/api/v1/guidance/generate/direct", json=guidance_payload, headers=H, timeout=30)
ok = check("Generate guidance (direct)", r.status_code in (200, 201), f"status={r.status_code}")
if ok:
    d = r.json()
    guidance_id = d.get("guidance_id")
    check("Guidance ID returned", bool(guidance_id), f"id={guidance_id}")
    rec_amount = d.get("recommended_amount")
    check("Recommended amount present", rec_amount is not None, f"value={rec_amount}")
    risk_summary = d.get("risk_summary") or d.get("risk_level")
    check("Risk summary present", bool(risk_summary), f"risk={risk_summary}")
else:
    print(f"    Error: {r.text[:400]}")

if guidance_id:
    r = httpx.get(f"{BASE}:8006/api/v1/guidance/{guidance_id}", headers=H, timeout=5)
    check("Get guidance by ID", r.status_code == 200, f"status={r.status_code}")

r = httpx.get(f"{BASE}:8006/api/v1/guidance/profile/{profile_id}/history", headers=H, timeout=5)
check("Get guidance by profile", r.status_code == 200, f"status={r.status_code}")


# ── SECURITY SERVICE ───────────────────────────────────────────────────────
section("8. Security Service (8007) — InMemorySecurityRepository")

consent_payload = {
    "profile_id": profile_id,
    "purpose": "CREDIT_ASSESSMENT",
    "data_categories": ["personal_info", "income_records", "loan_history"],
    "granted_by": profile_id,
    "valid_days": 30,
}

consent_id: str | None = None

r = httpx.post(f"{BASE}:8007/api/v1/security/consent", json=consent_payload, headers=H, timeout=10)
ok = check("Create consent record", r.status_code in (200, 201), f"status={r.status_code}")
if ok:
    consent_id = r.json().get("consent_id")
    check("Consent ID returned", bool(consent_id), f"id={consent_id}")
else:
    print(f"    Error: {r.text[:300]}")

if consent_id:
    r = httpx.get(f"{BASE}:8007/api/v1/security/consent/{consent_id}", headers=H, timeout=5)
    check("Get consent by ID", r.status_code == 200, f"status={r.status_code}")

r = httpx.get(f"{BASE}:8007/api/v1/security/consent/profile/{profile_id}", headers=H, timeout=5)
check("Get consents by profile", r.status_code == 200, f"status={r.status_code}")

# Check consent
check_payload = {
    "profile_id": profile_id,
    "purpose": "CREDIT_ASSESSMENT",
    "data_categories": ["personal_info"],
}
r = httpx.post(f"{BASE}:8007/api/v1/security/consent/check", json=check_payload, headers=H, timeout=5)
check("Check consent validity", r.status_code == 200, f"status={r.status_code}")

# Audit log
audit_payload = {
    "actor_id": "system-test",
    "resource_type": "BorrowerProfile",
    "resource_id": profile_id,
    "profile_id": profile_id,
    "details": {"action": "READ_PROFILE", "outcome": "SUCCESS"},
}
r = httpx.post(f"{BASE}:8007/api/v1/security/audit/access", json=audit_payload, headers=H, timeout=5)
check("Create audit log entry", r.status_code in (200, 201), f"status={r.status_code}")

r = httpx.get(f"{BASE}:8007/api/v1/security/audit/profile/{profile_id}", headers=H, timeout=5)
check("Get audit log by profile", r.status_code == 200, f"status={r.status_code}")

# Retention policies
r = httpx.get(f"{BASE}:8007/api/v1/security/retention/policies", headers=H, timeout=5)
check("Get retention policies", r.status_code == 200, f"status={r.status_code}")


# ── SUMMARY ───────────────────────────────────────────────────────────────
section("SUMMARY")
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
total = len(results)

print(f"\n  Total:  {total}")
print(f"  Passed: \033[92m{passed}\033[0m")
print(f"  Failed: \033[91m{failed}\033[0m")

if failed:
    print("\n  Failed checks:")
    for name, ok, detail in results:
        if not ok:
            print(f"    - {name}: {detail}")

print()
sys.exit(0 if failed == 0 else 1)
