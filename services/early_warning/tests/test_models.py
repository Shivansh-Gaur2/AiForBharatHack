"""Unit tests for Early Warning domain models — pure business logic.

Covers: IncomeDeviation, RepaymentStress, Alert lifecycle,
        Severity determination, Recommendations, Scenarios,
        Capacity impact, Multi-scenario comparison.
"""

from __future__ import annotations

import pytest

from services.early_warning.app.domain.models import (
    Alert,
    AlertStatus,
    CapacityImpact,
    IncomeDeviation,
    RecommendationPriority,
    RepaymentStressIndicator,
    ScenarioParameters,
    ScenarioProjection,
    ScenarioType,
    SimulationResult,
    build_alert,
    compute_income_deviations,
    compute_repayment_stress,
    determine_alert_severity,
    generate_recommendations,
    run_multi_scenario_comparison,
    simulate_scenario,
)
from services.shared.models import AlertSeverity, AlertType, RiskCategory


# ===========================================================================
# Income Deviations
# ===========================================================================
class TestComputeIncomeDeviations:
    def test_no_deviations_when_matching(self):
        expected = [(1, 2026, 10000.0), (2, 2026, 12000.0)]
        actual = [(1, 2026, 10000.0), (2, 2026, 12000.0)]
        devs = compute_income_deviations(expected, actual)
        assert len(devs) == 2
        assert all(d.deviation_pct == 0 for d in devs)
        assert all(not d.is_significant for d in devs)

    def test_significant_negative_deviation(self):
        expected = [(1, 2026, 10000.0)]
        actual = [(1, 2026, 7000.0)]  # 30% below
        devs = compute_income_deviations(expected, actual)
        assert len(devs) == 1
        assert devs[0].deviation_pct == -30.0
        assert devs[0].is_significant is True

    def test_positive_deviation_not_alarming_but_significant(self):
        expected = [(3, 2026, 10000.0)]
        actual = [(3, 2026, 15000.0)]  # +50%
        devs = compute_income_deviations(expected, actual)
        assert devs[0].deviation_pct == 50.0
        assert devs[0].is_significant is True  # abs >= 20

    def test_missing_actual_income_treated_as_zero(self):
        expected = [(1, 2026, 10000.0)]
        actual = []  # no actual data
        devs = compute_income_deviations(expected, actual)
        assert devs[0].actual_income == 0.0
        assert devs[0].deviation_pct == -100.0
        assert devs[0].is_significant is True

    def test_custom_threshold(self):
        expected = [(1, 2026, 10000.0)]
        actual = [(1, 2026, 8500.0)]  # -15%
        devs_20 = compute_income_deviations(expected, actual, threshold_pct=20.0)
        assert devs_20[0].is_significant is False
        devs_10 = compute_income_deviations(expected, actual, threshold_pct=10.0)
        assert devs_10[0].is_significant is True

    def test_zero_expected_income(self):
        expected = [(1, 2026, 0.0)]
        actual = [(1, 2026, 5000.0)]
        devs = compute_income_deviations(expected, actual)
        assert devs[0].deviation_pct == 100.0

    def test_both_zero(self):
        expected = [(1, 2026, 0.0)]
        actual = [(1, 2026, 0.0)]
        devs = compute_income_deviations(expected, actual)
        assert devs[0].deviation_pct == 0.0
        assert not devs[0].is_significant

    def test_multiple_months(self):
        expected = [(m, 2026, 10000.0) for m in range(1, 7)]
        actual = [(1, 2026, 8000.0), (2, 2026, 10000.0), (3, 2026, 6000.0)]
        devs = compute_income_deviations(expected, actual)
        assert len(devs) == 6
        sig = [d for d in devs if d.is_significant]
        # Month 1: -20%, Month 3: -40%, Months 4-6: -100%
        assert len(sig) >= 4


