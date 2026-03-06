"""End-to-end tests for the Early Warning & Scenarios service.

Hits the running service on http://localhost:8084.
Run after: uvicorn services.early_warning.app.main:app --port 8084
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e  # requires running service — skipped by default

BASE = "http://localhost:8005/api/v1/early-warning"


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE, timeout=15)


# ===========================================================================
# Health Check
# ===========================================================================
def test_health():
    r = httpx.get("http://localhost:8005/health")
    assert r.status_code == 200
    assert r.json()["service"] == "early-warning"


# ===========================================================================
# Alert Generation — Direct (no cross-service)
# ===========================================================================
class TestDirectAlerts:
    def test_generate_alert_direct(self, client):
        resp = client.post("/alerts/direct", json={
            "profile_id": "e2e-prof-1",
            "dti_ratio": 0.5,
            "missed_payments": 2,
            "days_overdue_avg": 10.0,
            "recent_surplus_trend": [10000, 8000, 5000, 2000],
            "expected_incomes": [
                {"month": 1, "year": 2026, "amount": 15000},
                {"month": 2, "year": 2026, "amount": 12000},
            ],
            "actual_incomes": [
                {"month": 1, "year": 2026, "amount": 10000},
                {"month": 2, "year": 2026, "amount": 8000},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["profile_id"] == "e2e-prof-1"
        assert data["status"] == "ACTIVE"
        assert data["severity"] in ("INFO", "WARNING", "CRITICAL")
        assert len(data["recommendations"]) > 0

    def test_generate_minimal_alert(self, client):
        resp = client.post("/alerts/direct", json={
            "profile_id": "e2e-prof-2",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["alert_type"] in (
            "INCOME_DEVIATION", "REPAYMENT_STRESS", "OVER_INDEBTEDNESS",
        )

    def test_generate_alert_with_risk_category(self, client):
        resp = client.post("/alerts/direct", json={
            "profile_id": "e2e-prof-3",
            "risk_category": "HIGH",
        })
        assert resp.status_code == 201
        assert resp.json()["severity"] == "WARNING"


# ===========================================================================
# Alert Lifecycle
# ===========================================================================
class TestAlertLifecycle:
    def _create_alert(self, client) -> str:
        resp = client.post("/alerts/direct", json={"profile_id": "e2e-lifecycle"})
        assert resp.status_code == 201
        return resp.json()["alert_id"]

    def test_get_alert(self, client):
        alert_id = self._create_alert(client)
        resp = client.get(f"/alerts/{alert_id}")
        assert resp.status_code == 200
        assert resp.json()["alert_id"] == alert_id

    def test_get_alert_not_found(self, client):
        resp = client.get("/alerts/nonexistent-id")
        assert resp.status_code == 404

    def test_escalate_alert(self, client):
        alert_id = self._create_alert(client)
        resp = client.post(f"/alerts/{alert_id}/escalate", json={
            "new_severity": "WARNING",
            "reason": "Conditions worsened",
        })
        assert resp.status_code == 200
        assert resp.json()["severity"] == "WARNING"

    def test_acknowledge_alert(self, client):
        alert_id = self._create_alert(client)
        resp = client.post(f"/alerts/{alert_id}/acknowledge")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ACKNOWLEDGED"

    def test_resolve_alert(self, client):
        alert_id = self._create_alert(client)
        resp = client.post(f"/alerts/{alert_id}/resolve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "RESOLVED"

    def test_full_lifecycle(self, client):
        alert_id = self._create_alert(client)

        # Escalate
        resp = client.post(f"/alerts/{alert_id}/escalate", json={
            "new_severity": "CRITICAL",
            "reason": "Emergency",
        })
        assert resp.status_code == 200

        # Acknowledge
        resp = client.post(f"/alerts/{alert_id}/acknowledge")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ACKNOWLEDGED"

        # Resolve
        resp = client.post(f"/alerts/{alert_id}/resolve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "RESOLVED"


# ===========================================================================
# Alert Queries
# ===========================================================================
class TestAlertQueries:
    def test_get_alerts_for_profile(self, client):
        for _ in range(3):
            client.post("/alerts/direct", json={"profile_id": "e2e-query-prof"})
        resp = client.get("/alerts/profile/e2e-query-prof")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 3

    def test_get_active_alerts(self, client):
        r1 = client.post("/alerts/direct", json={"profile_id": "e2e-active-prof"})
        alert_id = r1.json()["alert_id"]
        client.post(f"/alerts/{alert_id}/resolve")

        client.post("/alerts/direct", json={"profile_id": "e2e-active-prof"})

        resp = client.get("/alerts/profile/e2e-active-prof/active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        for item in data["items"]:
            assert item["status"] in ("ACTIVE", "ACKNOWLEDGED")


# ===========================================================================
# Scenario Simulation — Direct (no cross-service)
# ===========================================================================
class TestDirectScenarios:
    def test_simulate_direct(self, client):
        resp = client.post("/scenarios/simulate/direct", json={
            "profile_id": "e2e-scenario-1",
            "scenario_type": "INCOME_SHOCK",
            "name": "30% Income Drop",
            "income_reduction_pct": 30.0,
            "duration_months": 6,
            "baseline_projections": [
                {"month": m, "year": 2026, "inflow": 15000, "outflow": 10000}
                for m in range(1, 7)
            ],
            "existing_monthly_obligations": 3000.0,
            "household_monthly_expense": 8000.0,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["profile_id"] == "e2e-scenario-1"
        assert len(data["projections"]) == 6
        assert data["overall_risk_level"] in ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")
        assert data["capacity_impact"]["emi_reduction_pct"] >= 0

    def test_simulate_weather_scenario(self, client):
        resp = client.post("/scenarios/simulate/direct", json={
            "profile_id": "e2e-weather",
            "scenario_type": "WEATHER_IMPACT",
            "name": "Drought",
            "weather_adjustment": 0.5,
            "duration_months": 3,
            "baseline_projections": [
                {"month": m, "year": 2026, "inflow": 20000, "outflow": 12000}
                for m in range(1, 7)
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        projs = data["projections"]
        for p in projs[:3]:
            assert p["stressed_inflow"] < p["baseline_inflow"]
        for p in projs[3:]:
            assert p["stressed_inflow"] == p["baseline_inflow"]

    def test_simulate_returns_recommendations(self, client):
        resp = client.post("/scenarios/simulate/direct", json={
            "profile_id": "e2e-recs",
            "scenario_type": "INCOME_SHOCK",
            "name": "Severe Drop",
            "income_reduction_pct": 50.0,
            "duration_months": 6,
            "baseline_projections": [
                {"month": m, "year": 2026, "inflow": 15000, "outflow": 10000}
                for m in range(1, 7)
            ],
        })
        assert resp.status_code == 201
        assert len(resp.json()["recommendations"]) > 0


# ===========================================================================
# Scenario Comparison — Direct
# ===========================================================================
class TestDirectComparison:
    def test_compare_scenarios_direct(self, client):
        resp = client.post("/scenarios/compare/direct", json={
            "profile_id": "e2e-compare",
            "scenarios": [
                {
                    "scenario_type": "INCOME_SHOCK",
                    "name": "Mild",
                    "income_reduction_pct": 10.0,
                    "duration_months": 6,
                },
                {
                    "scenario_type": "INCOME_SHOCK",
                    "name": "Severe",
                    "income_reduction_pct": 50.0,
                    "duration_months": 6,
                },
            ],
            "baseline_projections": [
                {"month": m, "year": 2026, "inflow": 15000, "outflow": 10000}
                for m in range(1, 7)
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["results"]) == 2
        mild_loss = data["results"][0]["total_income_loss"]
        severe_loss = data["results"][1]["total_income_loss"]
        assert severe_loss > mild_loss


# ===========================================================================
# Scenario Queries
# ===========================================================================
class TestScenarioQueries:
    def test_get_simulation_by_id(self, client):
        r = client.post("/scenarios/simulate/direct", json={
            "profile_id": "e2e-sim-query",
            "scenario_type": "INCOME_SHOCK",
            "name": "Test",
            "income_reduction_pct": 20.0,
            "duration_months": 6,
            "baseline_projections": [
                {"month": m, "year": 2026, "inflow": 15000, "outflow": 10000}
                for m in range(1, 7)
            ],
        })
        assert r.status_code == 201
        sim_id = r.json()["simulation_id"]

        resp = client.get(f"/scenarios/{sim_id}")
        assert resp.status_code == 200
        assert resp.json()["simulation_id"] == sim_id

    def test_get_simulation_not_found(self, client):
        resp = client.get("/scenarios/nonexistent-id")
        assert resp.status_code == 404

    def test_get_simulation_history(self, client):
        for i in range(2):
            client.post("/scenarios/simulate/direct", json={
                "profile_id": "e2e-history-prof",
                "scenario_type": "INCOME_SHOCK",
                "name": f"Scenario {i}",
                "income_reduction_pct": 10.0 * (i + 1),
                "duration_months": 6,
                "baseline_projections": [
                    {"month": m, "year": 2026, "inflow": 15000, "outflow": 10000}
                    for m in range(1, 7)
                ],
            })
        resp = client.get("/scenarios/profile/e2e-history-prof/history")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 2


# ===========================================================================
# Monitor (cross-service with stubs)
# ===========================================================================
class TestMonitoring:
    def test_monitor_endpoint(self, client):
        resp = client.post("/monitor", json={"profile_id": "e2e-monitor-1"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["profile_id"] == "e2e-monitor-1"
        assert data["status"] == "ACTIVE"

    def test_monitor_empty_profile(self, client):
        resp = client.post("/monitor", json={"profile_id": ""})
        assert resp.status_code in (400, 422)


# ===========================================================================
# Cross-service Simulate (with stubs)
# ===========================================================================
_BASELINE = [
    {"month": m, "year": 2026, "inflow": 15000, "outflow": 8000}
    for m in range(1, 13)
]


class TestCrossServiceSimulate:
    def test_simulate_cross_service(self, client):
        resp = client.post("/scenarios/simulate/direct", json={
            "profile_id": "e2e-cross-sim",
            "scenario_type": "INCOME_SHOCK",
            "name": "Cross-Service Test",
            "income_reduction_pct": 25.0,
            "duration_months": 6,
            "baseline_projections": _BASELINE,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["profile_id"] == "e2e-cross-sim"
        assert len(data["projections"]) > 0

    def test_compare_cross_service(self, client):
        resp = client.post("/scenarios/compare/direct", json={
            "profile_id": "e2e-cross-compare",
            "scenarios": [
                {"scenario_type": "INCOME_SHOCK", "name": "A", "income_reduction_pct": 10},
                {"scenario_type": "WEATHER_IMPACT", "name": "B", "weather_adjustment": 0.6},
            ],
            "baseline_projections": _BASELINE,
        })
        assert resp.status_code == 201
        assert len(resp.json()["results"]) == 2
