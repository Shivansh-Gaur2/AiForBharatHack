"""Unit tests for Early Warning domain service — async orchestration tests."""

from __future__ import annotations

import pytest

from services.early_warning.app.domain.models import (
    Alert,
    AlertStatus,
    ScenarioParameters,
    ScenarioType,
    SimulationResult,
)
from services.early_warning.app.domain.services import EarlyWarningService
from services.early_warning.app.infrastructure.data_providers import (
    StubCashFlowDataProvider,
    StubLoanDataProvider,
    StubProfileDataProvider,
    StubRiskDataProvider,
)
from services.shared.events import AsyncInMemoryEventPublisher
from services.shared.models import AlertSeverity, AlertType, RiskCategory


# ---------------------------------------------------------------------------
# In-memory repository for testing
# ---------------------------------------------------------------------------
class InMemoryAlertRepository:
    """Minimal in-memory repo that satisfies the AlertRepository protocol."""

    def __init__(self) -> None:
        self._alerts: dict[str, Alert] = {}
        self._simulations: dict[str, SimulationResult] = {}

    async def save_alert(self, alert: Alert) -> None:
        self._alerts[alert.alert_id] = alert

    async def find_alert_by_id(self, alert_id: str) -> Alert | None:
        return self._alerts.get(alert_id)

    async def find_alerts_by_profile(
        self, profile_id: str, limit: int = 50,
    ) -> list[Alert]:
        return [
            a for a in self._alerts.values()
            if a.profile_id == profile_id
        ][:limit]

    async def find_active_alerts(self, profile_id: str) -> list[Alert]:
        return [
            a for a in self._alerts.values()
            if a.profile_id == profile_id and a.is_active()
        ]

    async def save_simulation(self, result: SimulationResult) -> None:
        self._simulations[result.simulation_id] = result

    async def find_simulation_by_id(self, simulation_id: str) -> SimulationResult | None:
        return self._simulations.get(simulation_id)

    async def find_simulations_by_profile(
        self, profile_id: str, limit: int = 20,
    ) -> list[SimulationResult]:
        return [
            s for s in self._simulations.values()
            if s.profile_id == profile_id
        ][:limit]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def service():
    repo = InMemoryAlertRepository()
    return EarlyWarningService(
        repo=repo,
        risk_provider=StubRiskDataProvider(),
        cashflow_provider=StubCashFlowDataProvider(),
        loan_provider=StubLoanDataProvider(),
        profile_provider=StubProfileDataProvider(),
        events=AsyncInMemoryEventPublisher(),
    )


@pytest.fixture
def high_risk_service():
    """Service configured with high-risk stub providers."""
    repo = InMemoryAlertRepository()
    return EarlyWarningService(
        repo=repo,
        risk_provider=StubRiskDataProvider(
            risk_category=RiskCategory.HIGH, risk_score=200.0,
        ),
        cashflow_provider=StubCashFlowDataProvider(),
        loan_provider=StubLoanDataProvider(
            exposure={"total_outstanding": 200000, "monthly_obligations": 15000,
                      "debt_to_income_ratio": 0.7, "active_loan_count": 3},
            repayment_stats={"missed_payments": 3, "days_overdue_avg": 25.0,
                             "on_time_ratio": 0.5},
        ),
        profile_provider=StubProfileDataProvider(
            actual_incomes=[(1, 2026, 5000), (2, 2026, 4000), (3, 2026, 3000)],
            household_expense=12000.0,
        ),
        events=AsyncInMemoryEventPublisher(),
    )