# ===========================================================================
# Repayment Stress
# ===========================================================================
class TestComputeRepaymentStress:
    def test_no_stress(self):
        stress = compute_repayment_stress(
            dti_ratio=0.0, missed_payments=0,
            days_overdue_avg=0.0, recent_surplus_trend=[5000, 6000, 7000],
        )
        assert stress.stress_score == 0.0
        assert stress.declining_surplus is False

    def test_high_dti(self):
        stress = compute_repayment_stress(
            dti_ratio=0.6, missed_payments=0,
            days_overdue_avg=0.0, recent_surplus_trend=[],
        )
        assert stress.stress_score == 30.0  # min(30, 0.6*50)
        assert stress.dti_ratio == 0.6

    def test_missed_payments_component(self):
        stress = compute_repayment_stress(
            dti_ratio=0.0, missed_payments=2,
            days_overdue_avg=0.0, recent_surplus_trend=[],
        )
        assert stress.stress_score == 20.0  # 2 * 10

    def test_overdue_days_component(self):
        stress = compute_repayment_stress(
            dti_ratio=0.0, missed_payments=0,
            days_overdue_avg=30.0, recent_surplus_trend=[],
        )
        assert stress.stress_score == 10.0  # min(20, 30/3)

    def test_declining_surplus(self):
        stress = compute_repayment_stress(
            dti_ratio=0.0, missed_payments=0,
            days_overdue_avg=0.0, recent_surplus_trend=[10000, 8000, 5000],
        )
        assert stress.declining_surplus is True
        assert stress.stress_score > 0

    def test_combined_factors(self):
        stress = compute_repayment_stress(
            dti_ratio=0.5, missed_payments=3,
            days_overdue_avg=60.0, recent_surplus_trend=[10000, 5000, 1000],
        )
        # DTI: min(30, 25) = 25
        # Missed: min(30, 30) = 30
        # Overdue: min(20, 20) = 20
        # Trend: some positive value
        assert stress.stress_score >= 75
        assert stress.stress_score <= 100

    def test_caps_at_100(self):
        stress = compute_repayment_stress(
            dti_ratio=1.0, missed_payments=5,
            days_overdue_avg=90.0, recent_surplus_trend=[20000, 10000, 0],
        )
        assert stress.stress_score <= 100.0

    def test_short_surplus_trend_no_decline(self):
        stress = compute_repayment_stress(
            dti_ratio=0.0, missed_payments=0,
            days_overdue_avg=0.0, recent_surplus_trend=[5000, 6000],
        )
        assert stress.declining_surplus is False


# ===========================================================================
# Alert Severity Determination
# ===========================================================================
class TestDetermineAlertSeverity:
    def _make_stress(self, score: float) -> RepaymentStressIndicator:
        return RepaymentStressIndicator(
            dti_ratio=0.3, missed_payments=0,
            days_overdue_avg=0.0, declining_surplus=False,
            stress_score=score,
        )

    def _make_deviations(self, count: int, pct: float = -30.0) -> list[IncomeDeviation]:
        return [
            IncomeDeviation(
                month=i + 1, year=2026,
                expected_income=10000, actual_income=10000 + (pct / 100 * 10000),
                deviation_pct=pct, is_significant=abs(pct) >= 20,
            )
            for i in range(count)
        ]

    def test_info_severity_low_stress(self):
        sev = determine_alert_severity(self._make_stress(10), [])
        assert sev == AlertSeverity.INFO

    def test_warning_moderate_stress(self):
        sev = determine_alert_severity(self._make_stress(35), [])
        assert sev == AlertSeverity.WARNING

    def test_warning_high_risk_category(self):
        sev = determine_alert_severity(
            self._make_stress(10), [], RiskCategory.HIGH,
        )
        assert sev == AlertSeverity.WARNING

    def test_warning_multiple_deviations(self):
        devs = self._make_deviations(3)
        sev = determine_alert_severity(self._make_stress(10), devs)
        assert sev == AlertSeverity.WARNING

    def test_critical_multi_factor_alignment(self):
        """CRITICAL requires stress>60 + 2 sig devs + high risk."""
        devs = self._make_deviations(3)
        sev = determine_alert_severity(
            self._make_stress(65), devs, RiskCategory.HIGH,
        )
        assert sev == AlertSeverity.CRITICAL

    def test_critical_very_high_stress_alone(self):
        sev = determine_alert_severity(self._make_stress(75), [])
        assert sev == AlertSeverity.CRITICAL

    def test_no_critical_without_alignment(self):
        """stress 65 alone (no devs, no high risk) → not critical via multi-factor."""
        sev = determine_alert_severity(self._make_stress(65), [])
        assert sev == AlertSeverity.WARNING


