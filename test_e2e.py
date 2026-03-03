"""End-to-end test: profile create → cashflow forecast → guidance → scenario simulation."""
import httpx, json, sys

BASE = "http://127.0.0.1"
H = {"Content-Type": "application/json", "X-Skip-Auth": "true"}

# ── 1. Create Profile ──────────────────────────────────────────────────────
profile_payload = {
    "personal_info": {
        "name": "Ramesh Kumar",
        "age": 42,
        "gender": "M",
        "district": "Pune",
        "state": "Maharashtra",
        "dependents": 3
    },
    "livelihood_info": {
        "primary_occupation": "FARMER",
        "secondary_occupations": [],
        "land_holding": {
            "total_acres": 3.5,
            "irrigated_acres": 1.5,
            "rain_fed_acres": 2.0,
            "ownership_type": "OWNED"
        },
        "crop_patterns": [
            {
                "crop_name": "rice",
                "season": "KHARIF",
                "area_acres": 2.0,
                "expected_yield_quintals": 40.0,
                "expected_price_per_quintal": 2183.0
            }
        ],
        "livestock": [],
        "migration_patterns": []
    },
    "income_records": [
        {"month": 1, "year": 2024, "amount": 10000, "source": "crop_sale"},
        {"month": 2, "year": 2024, "amount":  8000, "source": "crop_sale"},
        {"month": 3, "year": 2024, "amount": 12000, "source": "crop_sale"},
        {"month": 4, "year": 2024, "amount":  5000, "source": "crop_sale"},
        {"month": 5, "year": 2024, "amount":  5000, "source": "crop_sale"},
        {"month": 6, "year": 2024, "amount":  6000, "source": "crop_sale"},
    ],
    "expense_records": [
        {"month": 1, "year": 2024, "amount": 6000, "category": "household"},
        {"month": 2, "year": 2024, "amount": 5500, "category": "household"},
        {"month": 3, "year": 2024, "amount": 7000, "category": "household"},
    ],
    "seasonal_factors": [
        {"season": "KHARIF", "income_multiplier": 1.3, "expense_multiplier": 1.4, "notes": "Monsoon season"},
        {"season": "RABI",   "income_multiplier": 1.1, "expense_multiplier": 1.0, "notes": "Winter season"},
        {"season": "ZAID",   "income_multiplier": 0.6, "expense_multiplier": 0.6, "notes": "Summer off-season"},
    ]
}

r = httpx.post(f"{BASE}:8001/api/v1/profiles", json=profile_payload, headers=H, timeout=10, verify=False)
print(f"[1] Create Profile: [{r.status_code}]")
if r.status_code in (200, 201):
    profile_id = r.json().get("profile_id")
    print(f"    profile_id = {profile_id}")
else:
    print("    Error:", r.text[:200])
    # Try to use an existing profile
    r2 = httpx.get(f"{BASE}:8001/api/v1/profiles", headers=H, timeout=5, verify=False)
    profiles = r2.json().get("profiles", [])
    profile_id = profiles[0]["profile_id"] if profiles else None
    print(f"    Using existing profile_id = {profile_id}")

print()

if not profile_id:
    print("No profile available, stopping.")
    sys.exit(1)

# ── 2. Cashflow forecast with direct records (exercises weather + market APIs) ──
cashflow_direct = {
    "profile_id": profile_id,
    "records": [
        {"profile_id": profile_id, "category": "CROP_INCOME", "direction": "INFLOW",  "amount": 10000, "month": 1, "year": 2024},
        {"profile_id": profile_id, "category": "CROP_INCOME", "direction": "INFLOW",  "amount":  8000, "month": 2, "year": 2024},
        {"profile_id": profile_id, "category": "CROP_INCOME", "direction": "INFLOW",  "amount": 12000, "month": 3, "year": 2024},
        {"profile_id": profile_id, "category": "HOUSEHOLD",   "direction": "OUTFLOW", "amount":  6000, "month": 1, "year": 2024},
        {"profile_id": profile_id, "category": "HOUSEHOLD",   "direction": "OUTFLOW", "amount":  5500, "month": 2, "year": 2024},
        {"profile_id": profile_id, "category": "HOUSEHOLD",   "direction": "OUTFLOW", "amount":  7000, "month": 3, "year": 2024},
    ],
    "horizon_months": 6,
}
r = httpx.post(f"{BASE}:8004/api/v1/cashflow/forecast/direct", json=cashflow_direct, headers=H, timeout=15, verify=False)
print(f"[2] Cashflow forecast/direct: [{r.status_code}]")
if r.status_code in (200, 201):
    d = r.json()
    print(f"    forecast_id={d.get('forecast_id')}")
    projs = d.get('monthly_projections', [])
    if projs:
        avg_surplus = sum(p.get('net_cash_flow', 0) for p in projs) / len(projs)
        print(f"    avg_monthly_net (from projections)=Rs {avg_surplus:,.0f}")
    print(f"    weather_factor={d.get('weather_factor') or d.get('weather_adjustment_factor') or 'N/A (direct mode)'}")
    print(f"    market_factor={d.get('market_factor') or d.get('market_adjustment_factor') or 'N/A (direct mode)'}")