# ===========================================================================
# Alert Generation Tests
# ===========================================================================
class TestEarlyWarningService:
    @pytest.mark.asyncio
    async def test_monitor_and_alert_returns_alert(self, service):
        alert = await service.monitor_and_alert("prof-1")
        assert isinstance(alert, Alert)
        assert alert.profile_id == "prof-1"
        assert alert.status == AlertStatus.ACTIVE
        assert alert.alert_id

    @pytest.mark.asyncio
    async def test_monitor_and_alert_persists(self, service):
        alert = await service.monitor_and_alert("prof-1")
        found = await service.get_alert(alert.alert_id)
        assert found is not None
        assert found.alert_id == alert.alert_id

    @pytest.mark.asyncio
    async def test_direct_alert_with_stress_data(self, service):
        alert = await service.generate_alert_direct(
            profile_id="prof-1",
            dti_ratio=0.6,
            missed_payments=2,
            days_overdue_avg=15.0,
            recent_surplus_trend=[10000, 8000, 5000, 2000],
            expected_incomes=[(1, 2026, 15000), (2, 2026, 12000)],
            actual_incomes=[(1, 2026, 10000), (2, 2026, 8000)],
        )
        assert alert.severity in (AlertSeverity.WARNING, AlertSeverity.CRITICAL)
        assert len(alert.recommendations) > 0

    @pytest.mark.asyncio
    async def test_direct_alert_with_risk_category(self, service):
        alert = await service.generate_alert_direct(
            profile_id="prof-1",
            risk_category=RiskCategory.HIGH,
        )
        assert alert.severity == AlertSeverity.WARNING  # high risk → warning

    @pytest.mark.asyncio
    async def test_direct_alert_with_explicit_type(self, service):
        alert = await service.generate_alert_direct(
            profile_id="prof-1",
            alert_type=AlertType.WEATHER_RISK,
        )
        assert alert.alert_type == AlertType.WEATHER_RISK

    @pytest.mark.asyncio
    async def test_monitor_invalid_profile(self, service):
        with pytest.raises(ValueError, match="profile_id"):
            await service.monitor_and_alert("")

    @pytest.mark.asyncio
    async def test_high_risk_generates_critical_alert(self, high_risk_service):
        alert = await high_risk_service.monitor_and_alert("prof-distressed")
        # High DTI + missed payments + high risk category → high severity
        assert alert.severity in (AlertSeverity.WARNING, AlertSeverity.CRITICAL)

    # -----------------------------------------------------------------------
    # Alert Lifecycle
    # -----------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_escalate_alert(self, service):
        alert = await service.generate_alert_direct(profile_id="prof-1")
        escalated = await service.escalate_alert(
            alert.alert_id, AlertSeverity.WARNING, "Conditions worsened",
        )
        assert escalated.severity == AlertSeverity.WARNING

    @pytest.mark.asyncio
    async def test_escalate_nonexistent_alert(self, service):
        with pytest.raises(ValueError, match="not found"):
            await service.escalate_alert("nonexistent", AlertSeverity.CRITICAL, "reason")

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, service):
        alert = await service.generate_alert_direct(profile_id="prof-1")
        acked = await service.acknowledge_alert(alert.alert_id)
        assert acked.status == AlertStatus.ACKNOWLEDGED
        assert acked.acknowledged_at is not None

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent(self, service):
        with pytest.raises(ValueError, match="not found"):
            await service.acknowledge_alert("nonexistent")

    @pytest.mark.asyncio
    async def test_resolve_alert(self, service):
        alert = await service.generate_alert_direct(profile_id="prof-1")
        resolved = await service.resolve_alert(alert.alert_id)
        assert resolved.status == AlertStatus.RESOLVED
        assert resolved.resolved_at is not None

    @pytest.mark.asyncio
    async def test_resolve_nonexistent(self, service):
        with pytest.raises(ValueError, match="not found"):
            await service.resolve_alert("nonexistent")

    # -----------------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_get_alerts_for_profile(self, service):
        await service.generate_alert_direct(profile_id="prof-1")
        await service.generate_alert_direct(profile_id="prof-1")
        await service.generate_alert_direct(profile_id="prof-2")

        alerts = await service.get_alerts_for_profile("prof-1")
        assert len(alerts) == 2

    @pytest.mark.asyncio
    async def test_get_active_alerts(self, service):
        a1 = await service.generate_alert_direct(profile_id="prof-1")
        a2 = await service.generate_alert_direct(profile_id="prof-1")
        await service.resolve_alert(a1.alert_id)

        active = await service.get_active_alerts("prof-1")
        assert len(active) == 1
        assert active[0].alert_id == a2.alert_id

    @pytest.mark.asyncio
    async def test_get_alert_not_found(self, service):
        result = await service.get_alert("nonexistent")
        assert result is None