# ===========================================================================
# Alert Lifecycle
# ===========================================================================
class TestAlertLifecycle:
    def _make_alert(self, severity=AlertSeverity.INFO) -> Alert:
        return Alert.create(
            profile_id="prof-1",
            alert_type=AlertType.REPAYMENT_STRESS,
            severity=severity,
            title="Test Alert",
            description="Test Description",
        )

    def test_create_alert_defaults(self):
        alert = self._make_alert()
        assert alert.status == AlertStatus.ACTIVE
        assert alert.severity == AlertSeverity.INFO
        assert alert.is_active()
        assert alert.acknowledged_at is None
        assert alert.resolved_at is None

    def test_escalate_upwards(self):
        alert = self._make_alert(AlertSeverity.INFO)
        alert.escalate(AlertSeverity.WARNING, "Conditions worsened")
        assert alert.severity == AlertSeverity.WARNING
        assert "Escalated" in alert.description

    def test_escalate_to_critical(self):
        alert = self._make_alert(AlertSeverity.WARNING)
        alert.escalate(AlertSeverity.CRITICAL, "Emergency")
        assert alert.severity == AlertSeverity.CRITICAL

    def test_cannot_downgrade_severity(self):
        alert = self._make_alert(AlertSeverity.WARNING)
        alert.escalate(AlertSeverity.INFO, "Improved")
        assert alert.severity == AlertSeverity.WARNING  # unchanged

    def test_same_severity_no_change(self):
        alert = self._make_alert(AlertSeverity.WARNING)
        original_desc = alert.description
        alert.escalate(AlertSeverity.WARNING, "Same")
        assert alert.description == original_desc

    def test_acknowledge(self):
        alert = self._make_alert()
        alert.acknowledge()
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_at is not None
        assert alert.is_active()  # still active when acknowledged

    def test_resolve_from_active(self):
        alert = self._make_alert()
        alert.resolve()
        assert alert.status == AlertStatus.RESOLVED
        assert alert.resolved_at is not None
        assert not alert.is_active()

    def test_resolve_from_acknowledged(self):
        alert = self._make_alert()
        alert.acknowledge()
        alert.resolve()
        assert alert.status == AlertStatus.RESOLVED

    def test_cannot_acknowledge_resolved(self):
        alert = self._make_alert()
        alert.resolve()
        alert.acknowledge()  # should be no-op
        assert alert.status == AlertStatus.RESOLVED

    def test_alert_has_id(self):
        alert = self._make_alert()
        assert alert.alert_id  # not empty


