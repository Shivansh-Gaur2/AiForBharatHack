"""
Simulates the full app user journey:
  Field officer onboards wheat farmer Ramesh Kumar in Haryana,
  records cashflow, gets AI guidance for Rs 80k loan,
  tracks the disbursed loan, records repayments,
  runs a drought stress test, and monitors for early warnings.
"""
import httpx, sys

H = {"Content-Type": "application/json", "X-Skip-Auth": "true"}
B = "http://127.0.0.1"
ok: list[str] = []
err: list[str] = []


def chk(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        ok.append(label)
        print(f"  OK    {label}")
    else:
        err.append(label)
        print(f"  FAIL  {label}  {detail}")


def section(title: str) -> None:
    print()
    print("─" * 62)
    print(f"  {title}")
    print("─" * 62)


# ═══════════════════════════════════════════════════════════════
# USER STORY: Ramesh Kumar — wheat/paddy farmer, Karnal, Haryana
# Wants Rs 80,000 KCC loan for rabi wheat season
# ═══════════════════════════════════════════════════════════════

section("STEP 1 — Field officer creates borrower profile")

r = httpx.post(f"{B}:8001/api/v1/profiles", headers=H, json={
    "personal_info": {
        "name": "Ramesh Kumar", "age": 42, "gender": "M",
        "district": "Karnal", "state": "Haryana", "dependents": 4,
    },
    "livelihood_info": {
        "primary_occupation": "FARMER",
        "secondary_occupations": ["AGRICULTURAL_LABORER"],
        "land_holding": {
            "total_acres": 5.0, "irrigated_acres": 3.5,
            "rain_fed_acres": 1.5, "ownership_type": "OWNED",
        },
        "crop_patterns": [
            {"crop_name": "Wheat",  "season": "RABI",   "area_acres": 3.0, "expected_yield_quintals": 60, "expected_price_per_quintal": 2200},
            {"crop_name": "Paddy",  "season": "KHARIF", "area_acres": 2.0, "expected_yield_quintals": 40, "expected_price_per_quintal": 1900},
        ],
        "livestock": [{"animal_type": "CATTLE", "count": 2}],
        "migration_patterns": [],
    },
    "income_records": [],
    "expense_records": [],
}, timeout=10)
chk("Create profile (201)", r.status_code == 201, r.text[:120])
pid = r.json()["profile_id"]
print(f"  profile_id = {pid[:8]}...")

r2 = httpx.get(f"{B}:8001/api/v1/profiles/{pid}", headers=H, timeout=5)
chk("GET /profiles/{profileId} -> 200", r2.status_code == 200)
chk("Name persisted correctly", r2.json()["personal_info"]["name"] == "Ramesh Kumar")

# ═══════════════════════════════════════════════════════════════
section("STEP 2 — Record 12 months of cashflow (2025)")

# Harvest income spikes Apr (wheat) and Nov (paddy), lean the rest
monthly = [
    (1,  6_000,  9_500),
    (2,  5_500,  9_000),
    (3,  4_000,  8_500),
    (4, 92_000, 12_000),  # wheat harvest
    (5,  7_000,  9_000),
    (6,  6_000,  9_500),
    (7,  5_500,  9_000),
    (8,  6_500,  9_500),
    (9,  5_000,  9_000),
    (10, 8_000, 10_000),
    (11,58_000, 12_000),  # paddy harvest
    (12, 6_500,  9_500),
]
cf_errors = 0
for mo, infl, outfl in monthly:
    ri = httpx.post(f"{B}:8004/api/v1/cashflow/records", headers=H, json={
        "profile_id": pid, "category": "CROP_INCOME", "direction": "INFLOW",
        "amount": infl, "month": mo, "year": 2025,
    }, timeout=5)
    ro = httpx.post(f"{B}:8004/api/v1/cashflow/records", headers=H, json={
        "profile_id": pid, "category": "HOUSEHOLD", "direction": "OUTFLOW",
        "amount": outfl, "month": mo, "year": 2025,
    }, timeout=5)
    if ri.status_code not in (200, 201):
        cf_errors += 1
        print(f"  INFLOW error month={mo}: {ri.status_code} {ri.text[:120]}")
    if ro.status_code not in (200, 201):
        cf_errors += 1
        print(f"  OUTFLOW error month={mo}: {ro.status_code} {ro.text[:120]}")

chk("Record 24 cashflow entries — 0 errors", cf_errors == 0)

# ═══════════════════════════════════════════════════════════════
section("STEP 3 — Generate 12-month cashflow forecast")

rf = httpx.post(f"{B}:8004/api/v1/cashflow/forecast", headers=H, json={
    "profile_id": pid, "horizon_months": 12,
}, timeout=20)
chk("POST /cashflow/forecast -> 201", rf.status_code == 201, rf.text[:100])
cf_data = rf.json()
fid = cf_data.get("forecast_id", "")
chk("forecast_id present", bool(fid))
chk("12 monthly_projections", len(cf_data.get("monthly_projections", [])) == 12)
chk("seasonal_patterns present", len(cf_data.get("seasonal_patterns", [])) > 0)

if cf_data.get("monthly_projections"):
    mp = cf_data["monthly_projections"][0]
    chk("projection.projected_inflow", "projected_inflow" in mp)
    chk("projection.projected_outflow", "projected_outflow" in mp)
    chk("projection.net_cash_flow", "net_cash_flow" in mp)
    avg_net = sum(p["net_cash_flow"] for p in cf_data["monthly_projections"]) / 12
    print(f"  avg monthly net = Rs {avg_net:,.0f}")

# ═══════════════════════════════════════════════════════════════
section("STEP 4 — Risk assessment")

rr = httpx.post(f"{B}:8003/api/v1/risk/assess", headers=H, json={
    "profile_id": pid,
    "annual_income": 210_000,
    "monthly_obligations": 0,
    "total_assets": 500_000,
    "total_liabilities": 0,
}, timeout=10)
chk("POST /risk/assess -> 201", rr.status_code == 201, rr.text[:120])
risk = rr.json()
chk("risk_category present", "risk_category" in risk)
chk("risk_score present", "risk_score" in risk)
print(f"  risk = {risk.get('risk_category')}  score = {risk.get('risk_score')}")

# ═══════════════════════════════════════════════════════════════
section("STEP 5 — AI credit guidance for Rs 80,000 wheat loan (cross-service)")

rg = httpx.post(f"{B}:8006/api/v1/guidance/generate", headers=H, json={
    "profile_id": pid,
    "loan_purpose": "CROP_CULTIVATION",
    "requested_amount": 80_000,
    "tenure_months": 12,
    "interest_rate_annual": 9.0,
}, timeout=30)
chk("POST /guidance/generate -> 201", rg.status_code == 201, rg.text[:200])
g = rg.json()
ot  = g.get("optimal_timing") or {}
st  = g.get("suggested_terms") or {}
rs2 = g.get("risk_summary") or {}
exp = g.get("explanation") or {}
alts = g.get("alternative_options", [])

# Frontend field-shape checks
chk("expires_at (not valid_until)", "expires_at" in g and "valid_until" not in g)
chk("optimal_timing.expected_surplus", "expected_surplus" in ot)
chk("optimal_timing.suitability", "suitability" in ot)
chk("suggested_terms.tenure_months", "tenure_months" in st)
chk("suggested_terms.interest_rate_max_pct", "interest_rate_max_pct" in st)
chk("suggested_terms.emi_amount", "emi_amount" in st)
chk("suggested_terms.total_repayment", "total_repayment" in st)
chk("suggested_terms.source_recommendation", "source_recommendation" in st)
chk("risk_summary.key_risk_factors (not key_risks)", "key_risk_factors" in rs2 and "key_risks" not in rs2)
chk("risk_summary.dti_ratio", "dti_ratio" in rs2)
chk("risk_summary.repayment_capacity_pct", "repayment_capacity_pct" in rs2)
chk("explanation.confidence (not key_assumptions)", "confidence" in exp and "key_assumptions" not in exp)
if alts:
    chk("alt.advantages (not pros)", "advantages" in alts[0] and "pros" not in alts[0])
    chk("alt.estimated_amount (not amount_range)", "estimated_amount" in alts[0] and "amount_range" not in alts[0])
if exp.get("reasoning_steps"):
    step = exp["reasoning_steps"][0]
    chk("step.step_number (not step)", "step_number" in step and "step" not in step)
    chk("step.observation (not analysis)", "observation" in step and "analysis" not in step)

emi_amount = int(st.get("emi_amount", 7_000))
print(f"  Optimal: {ot.get('start_month')}/{ot.get('start_year')}  suitability={ot.get('suitability')}")
print(f"  expected_surplus = Rs {ot.get('expected_surplus', 0):,.0f}")
print(f"  EMI = Rs {emi_amount:,}  tenure = {st.get('tenure_months')} months")
print(f"  Confidence = {exp.get('confidence')}")
print(f"  AI: {exp.get('summary', '')[:130]}...")

# ═══════════════════════════════════════════════════════════════
section("STEP 6 — Loan disbursed — create tracking record")

rl = httpx.post(f"{B}:8002/api/v1/loans", headers=H, json={
    "profile_id": pid,
    "lender_name": "Punjab National Bank",
    "source_type": "FORMAL",
    "terms": {
        "principal": 80_000,
        "interest_rate_annual": 9.0,
        "tenure_months": 12,
        "emi_amount": emi_amount,
    },
    "disbursement_date": "2026-01-15T00:00:00",
    "purpose": "Wheat crop cultivation — Rabi 2026",
}, timeout=10)
chk("POST /loans nested terms -> 201", rl.status_code == 201, rl.text[:120])
loan = rl.json()
tid = loan.get("tracking_id", "")
chk("tracking_id returned", bool(tid))
chk("terms.principal = 80000", loan["terms"]["principal"] == 80_000)
chk("terms.interest_rate_annual = 9.0", loan["terms"]["interest_rate_annual"] == 9.0)
chk("status = ACTIVE", loan.get("status") == "ACTIVE")
print(f"  tracking_id = {tid[:8]}...")

# ═══════════════════════════════════════════════════════════════
section("STEP 7 — Record 3 monthly EMI repayments")

rep_errors = 0
for dt in ["2026-02-15T00:00:00", "2026-03-15T00:00:00", "2026-04-15T00:00:00"]:
    rp = httpx.post(f"{B}:8002/api/v1/loans/{tid}/repayments", headers=H, json={
        "date": dt, "amount": emi_amount, "is_late": False, "days_overdue": 0,
    }, timeout=5)
    if rp.status_code not in (200, 201):
        rep_errors += 1

chk("Record 3 EMIs — 0 errors", rep_errors == 0)
rl2 = httpx.get(f"{B}:8002/api/v1/loans/{tid}", headers=H, timeout=5)
chk("GET /loans/{trackingId} -> 200", rl2.status_code == 200)
loan2 = rl2.json()
chk("total_repaid > 0", loan2.get("total_repaid", 0) > 0)
chk("repayment_count = 3", loan2.get("repayment_count", 0) == 3)
print(f"  total_repaid = Rs {loan2.get('total_repaid', 0):,.0f}")

# ═══════════════════════════════════════════════════════════════
section("STEP 8 — Stress test: drought cuts income 40% for 6 months")

rs_sim = httpx.post(f"{B}:8005/api/v1/early-warning/scenarios/simulate", headers=H, json={
    "profile_id": pid,
    "scenario_type": "WEATHER_IMPACT",
    "name": "Drought scenario — 40% income loss",
    "weather_adjustment": 0.6,
    "income_reduction_pct": 40.0,
    "duration_months": 6,
    "existing_monthly_obligations": emi_amount,
    "household_monthly_expense": 9_500,
}, timeout=20)
chk("POST /scenarios/simulate -> 201", rs_sim.status_code == 201, rs_sim.text[:100])
sim = rs_sim.json()
chk("simulation_id present", "simulation_id" in sim)
chk("overall_risk_level present", "overall_risk_level" in sim)
chk("months_in_deficit present", "months_in_deficit" in sim)
chk("capacity_impact.can_still_repay", "can_still_repay" in sim.get("capacity_impact", {}))
chk("recommendations returned", len(sim.get("recommendations", [])) > 0)

print(f"  Risk under drought = {sim.get('overall_risk_level')}")
print(f"  Months in deficit  = {sim.get('months_in_deficit')}")
ci = sim.get("capacity_impact", {})
print(f"  Can still repay    = {ci.get('can_still_repay')}")
print(f"  Stressed EMI cap   = Rs {ci.get('stressed_recommended_emi', 0):,.0f}")
if sim.get("recommendations"):
    print(f"  Top recommendation: {sim['recommendations'][0].get('recommendation', '')[:80]}")

# ═══════════════════════════════════════════════════════════════
section("STEP 9 — Early warning monitor (cross-service, uses real cashflow)")

rm = httpx.post(f"{B}:8005/api/v1/early-warning/monitor", headers=H, json={
    "profile_id": pid,
}, timeout=20)
chk("POST /monitor -> 201", rm.status_code == 201, rm.text[:100])
alert = rm.json()
chk("alert profile_id matches", alert.get("profile_id") == pid)
chk("alert status returned", alert.get("status") in ("ACTIVE", "CLEAR", "MONITORING"))
chk("risk_factors present", "risk_factors" in alert)
print(f"  Alert status = {alert.get('status')}  severity = {alert.get('severity')}")

# ═══════════════════════════════════════════════════════════════
section("STEP 10 — Record data-sharing consent")

rc = httpx.post(f"{B}:8007/api/v1/security/consent", headers=H, json={
    "profile_id": pid, "purpose": "CREDIT_ASSESSMENT",
}, timeout=10)
chk("POST /security/consent -> 201", rc.status_code == 201, rc.text[:100])
consent = rc.json()
chk("consent_id present", "consent_id" in consent)
chk("status = GRANTED", consent.get("status") == "GRANTED")
print(f"  consent_id = {consent.get('consent_id', '')[:8]}...")

# ═══════════════════════════════════════════════════════════════
print()
print("═" * 62)
print("  USER JOURNEY SIMULATION COMPLETE")
print(f"  {len(ok)} PASSED  |  {len(err)} FAILED  |  {len(ok)+len(err)} total checks")
if err:
    print()
    print("  FAILED:")
    for e in err:
        print(f"    ✗ {e}")
    sys.exit(1)
else:
    print("  ✓  All checks passed — app wiring is correct end-to-end")
print("═" * 62)