else:
    print("    Error:", r.text[:400])

print()

# ── 3. Guidance generate/direct ────────────────────────────────────────────
r3 = httpx.get(f"{BASE}:8006/openapi.json", timeout=5, verify=False)
direct_schema = r3.json().get('components', {}).get('schemas', {}).get('GenerateGuidanceDirectRequest', {})
print("Guidance direct required fields:", [k for k,v in direct_schema.get('properties',{}).items()])
print()

guidance_direct = {
    "profile_id": profile_id,
    "loan_purpose": "CROP_CULTIVATION",
    "requested_amount": 50000,
    "tenure_months": 12,
    "interest_rate_annual": 9.0,
    "projections": [
        {"month": 1, "year": 2024, "inflow": 10000, "outflow": 6000},
        {"month": 2, "year": 2024, "inflow":  8000, "outflow": 5500},
        {"month": 3, "year": 2024, "inflow": 12000, "outflow": 7000},
    ]
}
r = httpx.post(f"{BASE}:8006/api/v1/guidance/generate/direct", json=guidance_direct, headers=H, timeout=20, verify=False)
print(f"[3] Guidance generate/direct: [{r.status_code}]")
if r.status_code in (200, 201):
    d = r.json()
    risk = d.get('risk_summary') or {}
    rec = d.get('recommended_amount') or {}
    print(f"    risk_level={risk.get('risk_category') or risk.get('risk_level') or d.get('risk_level')}")
    print(f"    recommended Rs {rec.get('min_amount'):,.0f} – Rs {rec.get('max_amount'):,.0f}" if rec else f"    recommended_amount={d.get('recommended_amount')}")
    expl = d.get("explanation") or {}
    summary = expl.get("summary", "") if isinstance(expl, dict) else str(expl)
    print(f"    summary={summary[:250]}")
else:
    print("    Error:", r.text[:600])

print()

# ── 4. Scenario Simulation ─────────────────────────────────────────────────
# Requires: cashflow forecast stored in step 2 for this profile_id.
# Early warning service fetches it via GET /api/v1/cashflow/forecast/profile/{id}
scenario_payload = {
    "profile_id": profile_id,
    "scenario_type": "WEATHER_IMPACT",
    "name": "Bad Monsoon — 40% weather reduction, 4 months",
    "weather_adjustment": 0.6,   # 40% income drop due to weather
    "duration_months": 4,
    "existing_monthly_obligations": 2500,
    "household_monthly_expense": 5000,
}
r = httpx.post(f"{BASE}:8005/api/v1/early-warning/scenarios/simulate", json=scenario_payload, headers=H, timeout=15, verify=False)
print(f"[4] Scenario simulation: [{r.status_code}]")
if r.status_code in (200, 201):
    d = r.json()
    cap = d.get("capacity_impact", {})
    print(f"    simulation_id = {d.get('simulation_id')}")
    print(f"    overall_risk  = {d.get('overall_risk_level')}")
    print(f"    months_in_deficit = {d.get('months_in_deficit')}")
    print(f"    total_income_loss = Rs {d.get('total_income_loss', 0):,.0f}")
    print(f"    emi_capacity: original=Rs {cap.get('original_recommended_emi', 0):,.0f}  stressed=Rs {cap.get('stressed_recommended_emi', 0):,.0f}")
    print(f"    can_still_repay = {cap.get('can_still_repay')}")
    print(f"    recommendations: {len(d.get('recommendations', []))}")
    for rec in d.get("recommendations", [])[:2]:
        print(f"      - {rec.get('recommendation', '')[:100]}")
else:
    print("    Error:", r.text[:400])