# ===========================================================================
# Recommendations
# ===========================================================================
class TestGenerateRecommendations:
    def _stress(self, dti=0.0, missed=0, overdue=0.0, declining=False, score=0.0):
        return RepaymentStressIndicator(
            dti_ratio=dti, missed_payments=missed,
            days_overdue_avg=overdue, declining_surplus=declining,
            stress_score=score,
        )

    def test_high_dti_recommendation(self):
        recs = generate_recommendations(
            self._stress(dti=0.6), [], AlertSeverity.WARNING,
        )
        assert any("restructuring" in r.action.lower() for r in recs)
        assert any(r.priority == RecommendationPriority.IMMEDIATE for r in recs)

    def test_medium_dti_recommendation(self):
        recs = generate_recommendations(
            self._stress(dti=0.35), [], AlertSeverity.INFO,
        )
        assert any("additional debt" in r.action.lower() for r in recs)

    def test_missed_payment_recommendation(self):
        recs = generate_recommendations(
            self._stress(missed=2), [], AlertSeverity.WARNING,
        )
        assert any("repayment" in r.action.lower() for r in recs)

    def test_income_deviation_recommendation(self):
        devs = [IncomeDeviation(1, 2026, 10000, 7000, -30.0, True)]
        recs = generate_recommendations(self._stress(), devs, AlertSeverity.WARNING)
        assert any("income" in r.action.lower() for r in recs)

    def test_declining_surplus_recommendation(self):
        recs = generate_recommendations(
            self._stress(declining=True), [], AlertSeverity.INFO,
        )
        assert any("spending" in r.action.lower() for r in recs)

    def test_critical_emergency_recommendation(self):
        recs = generate_recommendations(
            self._stress(dti=0.7, missed=3, score=80),
            [], AlertSeverity.CRITICAL,
        )
        assert any("extension officer" in r.action.lower() for r in recs)

    def test_default_monitoring_recommendation(self):
        recs = generate_recommendations(self._stress(), [], AlertSeverity.INFO)
        assert len(recs) >= 1
        assert any("monitoring" in r.action.lower() for r in recs)


# ===========================================================================
# Build Alert (orchestrator)
# ===========================================================================
class TestBuildAlert:
    def test_build_alert_determines_type_automatically(self):
        stress = RepaymentStressIndicator(
            dti_ratio=0.5, missed_payments=2,
            days_overdue_avg=10, declining_surplus=True, stress_score=55,
        )
        alert = build_alert("prof-1", stress, [])
        assert alert.alert_type == AlertType.REPAYMENT_STRESS  # stress > 40

    def test_build_alert_income_deviation_type(self):
        stress = RepaymentStressIndicator(
            dti_ratio=0.1, missed_payments=0,
            days_overdue_avg=0, declining_surplus=False, stress_score=5,
        )
        devs = [IncomeDeviation(1, 2026, 10000, 7000, -30.0, True)]
        alert = build_alert("prof-1", stress, devs)
        assert alert.alert_type == AlertType.INCOME_DEVIATION

    def test_build_alert_over_indebtedness_type(self):
        stress = RepaymentStressIndicator(
            dti_ratio=0.6, missed_payments=0,
            days_overdue_avg=0, declining_surplus=False, stress_score=30,
        )
        alert = build_alert("prof-1", stress, [])
        assert alert.alert_type == AlertType.OVER_INDEBTEDNESS

    def test_build_alert_explicit_type(self):
        stress = RepaymentStressIndicator(
            dti_ratio=0.1, missed_payments=0,
            days_overdue_avg=0, declining_surplus=False, stress_score=5,
        )
        alert = build_alert("prof-1", stress, [], alert_type=AlertType.WEATHER_RISK)
        assert alert.alert_type == AlertType.WEATHER_RISK

    def test_build_alert_has_recommendations(self):
        stress = RepaymentStressIndicator(
            dti_ratio=0.4, missed_payments=1,
            days_overdue_avg=5, declining_surplus=True, stress_score=45,
        )
        devs = [IncomeDeviation(1, 2026, 10000, 7000, -30.0, True)]
        alert = build_alert("prof-1", stress, devs)
        assert len(alert.recommendations) > 0

    def test_build_alert_has_risk_factors(self):
        stress = RepaymentStressIndicator(
            dti_ratio=0.5, missed_payments=2,
            days_overdue_avg=15, declining_surplus=True, stress_score=60,
        )
        devs = [IncomeDeviation(1, 2026, 10000, 6000, -40.0, True)]
        alert = build_alert("prof-1", stress, devs, RiskCategory.HIGH)
        assert len(alert.risk_factors) > 0

    def test_build_alert_with_risk_category(self):
        stress = RepaymentStressIndicator(
            dti_ratio=0.3, missed_payments=0,
            days_overdue_avg=0, declining_surplus=False, stress_score=10,
        )
        alert = build_alert("prof-1", stress, [], RiskCategory.HIGH)
        assert alert.severity == AlertSeverity.WARNING  # high risk → warning