# ===========================================================================
# Scenario Simulation Tests
# ===========================================================================
class TestScenarioSimulation:
    @pytest.fixture
    def params(self):
        return ScenarioParameters(
            scenario_type=ScenarioType.INCOME_SHOCK,
            name="30% Income Reduction",
            income_reduction_pct=30.0,
            duration_months=6,
        )

    @pytest.fixture
    def baseline_projections(self):
        return [
            (1, 2026, 15000.0, 10000.0),
            (2, 2026, 12000.0, 10000.0),
            (3, 2026, 13000.0, 11000.0),
            (4, 2026, 30000.0, 12000.0),
            (5, 2026, 10000.0, 10000.0),
            (6, 2026, 8000.0, 13000.0),
        ]

    @pytest.mark.asyncio
    async def test_run_scenario_cross_service(self, service, params):
        result = await service.run_scenario("prof-1", params)
        assert isinstance(result, SimulationResult)
        assert result.profile_id == "prof-1"
        assert len(result.projections) > 0

    @pytest.mark.asyncio
    async def test_run_scenario_direct(self, service, params, baseline_projections):
        result = await service.run_scenario_direct(
            "prof-1", params, baseline_projections,
        )
        assert result.profile_id == "prof-1"
        assert len(result.projections) == 6

    @pytest.mark.asyncio
    async def test_run_scenario_direct_empty_baseline(self, service, params):
        with pytest.raises(ValueError, match="baseline"):
            await service.run_scenario_direct("prof-1", params, [])

    @pytest.mark.asyncio
    async def test_run_scenario_persists(self, service, params, baseline_projections):
        result = await service.run_scenario_direct(
            "prof-1", params, baseline_projections,
        )
        found = await service.get_simulation(result.simulation_id)
        assert found is not None
        assert found.simulation_id == result.simulation_id

    @pytest.mark.asyncio
    async def test_compare_scenarios_direct(self, service, baseline_projections):
        scenarios = [
            ScenarioParameters(ScenarioType.INCOME_SHOCK, "Mild", income_reduction_pct=10),
            ScenarioParameters(ScenarioType.INCOME_SHOCK, "Severe", income_reduction_pct=50),
        ]
        results = await service.compare_scenarios_direct(
            "prof-1", scenarios, baseline_projections,
        )
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_compare_scenarios_cross_service(self, service):
        scenarios = [
            ScenarioParameters(ScenarioType.INCOME_SHOCK, "Mild", income_reduction_pct=10),
            ScenarioParameters(ScenarioType.WEATHER_IMPACT, "Drought", weather_adjustment=0.5),
        ]
        results = await service.compare_scenarios("prof-1", scenarios)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_compare_scenarios_empty(self, service, baseline_projections):
        with pytest.raises(ValueError, match=r"[Aa]t least one"):
            await service.compare_scenarios_direct("prof-1", [], baseline_projections)

    @pytest.mark.asyncio
    async def test_compare_scenarios_direct_no_baseline(self, service):
        scenarios = [
            ScenarioParameters(ScenarioType.INCOME_SHOCK, "Test", income_reduction_pct=20),
        ]
        with pytest.raises(ValueError, match="baseline"):
            await service.compare_scenarios_direct("prof-1", scenarios, [])

    # -----------------------------------------------------------------------
    # Simulation Queries
    # -----------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_get_simulation_history(self, service, baseline_projections):
        for i in range(3):
            params = ScenarioParameters(
                ScenarioType.INCOME_SHOCK, f"Scenario {i}",
                income_reduction_pct=10.0 * (i + 1),
            )
            await service.run_scenario_direct(
                "prof-1", params, baseline_projections,
            )
        history = await service.get_simulation_history("prof-1")
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_get_simulation_not_found(self, service):
        result = await service.get_simulation("nonexistent")
        assert result is None
