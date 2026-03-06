"""
Additional scenario simulations covering edge cases, lifecycle flows,
multi-borrower profiles, and cross-service operations.

Scenarios:
  A — Meena Devi: SHG microloan (semi-formal, low-income, stable borrower)
  B — Suresh Patel: Over-indebted tenant farmer (HIGH risk, debt exposure)
  C — Full loan lifecycle: disburse -> repay all -> close
  D — Multi-scenario comparison: drought vs price-crash vs flood side-by-side
  E — Security audit trail: access log + data lineage + usage summary
  F — Guidance lifecycle: generate -> retrieve explain -> supersede
  G — Alert lifecycle: create -> escalate -> acknowledge -> resolve
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
    print("=" * 62)
    print(f"  {title}")
    print("=" * 62)


def subsection(title: str) -> None:
    print(f"  -- {title}")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — typical 12-month cashflow baselines
# ─────────────────────────────────────────────────────────────────────────────

def baseline_projections(monthly_inflow: float, monthly_outflow: float) -> list[dict]:
    """Produce a flat 12-month baseline for direct endpoints."""
    return [
        {"month": m, "year": 2025, "inflow": monthly_inflow, "outflow": monthly_outflow}
        for m in range(1, 13)
    ]


def harvest_projections() -> list[dict]:
    """Seasonal Haryana wheat/paddy cashflow (same as journey test)."""
    months = [
        (1,  6_000,  9_500), (2,  5_500,  9_000), (3,  4_000,  8_500),
        (4, 92_000, 12_000), (5,  7_000,  9_000), (6,  6_000,  9_500),
        (7,  5_500,  9_000), (8,  6_500,  9_500), (9,  5_000,  9_000),
        (10, 8_000, 10_000), (11,58_000, 12_000), (12, 6_500,  9_500),
    ]
    return [{"month": m, "year": 2025, "inflow": i, "outflow": o} for m, i, o in months]


# ═════════════════════════════════════════════════════════════════════════════
# SCENARIO A — Meena Devi: SHG member, Uttar Pradesh
#   Stable but low income (remittance + goat rearing), Rs 10k microloan
# ═════════════════════════════════════════════════════════════════════════════
section("SCENARIO A — Meena Devi: SHG microloan (semi-formal)")

ra = httpx.post(f"{B}:8001/api/v1/profiles", headers=H, json={
    "personal_info": {
        "name": "Meena Devi", "age": 35, "gender": "F",
        "district": "Sitapur", "state": "Uttar Pradesh", "dependents": 3,
    },
    "livelihood_info": {
        "primary_occupation": "SHG_MEMBER",
        "secondary_occupations": ["LIVESTOCK_REARER"],
        "land_holding": {
            "total_acres": 0.5, "irrigated_acres": 0.0,
            "rain_fed_acres": 0.5, "ownership_type": "LEASED",
        },
        "crop_patterns": [],
        "livestock": [
            {"animal_type": "GOAT", "count": 8},
        ],
        "migration_patterns": [],
    },
    "income_records": [],
    "expense_records": [],
}, timeout=10)
chk("A1: Create Meena Devi profile (201)", ra.status_code == 201, ra.text[:120])
mid = ra.json()["profile_id"]
print(f"  profile_id = {mid[:8]}...")

# Stable low-income cashflow: Rs 4,500/mo inflow (remittance + goats), Rs 4,200/mo outflow
cf_a_errors = 0
for mo in range(1, 13):
    inflow  = 3_000 + (2_000 if mo % 3 == 0 else 0)  # quarterly goat sale bump
    outflow = 4_200
    ri = httpx.post(f"{B}:8004/api/v1/cashflow/records", headers=H, json={
        "profile_id": mid, "category": "REMITTANCE", "direction": "INFLOW",
        "amount": 3_000, "month": mo, "year": 2025,
    }, timeout=5)
    if ri.status_code not in (200, 201):
        cf_a_errors += 1
    if mo % 3 == 0:
        rl2 = httpx.post(f"{B}:8004/api/v1/cashflow/records", headers=H, json={
            "profile_id": mid, "category": "LIVESTOCK_INCOME", "direction": "INFLOW",
            "amount": 2_000, "month": mo, "year": 2025,
        }, timeout=5)
        if rl2.status_code not in (200, 201):
            cf_a_errors += 1
    ro = httpx.post(f"{B}:8004/api/v1/cashflow/records", headers=H, json={
        "profile_id": mid, "category": "HOUSEHOLD", "direction": "OUTFLOW",
        "amount": outflow, "month": mo, "year": 2025,
    }, timeout=5)
    if ro.status_code not in (200, 201):
        cf_a_errors += 1
chk("A2: Record Meena's cashflow (0 errors)", cf_a_errors == 0)

# Direct risk score — stable income, no debts, low land → MEDIUM
ra_risk = httpx.post(f"{B}:8003/api/v1/risk/score", headers=H, json={
    "profile_id": mid,
    "income_volatility_cv": 0.15,
    "annual_income": 44_000,
    "months_below_average": 2,
    "debt_to_income_ratio": 0.0,
    "total_outstanding": 0,
    "active_loan_count": 0,
    "credit_utilisation": 0.0,
    "on_time_repayment_ratio": 1.0,
    "has_defaults": False,
    "seasonal_variance": 0.1,
    "crop_diversification_index": 0.0,
    "weather_risk_score": 0.4,
    "market_risk_score": 0.3,
    "dependents": 3,
    "age": 35,
    "has_irrigation": False,
}, timeout=10)
chk("A3: Direct risk score (201)", ra_risk.status_code == 201, ra_risk.text[:120])
a_risk = ra_risk.json()
chk("A3: risk_category in LOW/MEDIUM", a_risk.get("risk_category") in ("LOW", "MEDIUM"))
print(f"  risk = {a_risk.get('risk_category')}  score = {a_risk.get('risk_score')}")

# Direct guidance — Rs 10,000 microloan at 12% from SHG
ra_guid = httpx.post(f"{B}:8006/api/v1/guidance/generate/direct", headers=H, json={
    "profile_id": mid,
    "loan_purpose": "WORKING_CAPITAL",
    "requested_amount": 10_000,
    "tenure_months": 12,
    "interest_rate_annual": 12.0,
    "projections": baseline_projections(3_000, 4_200),
    "risk_category": a_risk.get("risk_category", "MEDIUM"),
    "risk_score": a_risk.get("risk_score", 500),
    "dti_ratio": 0.0,
    "existing_obligations": 0,
}, timeout=30)
chk("A4: Direct guidance for microloan (201)", ra_guid.status_code == 201, ra_guid.text[:200])
ag = ra_guid.json()
a_guid_id = ag.get("guidance_id", "")
chk("A4: guidance_id present", bool(a_guid_id))
chk("A4: expires_at present", "expires_at" in ag)
print(f"  guidance_id = {a_guid_id[:8]}...")
print(f"  EMI = Rs {ag.get('suggested_terms', {}).get('emi_amount', 0):,.0f}  confidence = {ag.get('explanation', {}).get('confidence')}")

# Consent for this borrower (SHG purpose)
ra_con = httpx.post(f"{B}:8007/api/v1/security/consent", headers=H, json={
    "profile_id": mid, "purpose": "DATA_SHARING_LENDER", "granted_by": "field_officer_1",
}, timeout=10)
chk("A5: Consent granted (DATA_SHARING_LENDER)", ra_con.status_code == 201, ra_con.text[:100])
a_consent_id = ra_con.json().get("consent_id", "")

# Check consent is active
ra_check = httpx.post(f"{B}:8007/api/v1/security/consent/check", headers=H, json={
    "profile_id": mid, "purpose": "DATA_SHARING_LENDER",
}, timeout=5)
chk("A6: Consent check returns 200", ra_check.status_code == 200)
chk("A6: has_consent = True", ra_check.json().get("has_consent") is True)
print(f"  SHG consent active: {ra_check.json().get('has_consent')}")


# ═════════════════════════════════════════════════════════════════════════════
# SCENARIO B — Suresh Patel: over-indebted tenant farmer
#   HIGH risk: 2 active loans, DTI 0.72, 1 missed payment, Rs 50k more?
# ═════════════════════════════════════════════════════════════════════════════
section("SCENARIO B — Suresh Patel: high-risk / over-indebted borrower")

rb = httpx.post(f"{B}:8001/api/v1/profiles", headers=H, json={
    "personal_info": {
        "name": "Suresh Patel", "age": 50, "gender": "M",
        "district": "Vidisha", "state": "Madhya Pradesh", "dependents": 6,
    },
    "livelihood_info": {
        "primary_occupation": "TENANT_FARMER",
        "secondary_occupations": [],
        "land_holding": {
            "total_acres": 3.0, "irrigated_acres": 0.5,
            "rain_fed_acres": 2.5, "ownership_type": "LEASED",
        },
        "crop_patterns": [
            {"crop_name": "Soybean", "season": "KHARIF", "area_acres": 3.0,
             "expected_yield_quintals": 18, "expected_price_per_quintal": 3800},
        ],
        "livestock": [],
        "migration_patterns": [],
    },
    "income_records": [],
    "expense_records": [],
}, timeout=10)
chk("B1: Create Suresh profile (201)", rb.status_code == 201, rb.text[:120])
spid = rb.json()["profile_id"]
print(f"  profile_id = {spid[:8]}...")

# Direct risk score — high DTI, has defaults, multiple loans
rb_risk = httpx.post(f"{B}:8003/api/v1/risk/score", headers=H, json={
    "profile_id": spid,
    "income_volatility_cv": 0.55,
    "annual_income": 68_400,
    "months_below_average": 6,
    "debt_to_income_ratio": 0.72,
    "total_outstanding": 95_000,
    "active_loan_count": 2,
    "credit_utilisation": 0.85,
    "on_time_repayment_ratio": 0.67,
    "has_defaults": True,
    "seasonal_variance": 0.4,
    "crop_diversification_index": 0.1,
    "weather_risk_score": 0.7,
    "market_risk_score": 0.6,
    "dependents": 6,
    "age": 50,
    "has_irrigation": False,
}, timeout=10)
chk("B2: Direct risk score (201)", rb_risk.status_code == 201, rb_risk.text[:120])
b_risk = rb_risk.json()
chk("B2: risk_category = HIGH", b_risk.get("risk_category") == "HIGH")
print(f"  risk = {b_risk.get('risk_category')}  score = {b_risk.get('risk_score')}")

# Create two active loans showing existing debt load
rb_loan1 = httpx.post(f"{B}:8002/api/v1/loans", headers=H, json={
    "profile_id": spid,
    "lender_name": "Grameen Bank",
    "source_type": "SEMI_FORMAL",
    "terms": {"principal": 45_000, "interest_rate_annual": 18.0, "tenure_months": 24, "emi_amount": 2_250},
    "disbursement_date": "2024-06-01T00:00:00",
    "purpose": "Kharif seed + fertiliser",
}, timeout=10)
chk("B3: Loan 1 created (201)", rb_loan1.status_code == 201, rb_loan1.text[:100])
b_tid1 = rb_loan1.json().get("tracking_id", "")

rb_loan2 = httpx.post(f"{B}:8002/api/v1/loans", headers=H, json={
    "profile_id": spid,
    "lender_name": "Local moneylender",
    "source_type": "INFORMAL",
    "terms": {"principal": 50_000, "interest_rate_annual": 36.0, "tenure_months": 12, "emi_amount": 5_000},
    "disbursement_date": "2025-01-01T00:00:00",
    "purpose": "Household emergency",
}, timeout=10)
chk("B4: Loan 2 created (informal, 36%)", rb_loan2.status_code == 201, rb_loan2.text[:100])
b_tid2 = rb_loan2.json().get("tracking_id", "")

# List borrower loans
rb_list = httpx.get(f"{B}:8002/api/v1/loans/borrower/{spid}", headers=H, timeout=5)
chk("B5: GET /loans/borrower/{id} -> 200", rb_list.status_code == 200)
chk("B5: 2 loans in list", rb_list.json().get("count", 0) == 2)
print(f"  active loans count = {rb_list.json().get('count')}")

# Debt exposure check
rb_exp = httpx.get(f"{B}:8002/api/v1/loans/borrower/{spid}/exposure",
    params={"annual_income": 68_400}, headers=H, timeout=5)
chk("B6: GET /exposure -> 200", rb_exp.status_code == 200, rb_exp.text[:100])
exp = rb_exp.json()
chk("B6: total_outstanding > 0", exp.get("total_outstanding", 0) > 0)
chk("B6: debt_to_income_ratio present", "debt_to_income_ratio" in exp)
print(f"  total outstanding = Rs {exp.get('total_outstanding', 0):,.0f}")
print(f"  DTI ratio = {exp.get('debt_to_income_ratio', 0):.2f}")

# Direct alert — high DTI + missed payment → should be CRITICAL/HIGH severity
rb_alert = httpx.post(f"{B}:8005/api/v1/early-warning/alerts/direct", headers=H, json={
    "profile_id": spid,
    "dti_ratio": 0.72,
    "missed_payments": 1,
    "days_overdue_avg": 18.0,
    "recent_surplus_trend": [8000, 4000, -1000, -5000],
    "risk_category": "HIGH",
}, timeout=15)
chk("B7: Direct alert (201)", rb_alert.status_code == 201, rb_alert.text[:120])
b_alert = rb_alert.json()
b_alert_id = b_alert.get("alert_id", "")
chk("B7: severity in WARNING/HIGH/CRITICAL",
    b_alert.get("severity") in ("WARNING", "HIGH", "CRITICAL"))
print(f"  alert severity = {b_alert.get('severity')}  status = {b_alert.get('status')}")


# ═════════════════════════════════════════════════════════════════════════════
# SCENARIO C — Full loan lifecycle: disburse → all EMIs → CLOSED
# ═════════════════════════════════════════════════════════════════════════════
section("SCENARIO C — Full loan lifecycle: disburse -> repay all -> close")

# Re-use a fresh minimal profile
rc_prof = httpx.post(f"{B}:8001/api/v1/profiles", headers=H, json={
    "personal_info": {
        "name": "Anita Sharma", "age": 29, "gender": "F",
        "district": "Pune", "state": "Maharashtra", "dependents": 2,
    },
    "livelihood_info": {
        "primary_occupation": "SMALL_TRADER",
        "secondary_occupations": [],
        "land_holding": {
            "total_acres": 0.0, "irrigated_acres": 0.0,
            "rain_fed_acres": 0.0, "ownership_type": "LEASED",
        },
        "crop_patterns": [],
        "livestock": [],
        "migration_patterns": [],
    },
    "income_records": [],
    "expense_records": [],
}, timeout=10)
chk("C1: Create Anita profile (201)", rc_prof.status_code == 201, rc_prof.text[:120])
cpid = rc_prof.json()["profile_id"]
print(f"  profile_id = {cpid[:8]}...")

# Rs 15,000 / 3-month loan at 14% — 3 equal payments of Rs 5,000
rc_loan = httpx.post(f"{B}:8002/api/v1/loans", headers=H, json={
    "profile_id": cpid,
    "lender_name": "Jana Small Finance Bank",
    "source_type": "FORMAL",
    "terms": {
        "principal": 15_000,
        "interest_rate_annual": 14.0,
        "tenure_months": 3,
        "emi_amount": 5_000,
    },
    "disbursement_date": "2026-01-05T00:00:00",
    "purpose": "Stock purchase for festival season",
}, timeout=10)
chk("C2: 3-month loan created (201)", rc_loan.status_code == 201, rc_loan.text[:120])
ctid = rc_loan.json().get("tracking_id", "")
chk("C2: status = ACTIVE on creation", rc_loan.json().get("status") == "ACTIVE")

# Record all 3 EMIs
c_rep_errors = 0
for dt in ["2026-02-05T00:00:00", "2026-03-05T00:00:00", "2026-04-05T00:00:00"]:
    rp = httpx.post(f"{B}:8002/api/v1/loans/{ctid}/repayments", headers=H, json={
        "date": dt, "amount": 5_000, "is_late": False, "days_overdue": 0,
    }, timeout=5)
    if rp.status_code not in (200, 201):
        c_rep_errors += 1
        print(f"  EMI error: {rp.status_code} {rp.text[:100]}")
chk("C3: All 3 EMIs recorded (0 errors)", c_rep_errors == 0)

# Close the loan
rc_close = httpx.patch(f"{B}:8002/api/v1/loans/{ctid}/status", headers=H, json={
    "status": "CLOSED",
}, timeout=5)
chk("C4: PATCH status -> CLOSED (200)", rc_close.status_code == 200, rc_close.text[:100])

# Verify final state
rc_final = httpx.get(f"{B}:8002/api/v1/loans/{ctid}", headers=H, timeout=5)
chk("C5: GET loan -> 200", rc_final.status_code == 200)
final = rc_final.json()
chk("C5: status = CLOSED", final.get("status") == "CLOSED")
chk("C5: repayment_count = 3", final.get("repayment_count", 0) == 3)
chk("C5: total_repaid = 15000", final.get("total_repaid", 0) == 15_000)
print(f"  final status = {final.get('status')}  repaid = Rs {final.get('total_repaid', 0):,.0f}")


# ═════════════════════════════════════════════════════════════════════════════
# SCENARIO D — Side-by-side comparison: drought vs price-crash vs flood
# ═════════════════════════════════════════════════════════════════════════════
section("SCENARIO D — Multi-scenario comparison: drought / price-crash / flood")

# Use a seasonal borrower profile (new, with cashflow already in DB via STEP 2
# we need a profile that has cashflow — create + upload quickly)
rd_prof = httpx.post(f"{B}:8001/api/v1/profiles", headers=H, json={
    "personal_info": {
        "name": "Vijay Reddy", "age": 38, "gender": "M",
        "district": "Nalgonda", "state": "Telangana", "dependents": 4,
    },
    "livelihood_info": {
        "primary_occupation": "FARMER",
        "secondary_occupations": [],
        "land_holding": {
            "total_acres": 6.0, "irrigated_acres": 4.0,
            "rain_fed_acres": 2.0, "ownership_type": "OWNED",
        },
        "crop_patterns": [
            {"crop_name": "Cotton", "season": "KHARIF", "area_acres": 4.0,
             "expected_yield_quintals": 20, "expected_price_per_quintal": 6200},
            {"crop_name": "Jowar",  "season": "RABI",   "area_acres": 2.0,
             "expected_yield_quintals": 15, "expected_price_per_quintal": 2400},
        ],
        "livestock": [],
        "migration_patterns": [],
    },
    "income_records": [],
    "expense_records": [],
}, timeout=10)
chk("D1: Create Vijay profile (201)", rd_prof.status_code == 201, rd_prof.text[:120])
vpid = rd_prof.json()["profile_id"]

# Direct compare — no need to upload cashflow records, use inline baseline
# Cotton/Jowar farmer: high Oct-Nov, moderate Feb-Mar, lean rest
cotton_baseline = [
    {"month": 1,  "year": 2025, "inflow":  8_000, "outflow": 11_000},
    {"month": 2,  "year": 2025, "inflow": 12_000, "outflow": 10_000},
    {"month": 3,  "year": 2025, "inflow":  7_000, "outflow": 10_000},
    {"month": 4,  "year": 2025, "inflow":  6_500, "outflow": 10_500},
    {"month": 5,  "year": 2025, "inflow":  6_000, "outflow": 11_000},
    {"month": 6,  "year": 2025, "inflow":  5_500, "outflow": 10_500},
    {"month": 7,  "year": 2025, "inflow":  7_000, "outflow": 12_000},
    {"month": 8,  "year": 2025, "inflow":  8_500, "outflow": 13_000},
    {"month": 9,  "year": 2025, "inflow":  9_000, "outflow": 13_500},
    {"month": 10, "year": 2025, "inflow": 85_000, "outflow": 14_000},
    {"month": 11, "year": 2025, "inflow": 62_000, "outflow": 11_000},
    {"month": 12, "year": 2025, "inflow":  7_500, "outflow": 10_500},
]

rd_cmp = httpx.post(f"{B}:8005/api/v1/early-warning/scenarios/compare/direct", headers=H, json={
    "profile_id": vpid,
    "baseline_projections": cotton_baseline,
    "existing_monthly_obligations": 4_500,
    "household_monthly_expense": 11_000,
    "scenarios": [
        {
            "scenario_type": "WEATHER_IMPACT",
            "name": "Drought — 50% income loss for 5mo",
            "weather_adjustment": 0.5,
            "income_reduction_pct": 50.0,
            "duration_months": 5,
            "existing_monthly_obligations": 4_500,
            "household_monthly_expense": 11_000,
        },
        {
            "scenario_type": "MARKET_VOLATILITY",
            "name": "Cotton price crash — 35% drop",
            "market_price_change_pct": -35,
            "income_reduction_pct": 35.0,
            "duration_months": 6,
            "existing_monthly_obligations": 4_500,
            "household_monthly_expense": 11_000,
        },
        {
            "scenario_type": "WEATHER_IMPACT",
            "name": "Flood — 70% income loss for 3mo",
            "weather_adjustment": 0.3,
            "income_reduction_pct": 70.0,
            "duration_months": 3,
            "existing_monthly_obligations": 4_500,
            "household_monthly_expense": 11_000,
        },
    ],
}, timeout=30)
chk("D2: /compare/direct (201)", rd_cmp.status_code == 201, rd_cmp.text[:200])
cmp = rd_cmp.json()
chk("D2: 3 results returned", len(cmp.get("results", [])) == 3)
chk("D2: each result has simulation_id", all("simulation_id" in r for r in cmp.get("results", [])))
chk("D2: each result has overall_risk_level", all("overall_risk_level" in r for r in cmp.get("results", [])))

print(f"  Scenario comparison results (Vijay Reddy — Telangana cotton farmer):")
for res in cmp.get("results", []):
    ci2 = res.get("capacity_impact", {})
    print(f"    {res.get('scenario_name', 'n/a'):<45} "
          f"risk={res.get('overall_risk_level'):<8} "
          f"deficit_months={res.get('months_in_deficit')}  "
          f"can_repay={ci2.get('can_still_repay')}")

# Retrieve one simulation by ID to confirm persistence
sim_id = cmp["results"][0]["simulation_id"]
rd_get = httpx.get(f"{B}:8005/api/v1/early-warning/scenarios/{sim_id}", headers=H, timeout=5)
chk("D3: GET /scenarios/{id} -> 200", rd_get.status_code == 200)
chk("D3: simulation_id matches", rd_get.json().get("simulation_id") == sim_id)

# Check simulation history for this profile
rd_hist = httpx.get(
    f"{B}:8005/api/v1/early-warning/scenarios/profile/{vpid}/history",
    headers=H, timeout=5)
chk("D4: GET /scenarios/profile/{id}/history -> 200", rd_hist.status_code == 200)
chk("D4: at least 3 simulations in history", rd_hist.json().get("count", 0) >= 3)


# ═════════════════════════════════════════════════════════════════════════════
# SCENARIO E — Security audit trail: log access + data lineage + usage summary
# ═════════════════════════════════════════════════════════════════════════════
section("SCENARIO E — Security audit trail: access log + lineage + usage summary")

# Use Meena Devi (mid) established in Scenario A
subsection("Logging 3 data-access events for Meena Devi")
audit_errors = 0
for svc_name, res_type in [
    ("guidance_service", "CASHFLOW"),
    ("risk_assessment",  "PROFILE"),
    ("loan_tracker",     "RISK_ASSESSMENT"),
]:
    re_audit = httpx.post(f"{B}:8007/api/v1/security/audit/access", headers=H, json={
        "actor_id": "field_officer_1",
        "resource_type": res_type,
        "resource_id": mid,
        "profile_id": mid,
        "details": {"service": svc_name, "action": "READ"},
        "ip_address": "127.0.0.1",
    }, timeout=5)
    if re_audit.status_code not in (200, 201):
        audit_errors += 1
        print(f"  audit error: {re_audit.status_code} {re_audit.text[:80]}")
chk("E1: 3 audit access events logged", audit_errors == 0)

# Fetch audit log
re_log = httpx.get(f"{B}:8007/api/v1/security/audit/profile/{mid}", headers=H, timeout=5)
chk("E2: GET /audit/profile/{id} -> 200", re_log.status_code == 200)
log_data = re_log.json()
chk("E2: audit log count >= 3", log_data.get("count", 0) >= 3)
print(f"  audit entries = {log_data.get('count')}")

# Record data lineage: cashflow_service -> guidance_service (consent-backed)
re_lin = httpx.post(f"{B}:8007/api/v1/security/lineage", headers=H, json={
    "profile_id": mid,
    "data_category": "FINANCIAL",
    "source_service": "cashflow_service",
    "target_service": "guidance_service",
    "action": "TRANSFER",
    "fields_accessed": ["monthly_projections", "seasonal_patterns"],
    "purpose": "credit_guidance_generation",
    "consent_id": a_consent_id,
    "actor_id": "guidance_service",
}, timeout=5)
chk("E3: Record data lineage (201)", re_lin.status_code == 201, re_lin.text[:100])
lin = re_lin.json()
chk("E3: lineage has record_id", "record_id" in lin)
chk("E3: source_service = cashflow_service", lin.get("source_service") == "cashflow_service")

# Fetch lineage records
re_lget = httpx.get(f"{B}:8007/api/v1/security/lineage/profile/{mid}", headers=H, timeout=5)
chk("E4: GET /lineage/profile/{id} -> 200", re_lget.status_code == 200)
chk("E4: lineage count >= 1", re_lget.json().get("count", 0) >= 1)

# Data usage summary
re_usage = httpx.get(f"{B}:8007/api/v1/security/usage/{mid}", headers=H, timeout=5)
chk("E5: GET /usage/{id} -> 200", re_usage.status_code == 200)
usage = re_usage.json()
chk("E5: active_consent_count >= 1", usage.get("active_consent_count", 0) >= 1)
chk("E5: active_consents list present", "active_consents" in usage)
print(f"  active consents = {usage.get('active_consent_count')}  lineage records = {re_lget.json().get('count')}")


# ═════════════════════════════════════════════════════════════════════════════
# SCENARIO F — Guidance lifecycle: generate → explain → supersede → active list
# ═════════════════════════════════════════════════════════════════════════════
section("SCENARIO F — Guidance lifecycle: generate -> explain -> supersede")

# Fresh borrower to have a clean guidance history
rf_prof = httpx.post(f"{B}:8001/api/v1/profiles", headers=H, json={
    "personal_info": {
        "name": "Priya Iyer", "age": 32, "gender": "F",
        "district": "Salem", "state": "Tamil Nadu", "dependents": 2,
    },
    "livelihood_info": {
        "primary_occupation": "FARMER",
        "secondary_occupations": [],
        "land_holding": {
            "total_acres": 2.0, "irrigated_acres": 2.0,
            "rain_fed_acres": 0.0, "ownership_type": "OWNED",
        },
        "crop_patterns": [
            {"crop_name": "Sugarcane", "season": "KHARIF", "area_acres": 2.0,
             "expected_yield_quintals": 500, "expected_price_per_quintal": 290},
        ],
        "livestock": [],
        "migration_patterns": [],
    },
    "income_records": [],
    "expense_records": [],
}, timeout=10)
chk("F1: Create Priya profile (201)", rf_prof.status_code == 201, rf_prof.text[:120])
ppid = rf_prof.json()["profile_id"]

# Generate first guidance (Rs 50k sugarcane input loan)
rf_g1 = httpx.post(f"{B}:8006/api/v1/guidance/generate/direct", headers=H, json={
    "profile_id": ppid,
    "loan_purpose": "CROP_CULTIVATION",
    "requested_amount": 50_000,
    "tenure_months": 12,
    "interest_rate_annual": 8.5,
    "projections": baseline_projections(12_000, 8_000),
    "risk_category": "LOW",
    "risk_score": 750.0,
    "dti_ratio": 0.0,
    "existing_obligations": 0,
}, timeout=30)
chk("F2: First guidance generated (201)", rf_g1.status_code == 201, rf_g1.text[:120])
g1_id = rf_g1.json().get("guidance_id", "")
chk("F2: guidance_id present", bool(g1_id))
print(f"  first guidance_id = {g1_id[:8]}...")

# Retrieve the guidance
rf_get = httpx.get(f"{B}:8006/api/v1/guidance/{g1_id}", headers=H, timeout=5)
chk("F3: GET /guidance/{id} -> 200", rf_get.status_code == 200)
chk("F3: returned guidance_id matches", rf_get.json().get("guidance_id") == g1_id)

# Retrieve full explanation
rf_exp = httpx.get(f"{B}:8006/api/v1/guidance/{g1_id}/explain", headers=H, timeout=10)
chk("F4: GET /guidance/{id}/explain -> 200", rf_exp.status_code == 200)
exp_data = rf_exp.json()
chk("F4: reasoning_steps present", "reasoning_steps" in exp_data or "summary" in exp_data)
print(f"  explain keys: {list(exp_data.keys())}")

# Generate second, updated guidance (she found a better scheme — Rs 60k @ 7%)
rf_g2 = httpx.post(f"{B}:8006/api/v1/guidance/generate/direct", headers=H, json={
    "profile_id": ppid,
    "loan_purpose": "CROP_CULTIVATION",
    "requested_amount": 60_000,
    "tenure_months": 12,
    "interest_rate_annual": 7.0,
    "projections": baseline_projections(12_000, 8_000),
    "risk_category": "LOW",
    "risk_score": 750.0,
    "dti_ratio": 0.0,
    "existing_obligations": 0,
}, timeout=30)
chk("F5: Second (updated) guidance generated (201)", rf_g2.status_code == 201, rf_g2.text[:120])
g2_id = rf_g2.json().get("guidance_id", "")
print(f"  second guidance_id = {g2_id[:8]}...")

# Supersede the first guidance with the second
rf_sup = httpx.post(
    f"{B}:8006/api/v1/guidance/{g1_id}/supersede",
    headers=H,
    json={"new_guidance_id": g2_id},
    timeout=5,
)
chk("F6: Supersede first guidance -> 200", rf_sup.status_code == 200, rf_sup.text[:120])

# Active guidance list — should contain g2, not g1
rf_active = httpx.get(f"{B}:8006/api/v1/guidance/profile/{ppid}/active", headers=H, timeout=5)
chk("F7: GET /profile/{id}/active -> 200", rf_active.status_code == 200)
active_ids = [g["guidance_id"] for g in rf_active.json().get("items", [])]
chk("F7: Second guidance is active", g2_id in active_ids)
chk("F7: First guidance no longer active", g1_id not in active_ids)
print(f"  active guidance IDs: {[i[:8] for i in active_ids]}")

# Full guidance history
rf_hist = httpx.get(f"{B}:8006/api/v1/guidance/profile/{ppid}/history", headers=H, timeout=5)
chk("F8: GET /profile/{id}/history -> 200", rf_hist.status_code == 200)
chk("F8: history count >= 2", rf_hist.json().get("count", 0) >= 2)
print(f"  total guidance history = {rf_hist.json().get('count')}")


# ═════════════════════════════════════════════════════════════════════════════
# SCENARIO G — Alert lifecycle: create -> escalate -> acknowledge -> resolve
# ═════════════════════════════════════════════════════════════════════════════
section("SCENARIO G — Alert lifecycle: escalate -> acknowledge -> resolve")

# Fresh profile for clean alert history
rg_prof = httpx.post(f"{B}:8001/api/v1/profiles", headers=H, json={
    "personal_info": {
        "name": "Raju Yadav", "age": 45, "gender": "M",
        "district": "Muzzafarpur", "state": "Bihar", "dependents": 5,
    },
    "livelihood_info": {
        "primary_occupation": "FARMER",
        "secondary_occupations": ["SEASONAL_MIGRANT"],
        "land_holding": {
            "total_acres": 1.5, "irrigated_acres": 0.5,
            "rain_fed_acres": 1.0, "ownership_type": "OWNED",
        },
        "crop_patterns": [
            {"crop_name": "Maize", "season": "KHARIF", "area_acres": 1.5,
             "expected_yield_quintals": 22, "expected_price_per_quintal": 1900},
        ],
        "livestock": [],
        "migration_patterns": [],
    },
    "income_records": [],
    "expense_records": [],
}, timeout=10)
chk("G1: Create Raju profile (201)", rg_prof.status_code == 201, rg_prof.text[:120])
rpid = rg_prof.json()["profile_id"]

# Trigger alert directly — early warning signs (WARNING level inputs)
rg_alert = httpx.post(f"{B}:8005/api/v1/early-warning/alerts/direct", headers=H, json={
    "profile_id": rpid,
    "dti_ratio": 0.38,
    "missed_payments": 0,
    "days_overdue_avg": 5.0,
    "recent_surplus_trend": [6000, 4500, 3000, 2000],
    "risk_category": "MEDIUM",
}, timeout=15)
chk("G2: Alert created via direct (201)", rg_alert.status_code == 201, rg_alert.text[:120])
g_alert = rg_alert.json()
gaid = g_alert.get("alert_id", "")
chk("G2: alert_id present", bool(gaid))
chk("G2: initial severity = WARNING or INFO",
    g_alert.get("severity") in ("INFO", "WARNING"))
print(f"  alert_id = {gaid[:8]}...  severity = {g_alert.get('severity')}")

# GET alert by ID
rg_get = httpx.get(f"{B}:8005/api/v1/early-warning/alerts/{gaid}", headers=H, timeout=5)
chk("G3: GET /alerts/{id} -> 200", rg_get.status_code == 200)
chk("G3: status = ACTIVE initially", rg_get.json().get("status") == "ACTIVE")

# Escalate — severity INFO/WARNING → CRITICAL
rg_esc = httpx.post(f"{B}:8005/api/v1/early-warning/alerts/{gaid}/escalate",
    headers=H, json={"new_severity": "CRITICAL", "reason": "Situation deteriorated — crop failure confirmed"}, timeout=5)
chk("G4: Escalate alert -> 200", rg_esc.status_code == 200, rg_esc.text[:80])
chk("G4: severity = CRITICAL after escalate", rg_esc.json().get("severity") == "CRITICAL")
print(f"  after escalate: severity = {rg_esc.json().get('severity')}  status = {rg_esc.json().get('status')}")

# Acknowledge
rg_ack = httpx.post(f"{B}:8005/api/v1/early-warning/alerts/{gaid}/acknowledge",
    headers=H, json={}, timeout=5)
chk("G5: Acknowledge alert -> 200", rg_ack.status_code == 200, rg_ack.text[:80])
chk("G5: status = ACKNOWLEDGED after ack", rg_ack.json().get("status") == "ACKNOWLEDGED")
print(f"  after acknowledge: status = {rg_ack.json().get('status')}")

# Resolve
rg_res = httpx.post(f"{B}:8005/api/v1/early-warning/alerts/{gaid}/resolve",
    headers=H, json={}, timeout=5)
chk("G6: Resolve alert -> 200", rg_res.status_code == 200, rg_res.text[:80])
chk("G6: status = RESOLVED after resolve", rg_res.json().get("status") == "RESOLVED")
print(f"  after resolve: status = {rg_res.json().get('status')}")

# Active alerts for profile should now be empty
rg_active = httpx.get(
    f"{B}:8005/api/v1/early-warning/alerts/profile/{rpid}/active",
    headers=H, timeout=5)
chk("G7: GET /alerts/profile/{id}/active -> 200", rg_active.status_code == 200)
chk("G7: No active alerts after resolution", rg_active.json().get("count", 0) == 0)
print(f"  active alerts after resolution = {rg_active.json().get('count')}")

# Full alert history for profile
rg_hist = httpx.get(
    f"{B}:8005/api/v1/early-warning/alerts/profile/{rpid}",
    headers=H, timeout=5)
chk("G8: GET /alerts/profile/{id} -> 200", rg_hist.status_code == 200)
chk("G8: at least 1 alert in full history", rg_hist.json().get("count", 0) >= 1)


# ═════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═════════════════════════════════════════════════════════════════════════════
print()
print("=" * 62)
print("  SCENARIO SIMULATIONS COMPLETE")
print(f"  {len(ok)} PASSED  |  {len(err)} FAILED  |  {len(ok)+len(err)} total checks")
if err:
    print()
    print("  FAILED:")
    for e in err:
        print(f"    x {e}")
    sys.exit(1)
else:
    print("  All checks passed — all 7 services wired correctly")
print("=" * 62)