# ===========================================================================
# Scenario Simulation
# ===========================================================================
class TestSimulateScenario:
    @pytest.fixture
    def baseline(self):
        return [
            (1, 2026, 15000.0, 10000.0),
            (2, 2026, 12000.0, 10000.0),
            (3, 2026, 13000.0, 11000.0),
            (4, 2026, 30000.0, 12000.0),
            (5, 2026, 10000.0, 10000.0),
            (6, 2026, 8000.0, 13000.0),
        ]

    def test_income_shock_reduces_inflow(self, baseline):
        params = ScenarioParameters(
            scenario_type=ScenarioType.INCOME_SHOCK,
            name="30% Income Drop",
            income_reduction_pct=30.0,
            duration_months=6,
        )
        result = simulate_scenario(baseline, params)
        for p in result.projections:
            assert p.stressed_inflow == pytest.approx(p.baseline_inflow * 0.7, rel=0.01)

    def test_weather_impact(self, baseline):
        params = ScenarioParameters(
            scenario_type=ScenarioType.WEATHER_IMPACT,
            name="Drought",
            weather_adjustment=0.5,
            duration_months=3,
        )
        result = simulate_scenario(baseline, params)
        # First 3 months stressed, last 3 normal
        for p in result.projections[:3]:
            assert p.stressed_inflow == pytest.approx(p.baseline_inflow * 0.5, rel=0.01)
        for p in result.projections[3:]:
            assert p.stressed_inflow == p.baseline_inflow

    def test_market_volatility(self, baseline):
        params = ScenarioParameters(
            scenario_type=ScenarioType.MARKET_VOLATILITY,
            name="Price Drop",
            market_price_change_pct=-25.0,
            duration_months=6,
        )
        result = simulate_scenario(baseline, params)
        for p in result.projections:
            assert p.stressed_inflow == pytest.approx(p.baseline_inflow * 0.75, rel=0.01)

    def test_combined_scenario(self, baseline):
        params = ScenarioParameters(
            scenario_type=ScenarioType.COMBINED,
            name="Perfect Storm",
            income_reduction_pct=20.0,
            weather_adjustment=0.8,
            market_price_change_pct=-10.0,
            duration_months=6,
        )
        result = simulate_scenario(baseline, params)
        # Combined: 0.8 * 0.8 * 0.9 = 0.576
        for p in result.projections:
            expected = p.baseline_inflow * 0.8 * 0.8 * 0.9
            assert p.stressed_inflow == pytest.approx(expected, rel=0.01)

    def test_no_stress_scenario(self, baseline):
        params = ScenarioParameters(
            scenario_type=ScenarioType.INCOME_SHOCK,
            name="No Change",
            income_reduction_pct=0.0,
            duration_months=6,
        )
        result = simulate_scenario(baseline, params)
        for p in result.projections:
            assert p.stressed_inflow == p.baseline_inflow

    def test_simulation_has_projections(self, baseline):
        params = ScenarioParameters(
            scenario_type=ScenarioType.INCOME_SHOCK,
            name="Test",
            income_reduction_pct=20.0,
            duration_months=6,
        )
        result = simulate_scenario(baseline, params)
        assert len(result.projections) == 6

    def test_simulation_has_capacity_impact(self, baseline):
        params = ScenarioParameters(
            scenario_type=ScenarioType.INCOME_SHOCK,
            name="Test",
            income_reduction_pct=30.0,
            duration_months=6,
        )
        result = simulate_scenario(baseline, params)
        assert result.capacity_impact.emi_reduction_pct > 0
        assert result.capacity_impact.stressed_recommended_emi <= result.capacity_impact.original_recommended_emi

    def test_simulation_has_risk_level(self, baseline):
        params = ScenarioParameters(
            scenario_type=ScenarioType.INCOME_SHOCK,
            name="Severe",
            income_reduction_pct=60.0,
            duration_months=6,
        )
        result = simulate_scenario(baseline, params)
        assert result.overall_risk_level in (
            RiskCategory.LOW, RiskCategory.MEDIUM,
            RiskCategory.HIGH, RiskCategory.VERY_HIGH,
        )

    def test_simulation_has_recommendations(self, baseline):
        params = ScenarioParameters(
            scenario_type=ScenarioType.INCOME_SHOCK,
            name="Severe",
            income_reduction_pct=50.0,
            duration_months=6,
        )
        result = simulate_scenario(baseline, params)
        assert len(result.recommendations) >= 1


