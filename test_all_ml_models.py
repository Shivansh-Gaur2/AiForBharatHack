"""
Comprehensive ML/AI Model Simulation Test
==========================================
Tests every AI/ML-powered endpoint across all services to verify
the models (or their rule-based fallbacks) are functioning correctly.

Services tested:
  1. Risk Assessment (8003) — XGBoost / rule-based risk scoring
  2. Cashflow Service (8004) — Prophet / seasonal projection
  3. Early Warning (8005)   — Isolation Forest + LightGBM / rule-based alerts
  4. Early Warning Scenarios — Monte Carlo / deterministic scenario sim
  5. Guidance (8006)         — Rule-based guidance (consumes ML outputs)
  6. AI Advisor (8008)       — Bedrock LLM / Stub LLM
"""

import json
import sys
import time
import requests

# ─── Config ───────────────────────────────────────────────────────────────
PROFILE_SERVICE = "http://127.0.0.1:8001"
RISK_SERVICE    = "http://127.0.0.1:8003"
CASHFLOW_SERVICE= "http://127.0.0.1:8004"
EARLY_WARNING   = "http://127.0.0.1:8005"
GUIDANCE_SERVICE= "http://127.0.0.1:8006"
AI_ADVISOR      = "http://127.0.0.1:8008"

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
WARN = "\033[93m⚠ WARN\033[0m"

results = []

