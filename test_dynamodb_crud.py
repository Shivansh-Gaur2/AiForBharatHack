"""Quick DynamoDB CRUD smoke test — create + read-back on live services."""
import httpx, sys

H = {"Content-Type": "application/json", "X-Skip-Auth": "true"}
errors = []

# 1. Profile service
r = httpx.post("http://localhost:8001/api/v1/profiles", headers=H, json={
    "personal_info": {"name": "Test Farmer", "age": 35, "gender": "M",
                      "district": "Pune", "state": "Maharashtra", "dependents": 2},
    "livelihood_info": {
        "primary_occupation": "FARMER", "secondary_occupations": [],
        "land_holding": {"total_acres": 2.0, "irrigated_acres": 1.0,
                         "rain_fed_acres": 1.0, "ownership_type": "OWNED"},
        "crop_patterns": [], "livestock": [], "migration_patterns": []
    },
    "income_records": [], "expense_records": []
}, timeout=10)
if r.status_code == 201:
    pid = r.json()["profile_id"]
    r2 = httpx.get(f"http://localhost:8001/api/v1/profiles/{pid}", headers=H, timeout=5)
    print(f"  201/{r2.status_code}  Profile  id={pid[:8]}...  (DynamoDB write+read OK)")
else:
    errors.append(f"Profile create {r.status_code}: {r.text[:150]}")
    pid = None

# 2. Loan tracker (source_type: FORMAL/SEMI_FORMAL/INFORMAL, terms is a nested object)
if pid:
    r = httpx.post("http://localhost:8002/api/v1/loans", headers=H, json={
        "profile_id": pid, "lender_name": "SBI", "source_type": "FORMAL",
        "terms": {
            "principal": 50000, "interest_rate_annual": 9.5,
            "tenure_months": 24, "emi_amount": 2300
        },
        "disbursement_date": "2025-01-01T00:00:00"
    }, timeout=10)
    if r.status_code == 201:
        lid = r.json()["tracking_id"]
        r2 = httpx.get(f"http://localhost:8002/api/v1/loans/{lid}", headers=H, timeout=5)
        print(f"  201/{r2.status_code}  Loan     id={lid[:8]}...  (DynamoDB write+read OK)")
    else:
        errors.append(f"Loan create {r.status_code}: {r.text[:150]}")

# 3. Risk assessment
if pid:
    r = httpx.post("http://localhost:8003/api/v1/risk/assess", headers=H, json={
        "profile_id": pid, "monthly_income": 12000, "monthly_expenses": 7000,
        "total_assets": 300000, "total_liabilities": 50000,
        "active_loans": 1, "missed_payments_12m": 0, "credit_history_months": 36,
        "loan_amount_requested": 50000, "loan_purpose": "CROP_CULTIVATION"
    }, timeout=10)
    if r.status_code == 201:
        d = r.json()
        print(f"  201      Risk     score={d.get('risk_score')}  category={d.get('risk_category')}  (DynamoDB write OK)")
    else:
        errors.append(f"Risk assess {r.status_code}: {r.text[:150]}")

# 4. Cashflow direct forecast (min 3 records, each needs profile_id)
if pid:
    records = [
        {"profile_id": pid, "category": "CROP_INCOME", "direction": "INFLOW",  "amount": 12000, "month": m, "year": 2025}
        for m in [1, 2, 3]
    ] + [
        {"profile_id": pid, "category": "HOUSEHOLD",   "direction": "OUTFLOW", "amount":  7000, "month": m, "year": 2025}
        for m in [1, 2, 3]
    ]
    r = httpx.post("http://localhost:8004/api/v1/cashflow/forecast/direct", headers=H, json={
        "profile_id": pid, "records": records
    }, timeout=15)
    if r.status_code == 201:
        fid = r.json()["forecast_id"]
        print(f"  201      Cashflow forecast_id={fid[:8]}...  (DynamoDB write OK)")
    else:
        errors.append(f"Cashflow forecast {r.status_code}: {r.text[:200]}")

# 5. Early Warning monitor
if pid:
    r = httpx.post("http://localhost:8005/api/v1/early-warning/monitor", headers=H,
                   json={"profile_id": pid}, timeout=10)
    if r.status_code in (200, 201):
        d = r.json()
        print(f"  {r.status_code}      EarlyWrn alert_type={d.get('alert_type','n/a')}  severity={d.get('severity','n/a')}  (DynamoDB write OK)")
    else:
        errors.append(f"EarlyWarning monitor {r.status_code}: {r.text[:150]}")

# 6. Security consent
if pid:
    r = httpx.post("http://localhost:8007/api/v1/security/consent", headers=H, json={
        "profile_id": pid,
        "purpose": "CREDIT_ASSESSMENT",
        "granted_by": "smoke-test",
        "duration_days": 30
    }, timeout=10)
    if r.status_code in (201, 200):
        cid = r.json()["consent_id"]
        print(f"  {r.status_code}      Security consent id={cid[:8]}...  (DynamoDB write OK)")
    else:
        errors.append(f"Security consent {r.status_code}: {r.text[:150]}")

print()
if errors:
    print("FAILURES:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("All DynamoDB CRUD checks passed.")