# ===========================================================================
# Simulation Result Aggregate Methods
# ===========================================================================
class TestSimulationResultMethods:
    def _make_result(self, projections=None) -> SimulationResult:
        projs = projections or [
            ScenarioProjection(1, 2026, 15000, 10000, 10000, 10000, 5000, 0),
            ScenarioProjection(2, 2026, 12000, 8000, 10000, 10000, 2000, -2000),
            ScenarioProjection(3, 2026, 13000, 9000, 11000, 11000, 2000, -2000),
        ]
        return SimulationResult(
            simulation_id="sim-1",
            profile_id="prof-1",
            scenario=ScenarioParameters(
                scenario_type=ScenarioType.INCOME_SHOCK, name="Test",
            ),
            projections=projs,
            capacity_impact=CapacityImpact(
                original_recommended_emi=3000, stressed_recommended_emi=1000,
                original_max_emi=5000, stressed_max_emi=2000,
                original_dscr=1.5, stressed_dscr=0.8,
                emi_reduction_pct=66.7, can_still_repay=False,
            ),
            recommendations=[],
            overall_risk_level=RiskCategory.HIGH,
        )

    def test_get_worst_month(self):
        result = self._make_result()
        worst = result.get_worst_month()
        assert worst is not None
        assert worst.stressed_net == -2000

    def test_get_total_income_loss(self):
        result = self._make_result()
        loss = result.get_total_income_loss()
        # (15000-10000) + (12000-8000) + (13000-9000) = 5000+4000+4000 = 13000
        assert loss == 13000

    def test_months_in_deficit(self):
        result = self._make_result()
        assert result.months_in_deficit() == 2

    def test_get_worst_month_empty(self):
        result = SimulationResult(
            simulation_id="sim-1",
            profile_id="prof-1",
            scenario=ScenarioParameters(
                scenario_type=ScenarioType.INCOME_SHOCK, name="Test",
            ),
            projections=[],
            capacity_impact=CapacityImpact(
                original_recommended_emi=0, stressed_recommended_emi=0,
                original_max_emi=0, stressed_max_emi=0,
                original_dscr=0, stressed_dscr=0,
                emi_reduction_pct=0, can_still_repay=False,
            ),
            recommendations=[],
            overall_risk_level=RiskCategory.HIGH,
        )
        assert result.get_worst_month() is None


# ===========================================================================
# Capacity Impact
# ===========================================================================
class TestCapacityImpact:
    def test_capacity_with_no_projections(self):
        from services.early_warning.app.domain.models import _compute_capacity_impact
        cap = _compute_capacity_impact([], 0, 5000)
        assert cap.can_still_repay is False

    def test_capacity_reduction_with_stress(self):
        from services.early_warning.app.domain.models import _compute_capacity_impact
        projs = [
            ScenarioProjection(1, 2026, 20000, 12000, 10000, 10000, 10000, 2000),
            ScenarioProjection(2, 2026, 20000, 12000, 10000, 10000, 10000, 2000),
            ScenarioProjection(3, 2026, 20000, 12000, 10000, 10000, 10000, 2000),
        ]
        cap = _compute_capacity_impact(projs, 1000, 5000)
        # original avg surplus = 10000, rec = 10000*0.4 - 1000 = 3000
        # stressed avg surplus = 2000, rec = 2000*0.4 - 1000 = max(0, -200) = 0
        # So original > stressed
        assert cap.original_recommended_emi > cap.stressed_recommended_emi
        assert cap.emi_reduction_pct > 0