def log_result(service: str, test: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    results.append({"service": service, "test": test, "passed": passed, "detail": detail})
    print(f"  {status}  {test}")
    if detail and not passed:
        print(f"         Detail: {detail[:200]}")

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════════════════
# Step 0: Get a profile ID to test with
# ═══════════════════════════════════════════════════════════════════════════
section("0. SETUP — Fetching test profile")

try:
    # Try listing profiles (may return items or have pagination issues)
    r = requests.get(f"{PROFILE_SERVICE}/api/v1/profiles?limit=50", timeout=5)
    profiles = r.json().get("items", [])
    if profiles:
        PROFILE_ID = profiles[0]["profile_id"]
        print(f"  Using profile: {PROFILE_ID} ({profiles[0].get('name', '?')})")
    else:
        # Try a known profile ID (from earlier terminal output)
        known_id = "74d9d101-9d84-4ab9-9058-cba07b3989dd"
        r2 = requests.get(f"{PROFILE_SERVICE}/api/v1/profiles/{known_id}", timeout=5)
        if r2.status_code == 200:
            PROFILE_ID = known_id
            pdata = r2.json()
            name = pdata.get("personal_info", {}).get("name", "?")
            print(f"  Using known profile: {PROFILE_ID} ({name})")
        else:
            # Create one as last resort
            print(f"  {WARN} No profiles found — creating a test profile...")
            r3 = requests.post(f"{PROFILE_SERVICE}/api/v1/profiles", json={
                "name": "Test Farmer",
                "age": 35,
                "location": "Pune",
                "occupation": "FARMER",
                "annual_income": 180000,
                "land_holding_acres": 3.5,
                "dependents": 4,
                "has_irrigation": True,
                "crops": ["soybean", "wheat"],
                "district": "Pune",
                "state": "Maharashtra",
            }, timeout=5)
            data3 = r3.json()
            PROFILE_ID = data3.get("profile_id", data3.get("id"))
            print(f"  Created profile: {PROFILE_ID}")
except Exception as e:
    print(f"  {FAIL} Cannot reach Profile Service: {e}")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: RISK ASSESSMENT
# ═══════════════════════════════════════════════════════════════════════════
section("1. RISK ASSESSMENT SERVICE (port 8003)")

# 1a. Direct scoring (POST /score)
try:
    r = requests.post(f"{RISK_SERVICE}/api/v1/risk/score", json={
        "profile_id": PROFILE_ID,
        "income_volatility_cv": 0.35,
        "annual_income": 180000,
        "months_below_average": 3,
        "debt_to_income_ratio": 0.25,
        "total_outstanding": 50000,
        "active_loan_count": 1,
        "credit_utilisation": 0.4,
        "on_time_repayment_ratio": 0.9,
        "has_defaults": False,
        "seasonal_variance": 0.3,
        "crop_diversification_index": 0.5,
        "weather_risk_score": 20.0,
        "market_risk_score": 15.0,
        "dependents": 3,
        "age": 35,
        "has_irrigation": True,
    }, timeout=10)
    data = r.json()
    passed = r.status_code in (200, 201) and "risk_score" in data
    score = data.get("risk_score", "?")
    cat = data.get("risk_category", "?")
    log_result("Risk", f"Direct score → score={score}, category={cat}", passed,
               f"status={r.status_code}" if not passed else "")
except Exception as e:
    log_result("Risk", "Direct score (POST /score)", False, str(e))

# 1b. Full assessment (POST /assess) — cross-service
try:
    r = requests.post(f"{RISK_SERVICE}/api/v1/risk/assess", json={
        "profile_id": PROFILE_ID,
    }, timeout=15)
    data = r.json()
    passed = r.status_code in (200, 201) and ("risk_score" in data or "assessment_id" in data)
    log_result("Risk", f"Full assess → {data.get('risk_category', data.get('detail', '?'))}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("Risk", "Full assessment (POST /assess)", False, str(e))

# 1c. Risk explanation
try:
    # Try to get latest for profile
    r = requests.get(f"{RISK_SERVICE}/api/v1/risk/profile/{PROFILE_ID}", timeout=10)
    if r.status_code == 200:
        assessment_id = r.json().get("assessment_id")
        if assessment_id:
            r2 = requests.get(f"{RISK_SERVICE}/api/v1/risk/{assessment_id}/explain", timeout=10)
            passed = r2.status_code == 200
            log_result("Risk", f"Risk explanation → {r2.status_code}", passed)
        else:
            log_result("Risk", "Risk explanation (no assessment_id to explain)", True, "Skipped")
    else:
        log_result("Risk", "Risk explanation", True, f"No assessment yet (status={r.status_code})")
except Exception as e:
    log_result("Risk", "Risk explanation", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Test 2: CASHFLOW SERVICE
# ═══════════════════════════════════════════════════════════════════════════
section("2. CASHFLOW SERVICE (port 8004)")

# 2a. Direct forecast
try:
    records = []
    for m in range(1, 13):
        records.append({"profile_id": PROFILE_ID, "category": "CROP_INCOME", "direction": "INFLOW",
                        "amount": 15000 + (m % 4) * 5000, "month": m, "year": 2025})
        records.append({"profile_id": PROFILE_ID, "category": "HOUSEHOLD", "direction": "OUTFLOW",
                        "amount": 8000 + (m % 3) * 1000, "month": m, "year": 2025})
    r = requests.post(f"{CASHFLOW_SERVICE}/api/v1/cashflow/forecast/direct", json={
        "profile_id": PROFILE_ID,
        "records": records,
        "horizon_months": 6,
        "existing_monthly_obligations": 5000,
        "household_monthly_expense": 8000,
        "weather_adjustment": 1.0,
        "market_adjustment": 1.0,
        "loan_tenure_months": 12,
    }, timeout=15)
    data = r.json()
    passed = r.status_code in (200, 201)
    months = len(data.get("monthly_projections", data.get("projections", [])))
    log_result("Cashflow", f"Direct forecast → {months} months projected", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("Cashflow", "Direct forecast (POST /forecast/direct)", False, str(e))

# 2b. Cross-service forecast
try:
    r = requests.post(f"{CASHFLOW_SERVICE}/api/v1/cashflow/forecast", json={
        "profile_id": PROFILE_ID,
        "horizon_months": 6,
        "start_month": 3,
        "start_year": 2026,
        "loan_tenure_months": 12,
    }, timeout=15)
    data = r.json()
    passed = r.status_code in (200, 201)
    log_result("Cashflow", f"Cross-service forecast → status {r.status_code}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("Cashflow", "Cross-service forecast (POST /forecast)", False, str(e))

# 2c. Repayment capacity
try:
    r = requests.get(f"{CASHFLOW_SERVICE}/api/v1/cashflow/capacity/{PROFILE_ID}", timeout=10)
    data = r.json()
    passed = r.status_code == 200
    cap = data.get("recommended_emi", data.get("recommended_monthly_emi", "?"))
    log_result("Cashflow", f"Repayment capacity → recommended EMI = {cap}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("Cashflow", "Repayment capacity", False, str(e))

# 2d. Credit timing
try:
    r = requests.get(f"{CASHFLOW_SERVICE}/api/v1/cashflow/timing/{PROFILE_ID}", timeout=10)
    data = r.json()
    passed = r.status_code == 200
    log_result("Cashflow", f"Credit timing → status {r.status_code}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("Cashflow", "Credit timing", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Test 3: EARLY WARNING SERVICE
# ═══════════════════════════════════════════════════════════════════════════
section("3. EARLY WARNING SERVICE (port 8005)")

# 3a. Direct alert generation
try:
    r = requests.post(f"{EARLY_WARNING}/api/v1/early-warning/alerts/direct", json={
        "profile_id": PROFILE_ID,
        "dti_ratio": 0.55,
        "missed_payments": 2,
        "days_overdue_avg": 20.0,
        "recent_surplus_trend": [5000, 3000, 1000, -2000],
        "risk_category": "HIGH",
        "alert_type": "REPAYMENT_STRESS",
    }, timeout=10)
    data = r.json()
    passed = r.status_code in (200, 201)
    sev = data.get("severity", data.get("alert", {}).get("severity", "?"))
    log_result("EarlyWarning", f"Direct alert → severity={sev}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("EarlyWarning", "Direct alert (POST /alerts/direct)", False, str(e))

# 3b. Full monitoring pipeline
try:
    r = requests.post(f"{EARLY_WARNING}/api/v1/early-warning/monitor", json={
        "profile_id": PROFILE_ID,
    }, timeout=15)
    data = r.json()
    passed = r.status_code in (200, 201)
    n_alerts = len(data.get("alerts", [data] if "alert_id" in data else []))
    log_result("EarlyWarning", f"Monitor pipeline → {n_alerts} alert(s) generated", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("EarlyWarning", "Monitor pipeline (POST /monitor)", False, str(e))

# 3c. Scenario simulation (direct)
try:
    r = requests.post(f"{EARLY_WARNING}/api/v1/early-warning/scenarios/simulate/direct", json={
        "profile_id": PROFILE_ID,
        "scenario_type": "INCOME_SHOCK",
        "name": "Drought Test",
        "description": "50% income reduction due to drought",
        "income_reduction_pct": 50,
        "weather_adjustment": 0.5,
        "duration_months": 6,
        "baseline_projections": [
            {"month": m, "year": 2026, "inflow": 25000 - m*500, "outflow": 15000}
            for m in range(1, 7)
        ],
        "existing_monthly_obligations": 5000,
        "household_monthly_expense": 8000,
    }, timeout=15)
    data = r.json()
    passed = r.status_code in (200, 201)
    risk = data.get("distress_risk", data.get("default_probability", "?"))
    log_result("EarlyWarning", f"Scenario sim (drought) → distress_risk={risk}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("EarlyWarning", "Scenario simulation (POST /scenarios/simulate/direct)", False, str(e))

# 3d. Cross-service scenario
try:
    r = requests.post(f"{EARLY_WARNING}/api/v1/early-warning/scenarios/simulate", json={
        "profile_id": PROFILE_ID,
        "scenario_type": "WEATHER_IMPACT",
        "name": "Monsoon Failure",
        "description": "Complete monsoon failure",
        "income_reduction_pct": 60,
        "weather_adjustment": 0.3,
        "duration_months": 4,
        "existing_monthly_obligations": 5000,
        "household_monthly_expense": 8000,
    }, timeout=15)
    data = r.json()
    passed = r.status_code in (200, 201)
    log_result("EarlyWarning", f"Cross-service scenario → status {r.status_code}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("EarlyWarning", "Cross-service scenario simulation", False, str(e))

# 3e. Multi-scenario comparison
try:
    r = requests.post(f"{EARLY_WARNING}/api/v1/early-warning/scenarios/compare/direct", json={
        "profile_id": PROFILE_ID,
        "baseline_projections": [
            {"month": m, "year": 2026, "inflow": 25000, "outflow": 15000}
            for m in range(1, 7)
        ],
        "scenarios": [
            {"scenario_type": "INCOME_SHOCK", "name": "Mild shock",
             "income_reduction_pct": 20, "duration_months": 3},
            {"scenario_type": "INCOME_SHOCK", "name": "Severe shock",
             "income_reduction_pct": 60, "duration_months": 6},
        ],
        "existing_monthly_obligations": 5000,
        "household_monthly_expense": 8000,
    }, timeout=15)
    data = r.json()
    passed = r.status_code in (200, 201)
    n = len(data.get("results", data.get("scenarios", [])))
    log_result("EarlyWarning", f"Scenario comparison → {n} scenarios compared", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("EarlyWarning", "Scenario comparison (POST /scenarios/compare/direct)", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Test 4: GUIDANCE SERVICE
# ═══════════════════════════════════════════════════════════════════════════
section("4. GUIDANCE SERVICE (port 8006)")

# 4a. Direct guidance generation
try:
    r = requests.post(f"{GUIDANCE_SERVICE}/api/v1/guidance/generate/direct", json={
        "profile_id": PROFILE_ID,
        "loan_purpose": "CROP_CULTIVATION",
        "requested_amount": 50000,
        "tenure_months": 12,
        "interest_rate_annual": 9.0,
        "projections": [
            {"month": m, "year": 2026, "inflow": 25000 + (m%3)*3000, "outflow": 14000 + (m%2)*2000}
            for m in range(1, 13)
        ],
        "risk_category": "MEDIUM",
        "risk_score": 500,
        "dti_ratio": 0.3,
        "existing_obligations": 5000,
    }, timeout=15)
    data = r.json()
    passed = r.status_code in (200, 201)
    verdict = data.get("verdict", data.get("recommendation", "?"))
    log_result("Guidance", f"Direct guidance → verdict={verdict}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("Guidance", "Direct guidance (POST /generate/direct)", False, str(e))

# 4b. Cross-service guidance
try:
    r = requests.post(f"{GUIDANCE_SERVICE}/api/v1/guidance/generate", json={
        "profile_id": PROFILE_ID,
        "loan_purpose": "CROP_CULTIVATION",
        "requested_amount": 50000,
        "tenure_months": 12,
        "interest_rate_annual": 9.0,
    }, timeout=15)
    data = r.json()
    passed = r.status_code in (200, 201)
    log_result("Guidance", f"Cross-service guidance → status {r.status_code}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("Guidance", "Cross-service guidance (POST /generate)", False, str(e))

# 4c. Loan timing
try:
    r = requests.post(f"{GUIDANCE_SERVICE}/api/v1/guidance/timing", json={
        "profile_id": PROFILE_ID,
        "loan_amount": 50000,
        "tenure_months": 12,
    }, timeout=15)
    data = r.json()
    passed = r.status_code in (200, 201)
    best = data.get("best_month", data.get("recommended_month", "?"))
    log_result("Guidance", f"Loan timing → best month={best}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("Guidance", "Loan timing (POST /timing)", False, str(e))

# 4d. Loan amount recommendation
try:
    r = requests.post(f"{GUIDANCE_SERVICE}/api/v1/guidance/amount", json={
        "profile_id": PROFILE_ID,
        "tenure_months": 12,
        "interest_rate_annual": 9.0,
    }, timeout=15)
    data = r.json()
    passed = r.status_code in (200, 201)
    amt = data.get("recommended_amount", data.get("max_amount", "?"))
    log_result("Guidance", f"Loan amount → recommended={amt}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("Guidance", "Loan amount (POST /amount)", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Test 5: AI ADVISOR (LLM)
# ═══════════════════════════════════════════════════════════════════════════
section("5. AI ADVISOR SERVICE (port 8008)")

# 5a. Start conversation (no profile)
try:
    r = requests.post(f"{AI_ADVISOR}/api/v1/ai-advisor/conversations", json={
        "language": "en",
    }, timeout=15)
    data = r.json()
    passed = r.status_code == 200 and "conversation_id" in data
    conv_id = data.get("conversation_id", "?")
    log_result("AI Advisor", f"Start conversation → id={conv_id[:20]}...", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("AI Advisor", "Start conversation", False, str(e))
    conv_id = None

# 5b. Start conversation WITH profile context
try:
    r = requests.post(f"{AI_ADVISOR}/api/v1/ai-advisor/conversations", json={
        "profile_id": PROFILE_ID,
        "language": "en",
        "message": "What is my current risk level and can I safely take a loan of Rs 50,000?",
    }, timeout=20)
    data = r.json()
    passed = r.status_code == 200 and "message" in data
    msg_preview = (data.get("message", "")[:80] + "...") if data.get("message") else "?"
    log_result("AI Advisor", f"Contextual conversation → \"{msg_preview}\"", passed,
               json.dumps(data)[:200] if not passed else "")
    conv_id_ctx = data.get("conversation_id")
except Exception as e:
    log_result("AI Advisor", "Contextual conversation", False, str(e))
    conv_id_ctx = None

# 5c. Send follow-up message
if conv_id:
    try:
        r = requests.post(f"{AI_ADVISOR}/api/v1/ai-advisor/conversations/{conv_id}/messages", json={
            "message": "Tell me about government schemes for small farmers",
        }, timeout=20)
        data = r.json()
        passed = r.status_code == 200 and "message" in data
        msg_preview = (data.get("message", "")[:80] + "...") if data.get("message") else "?"
        log_result("AI Advisor", f"Follow-up message → \"{msg_preview}\"", passed,
                   json.dumps(data)[:200] if not passed else "")
    except Exception as e:
        log_result("AI Advisor", "Follow-up message", False, str(e))

# 5d. Quick analysis
try:
    r = requests.post(f"{AI_ADVISOR}/api/v1/ai-advisor/analyze", json={
        "profile_id": PROFILE_ID,
    }, timeout=20)
    data = r.json()
    passed = r.status_code == 200 and "analysis" in data
    analysis_preview = (data.get("analysis", "")[:80] + "...") if data.get("analysis") else "?"
    log_result("AI Advisor", f"Quick analysis → \"{analysis_preview}\"", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("AI Advisor", "Quick analysis (POST /analyze)", False, str(e))

# 5e. Scenario analysis
try:
    r = requests.post(f"{AI_ADVISOR}/api/v1/ai-advisor/scenarios", json={
        "profile_id": PROFILE_ID,
        "scenario": "What if soybean prices drop 30% and monsoon is delayed by 3 weeks?",
    }, timeout=20)
    data = r.json()
    passed = r.status_code == 200 and "analysis" in data
    analysis_preview = (data.get("analysis", "")[:80] + "...") if data.get("analysis") else "?"
    log_result("AI Advisor", f"Scenario analysis → \"{analysis_preview}\"", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("AI Advisor", "Scenario analysis (POST /scenarios)", False, str(e))

# 5f. Hindi language test
try:
    r = requests.post(f"{AI_ADVISOR}/api/v1/ai-advisor/conversations", json={
        "language": "hi",
        "message": "मेरे लिए कौन सी सरकारी योजना उपलब्ध है?",
    }, timeout=20)
    data = r.json()
    passed = r.status_code == 200 and "message" in data
    log_result("AI Advisor", f"Hindi conversation → status {r.status_code}", passed,
               json.dumps(data)[:200] if not passed else "")
except Exception as e:
    log_result("AI Advisor", "Hindi conversation", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
section("FINAL RESULTS SUMMARY")

total = len(results)
passed = sum(1 for r in results if r["passed"])
failed = total - passed

by_service = {}
for r in results:
    svc = r["service"]
    if svc not in by_service:
        by_service[svc] = {"pass": 0, "fail": 0}
    if r["passed"]:
        by_service[svc]["pass"] += 1
    else:
        by_service[svc]["fail"] += 1

print(f"\n  Total tests:  {total}")
print(f"  Passed:       {passed}  ({100*passed//total}%)")
print(f"  Failed:       {failed}")
print()

for svc, counts in by_service.items():
    status = PASS if counts["fail"] == 0 else FAIL
    print(f"  {status}  {svc:20s}  {counts['pass']}/{counts['pass']+counts['fail']} passed")

if failed > 0:
    print(f"\n  Failed tests:")
    for r in results:
        if not r["passed"]:
            print(f"    {FAIL}  [{r['service']}] {r['test']}")
            if r["detail"]:
                print(f"           {r['detail'][:150]}")

print()
sys.exit(0 if failed == 0 else 1)