# ===========================================================================
# Risk Assessment for Scenarios
# ===========================================================================
class TestAssessScenarioRisk:
    def test_low_risk(self):
        from services.early_warning.app.domain.models import _assess_scenario_risk
        cap = CapacityImpact(3000, 2500, 5000, 4000, 1.5, 1.3, 16.0, True)
        projs = [ScenarioProjection(1, 2026, 15000, 13000, 10000, 10000, 5000, 3000)]
        assert _assess_scenario_risk(cap, projs) == RiskCategory.LOW

    def test_very_high_risk(self):
        from services.early_warning.app.domain.models import _assess_scenario_risk
        cap = CapacityImpact(3000, 0, 5000, 0, 1.5, 0.3, 100.0, False)
        projs = [
            ScenarioProjection(m, 2026, 15000, 5000, 10000, 10000, 5000, -5000)
            for m in range(1, 7)
        ]
        # All 6 months in deficit, can't repay
        assert _assess_scenario_risk(cap, projs) == RiskCategory.VERY_HIGH


# ===========================================================================
# Multi-Scenario Comparison
# ===========================================================================
class TestMultiScenarioComparison:
    def test_runs_all_scenarios(self):
        baseline = [(m, 2026, 15000.0, 10000.0) for m in range(1, 7)]
        scenarios = [
            ScenarioParameters(ScenarioType.INCOME_SHOCK, "Mild", income_reduction_pct=10),
            ScenarioParameters(ScenarioType.INCOME_SHOCK, "Severe", income_reduction_pct=50),
        ]
        results = run_multi_scenario_comparison(baseline, scenarios)
        assert len(results) == 2
        # Severe should have higher risk
        mild_loss = results[0].get_total_income_loss()
        severe_loss = results[1].get_total_income_loss()
        assert severe_loss > mild_loss

    def test_single_scenario_comparison(self):
        baseline = [(1, 2026, 15000.0, 10000.0)]
        scenarios = [
            ScenarioParameters(ScenarioType.WEATHER_IMPACT, "Drought", weather_adjustment=0.5),
        ]
        results = run_multi_scenario_comparison(baseline, scenarios)
        assert len(results) == 1


# ===========================================================================
# Scenario Recommendations
# ===========================================================================
class TestScenarioRecommendations:
    def test_weather_recommendation(self):
        baseline = [(m, 2026, 15000.0, 10000.0) for m in range(1, 7)]
        params = ScenarioParameters(
            scenario_type=ScenarioType.WEATHER_IMPACT,
            name="Severe Drought",
            weather_adjustment=0.3,
            duration_months=6,
        )
        result = simulate_scenario(baseline, params)
        assert any("insurance" in r.recommendation.lower() or "weather" in r.recommendation.lower()
                    for r in result.recommendations)

    def test_market_recommendation(self):
        baseline = [(m, 2026, 15000.0, 10000.0) for m in range(1, 7)]
        params = ScenarioParameters(
            scenario_type=ScenarioType.MARKET_VOLATILITY,
            name="Price Crash",
            market_price_change_pct=-30.0,
            duration_months=6,
        )
        result = simulate_scenario(baseline, params)
        assert any("diversif" in r.recommendation.lower() or "price" in r.rationale.lower()
                    for r in result.recommendations)

    def test_low_risk_positive_recommendation(self):
        baseline = [(m, 2026, 50000.0, 10000.0) for m in range(1, 7)]
        params = ScenarioParameters(
            scenario_type=ScenarioType.INCOME_SHOCK,
            name="Tiny Drop",
            income_reduction_pct=5.0,
            duration_months=3,
        )
        result = simulate_scenario(baseline, params)
        assert any("safe to proceed" in r.recommendation.lower() for r in result.recommendations)
