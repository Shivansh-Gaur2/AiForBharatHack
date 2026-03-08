"""Early Warning & Scenario domain service — orchestrates use cases.

Consumes data from Risk, CashFlow, Loan, and Profile services (via ports),
generates alerts, runs scenario simulations, and publishes events.

Uses the FusionAnomalyDetector (fusion-anomaly-v1) from the shared AI layer
to augment rule-based detection with statistical anomaly detection.
"""

from __future__ import annotations

import logging
from statistics import mean

from services.shared.events import AsyncEventPublisher, DomainEvent
from services.shared.models import AlertSeverity, AlertType, ProfileId, RiskCategory

from .interfaces import (
    AlertRepository,
    CashFlowDataProvider,
    LoanDataProvider,
    ProfileDataProvider,
    RiskDataProvider,
    SmsNotifier,
)
from .models import (
    ActionableRecommendation,
    Alert,
    RecommendationPriority,
    RiskFactorSnapshot,
    ScenarioParameters,
    SimulationResult,
    build_alert,
    compute_income_deviations,
    compute_repayment_stress,
    run_multi_scenario_comparison,
    simulate_scenario,
)
from .validators import (
    validate_monitor_request,
    validate_multi_scenario_request,
    validate_scenario_params,
)

logger = logging.getLogger(__name__)


def _ai_anomaly_check(
    projections: list[tuple],
    exposure: dict,
    repayment_stats: dict,
) -> dict | None:
    """Run the FusionAnomalyDetector; return enrichment dict or None."""
    try:
        from services.shared.ai import get_anomaly_detector

        detector = get_anomaly_detector()

        recent_flows = [
            {"inflow": inf, "outflow": outf}
            for _, _, inf, outf in projections[-12:]
        ]
        if not recent_flows:
            return None

        inflows = [f["inflow"] for f in recent_flows]
        avg_inflow = mean(inflows) if inflows else 0.0
        total_reps = repayment_stats.get("total_repayments", 1) or 1

        baseline = {
            "avg_monthly_inflow": avg_inflow,
            "dti_ratio": exposure.get("debt_to_income_ratio", 0.0),
            "missed_payments_pct": (
                repayment_stats.get("missed_payments", 0) / total_reps
            ),
            "consecutive_deficit_months": sum(
                1 for f in recent_flows[-6:] if f["inflow"] < f["outflow"]
            ),
        }

        result = detector.detect_anomalies(recent_flows, baseline)
        return {
            "is_anomalous": result.is_anomalous,
            "anomaly_score": result.anomaly_score,
            "severity": result.severity,
            "deviating_features": result.deviating_features,
            "recommended_actions": result.recommended_actions,
        }
    except Exception:
        logger.warning(
            "FusionAnomalyDetector unavailable, proceeding with rules only",
            exc_info=True,
        )
        return None


class EarlyWarningService:
    """Application service for Early Warning & Scenario Simulation.

    Req 5.1–5.5 (Early Warning), Req 6.1–6.5 (Scenario Simulation).
    """

    def __init__(
        self,
        repo: AlertRepository,
        risk_provider: RiskDataProvider,
        cashflow_provider: CashFlowDataProvider,
        loan_provider: LoanDataProvider,
        profile_provider: ProfileDataProvider,
        events: AsyncEventPublisher,
        sms_notifier: SmsNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._risk = risk_provider
        self._cashflow = cashflow_provider
        self._loans = loan_provider
        self._profiles = profile_provider
        self._events = events
        self._sms = sms_notifier

    # -----------------------------------------------------------------------
    # Internal: SMS dispatch helper
    # -----------------------------------------------------------------------
    async def _dispatch_sms(self, profile_id: ProfileId, alert: Alert) -> None:
        """Send SMS for WARNING/CRITICAL alerts. Fire-and-forget."""
        if self._sms is None:
            return
        if alert.severity not in (
            AlertSeverity.WARNING.value,
            AlertSeverity.CRITICAL.value,
            AlertSeverity.WARNING,
            AlertSeverity.CRITICAL,
        ):
            return

        try:
            phone = await self._profiles.get_phone_number(profile_id)
            if not phone:
                logger.debug("No phone for profile %s, skipping SMS", profile_id)
                return

            lang = await self._profiles.get_preferred_language(profile_id)

            # Build localised message
            try:
                from services.shared.localization import Translator
                t = Translator(lang)
                message = t.translate(
                    "alert_sms",
                    severity=str(alert.severity),
                    title=alert.title,
                )
            except Exception:
                message = (
                    f"[{alert.severity}] {alert.title}. "
                    f"Please check your Rural Credit Advisory dashboard."
                )

            await self._sms.send_alert_sms(phone, message[:160])
        except Exception:
            logger.warning("SMS dispatch failed for profile %s", profile_id, exc_info=True)

    # -----------------------------------------------------------------------
    # Early Warning — Monitoring & Alert Generation
    # -----------------------------------------------------------------------
    async def monitor_and_alert(self, profile_id: ProfileId) -> Alert:
        """Run full monitoring pipeline: gather data → detect stress → generate alert.

        Cross-service orchestration: fetches from Risk, CashFlow, Loan, Profile.
        Req 5.1, 5.2, 5.3, 5.4.
        """
        validate_monitor_request(profile_id)

        # Gather data from other services
        risk_cat_str = await self._risk.get_latest_risk_category(profile_id)
        risk_category = RiskCategory(risk_cat_str) if risk_cat_str else None

        projections = await self._cashflow.get_latest_forecast_projections(profile_id)
        expected_incomes = [(m, y, inf) for m, y, inf, _ in projections]

        actual_incomes = await self._profiles.get_actual_incomes(profile_id)

        exposure = await self._loans.get_debt_exposure(profile_id)
        repayment_stats = await self._loans.get_repayment_stats(profile_id)

        # Record data lineage (fire-and-forget)
        try:
            from services.shared.lineage import record_data_access
            await record_data_access(
                profile_id=profile_id,
                accessed_by="early-warning",
                access_type="READ",
                fields_accessed=["risk_category", "forecast_projections", "actual_incomes", "debt_exposure", "repayment_stats"],
                purpose="early warning monitoring",
            )
        except Exception:
            pass

        # Compute deviations
        deviations = compute_income_deviations(expected_incomes, actual_incomes)

        # Compute repayment stress
        # Build surplus trend from projections
        surplus_trend = [inf - outf for _, _, inf, outf in projections[-6:]]
        stress = compute_repayment_stress(
            dti_ratio=exposure.get("debt_to_income_ratio", 0.0),
            missed_payments=repayment_stats.get("missed_payments", 0),
            days_overdue_avg=repayment_stats.get("days_overdue_avg", 0.0),
            recent_surplus_trend=surplus_trend,
        )

        # Build alert (rule-based)
        alert = build_alert(
            profile_id=profile_id,
            stress=stress,
            deviations=deviations,
            risk_category=risk_category,
        )

        # ── AI Anomaly Augmentation ──────────────────────────────
        ai_result = _ai_anomaly_check(projections, exposure, repayment_stats)
        if ai_result and ai_result["is_anomalous"]:
            # Escalate severity if AI detects higher severity
            ai_sev_map = {
                "CRITICAL": AlertSeverity.CRITICAL,
                "WARNING": AlertSeverity.WARNING,
                "INFO": AlertSeverity.INFO,
            }
            ai_sev = ai_sev_map.get(ai_result["severity"], AlertSeverity.INFO)
            sev_rank = {AlertSeverity.INFO: 0, AlertSeverity.WARNING: 1, AlertSeverity.CRITICAL: 2}
            if sev_rank.get(ai_sev, 0) > sev_rank.get(AlertSeverity(alert.severity), 0):
                alert.escalate(ai_sev, "AI anomaly detector flagged higher severity")

            # Append AI-detected anomaly features as risk factor snapshots
            for feat in ai_result["deviating_features"]:
                alert.risk_factors.append(RiskFactorSnapshot(
                    factor_name=f"AI: {feat}",
                    current_value=ai_result["anomaly_score"],
                    threshold=0.5,
                    severity_contribution=ai_result["anomaly_score"] * 0.3,
                ))

            # Append AI recommended actions
            for action in ai_result["recommended_actions"]:
                alert.recommendations.append(ActionableRecommendation(
                    action=action,
                    rationale="Generated by FusionAnomalyDetector (fusion-anomaly-v1)",
                    priority=RecommendationPriority.IMMEDIATE
                    if ai_result["severity"] == "CRITICAL"
                    else RecommendationPriority.SHORT_TERM,
                    estimated_impact="AI-assessed anomaly mitigation",
                ))
            logger.info(
                "AI anomaly detector enriched alert %s: score=%.2f sev=%s",
                alert.alert_id, ai_result["anomaly_score"], ai_result["severity"],
            )

        # Persist
        await self._repo.save_alert(alert)

        # Publish event
        await self._events.publish(DomainEvent(
            event_type="alert.generated",
            aggregate_id=alert.alert_id,
            payload={
                "profile_id": profile_id,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "title": alert.title,
            },
        ))

        logger.info(
            "Alert generated: %s severity=%s for profile %s",
            alert.alert_id, alert.severity, profile_id,
        )

        # Dispatch SMS for WARNING/CRITICAL (fire-and-forget)
        await self._dispatch_sms(profile_id, alert)

        return alert

    async def generate_alert_direct(
        self,
        profile_id: ProfileId,
        dti_ratio: float = 0.0,
        missed_payments: int = 0,
        days_overdue_avg: float = 0.0,
        recent_surplus_trend: list[float] | None = None,
        expected_incomes: list[tuple[int, int, float]] | None = None,
        actual_incomes: list[tuple[int, int, float]] | None = None,
        risk_category: str | None = None,
        alert_type: str | None = None,
    ) -> Alert:
        """Generate an alert from directly-provided data (no cross-service calls).

        Useful for testing and for event-driven triggers.
        """
        validate_monitor_request(profile_id)

        deviations = compute_income_deviations(
            expected_incomes or [], actual_incomes or [],
        )

        stress = compute_repayment_stress(
            dti_ratio=dti_ratio,
            missed_payments=missed_payments,
            days_overdue_avg=days_overdue_avg,
            recent_surplus_trend=recent_surplus_trend or [],
        )

        risk_cat = RiskCategory(risk_category) if risk_category else None
        a_type = AlertType(alert_type) if alert_type else None

        alert = build_alert(
            profile_id=profile_id,
            stress=stress,
            deviations=deviations,
            risk_category=risk_cat,
            alert_type=a_type,
        )

        await self._repo.save_alert(alert)

        await self._events.publish(DomainEvent(
            event_type="alert.generated",
            aggregate_id=alert.alert_id,
            payload={
                "profile_id": profile_id,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
            },
        ))

        return alert

    async def escalate_alert(
        self, alert_id: str, new_severity: str, reason: str,
    ) -> Alert:
        """Escalate an existing alert to a higher severity (Req 5.3)."""
        from services.shared.models import AlertSeverity

        alert = await self._repo.find_alert_by_id(alert_id)
        if alert is None:
            raise ValueError(f"Alert {alert_id} not found")

        alert.escalate(AlertSeverity(new_severity), reason)
        await self._repo.save_alert(alert)

        await self._events.publish(DomainEvent(
            event_type="alert.escalated",
            aggregate_id=alert.alert_id,
            payload={
                "profile_id": alert.profile_id,
                "new_severity": new_severity,
                "reason": reason,
            },
        ))

        # SMS on escalation
        await self._dispatch_sms(alert.profile_id, alert)

        return alert

    async def acknowledge_alert(self, alert_id: str) -> Alert:
        """Mark an alert as acknowledged."""
        alert = await self._repo.find_alert_by_id(alert_id)
        if alert is None:
            raise ValueError(f"Alert {alert_id} not found")

        alert.acknowledge()
        await self._repo.save_alert(alert)
        return alert

    async def resolve_alert(self, alert_id: str) -> Alert:
        """Mark an alert as resolved."""
        alert = await self._repo.find_alert_by_id(alert_id)
        if alert is None:
            raise ValueError(f"Alert {alert_id} not found")

        alert.resolve()
        await self._repo.save_alert(alert)
        return alert

    # -----------------------------------------------------------------------
    # Queries — Alerts
    # -----------------------------------------------------------------------
    async def get_alert(self, alert_id: str) -> Alert | None:
        return await self._repo.find_alert_by_id(alert_id)

    async def get_alerts_for_profile(
        self, profile_id: ProfileId, limit: int = 50,
    ) -> list[Alert]:
        return await self._repo.find_alerts_by_profile(profile_id, limit)

    async def get_active_alerts(self, profile_id: ProfileId) -> list[Alert]:
        return await self._repo.find_active_alerts(profile_id)

    # -----------------------------------------------------------------------
    # Scenario Simulation
    # -----------------------------------------------------------------------
    async def run_scenario(
        self, profile_id: ProfileId, params: ScenarioParameters,
    ) -> SimulationResult:
        """Run a single scenario simulation against the profile's cash flow forecast.

        Cross-service: fetches baseline projections from Cash Flow service.
        Req 6.1, 6.2, 6.3, 6.4, 6.5.
        """
        validate_scenario_params(params)

        # Get baseline from cash flow service
        projections = await self._cashflow.get_latest_forecast_projections(profile_id)
        if not projections:
            raise ValueError(f"No cash flow forecast found for profile {profile_id}")

        capacity = await self._cashflow.get_repayment_capacity(profile_id)  # noqa: F841
        household_expense = await self._profiles.get_household_expense(profile_id)
        exposure = await self._loans.get_debt_exposure(profile_id)

        result = simulate_scenario(
            baseline_projections=projections,
            params=params,
            existing_monthly_obligations=exposure.get("monthly_obligations", 0.0),
            household_monthly_expense=household_expense,
        )
        # Set profile_id on result
        object.__setattr__(result, "profile_id", profile_id)

        await self._repo.save_simulation(result)

        await self._events.publish(DomainEvent(
            event_type="scenario.simulated",
            aggregate_id=result.simulation_id,
            payload={
                "profile_id": profile_id,
                "scenario_type": params.scenario_type,
                "risk_level": result.overall_risk_level,
            },
        ))

        return result

    async def run_scenario_direct(
        self,
        profile_id: ProfileId,
        params: ScenarioParameters,
        baseline_projections: list[tuple[int, int, float, float]],
        existing_obligations: float = 0.0,
        household_expense: float = 5000.0,
    ) -> SimulationResult:
        """Run a scenario with directly-provided baseline data (no cross-service calls)."""
        validate_scenario_params(params)

        if not baseline_projections:
            raise ValueError("At least one baseline projection is required")

        result = simulate_scenario(
            baseline_projections=baseline_projections,
            params=params,
            existing_monthly_obligations=existing_obligations,
            household_monthly_expense=household_expense,
        )
        object.__setattr__(result, "profile_id", profile_id)

        await self._repo.save_simulation(result)

        await self._events.publish(DomainEvent(
            event_type="scenario.simulated",
            aggregate_id=result.simulation_id,
            payload={
                "profile_id": profile_id,
                "scenario_type": params.scenario_type,
                "risk_level": result.overall_risk_level,
            },
        ))

        return result

    async def compare_scenarios(
        self,
        profile_id: ProfileId,
        scenarios: list[ScenarioParameters],
    ) -> list[SimulationResult]:
        """Run multiple scenarios and return for side-by-side comparison (Req 6.1)."""
        validate_multi_scenario_request(scenarios)

        projections = await self._cashflow.get_latest_forecast_projections(profile_id)
        if not projections:
            raise ValueError(f"No cash flow forecast found for profile {profile_id}")

        exposure = await self._loans.get_debt_exposure(profile_id)
        household_expense = await self._profiles.get_household_expense(profile_id)

        results = run_multi_scenario_comparison(
            baseline_projections=projections,
            scenarios=scenarios,
            existing_obligations=exposure.get("monthly_obligations", 0.0),
            household_expense=household_expense,
        )

        for result in results:
            object.__setattr__(result, "profile_id", profile_id)
            await self._repo.save_simulation(result)

        return results

    async def compare_scenarios_direct(
        self,
        profile_id: ProfileId,
        scenarios: list[ScenarioParameters],
        baseline_projections: list[tuple[int, int, float, float]],
        existing_obligations: float = 0.0,
        household_expense: float = 5000.0,
    ) -> list[SimulationResult]:
        """Compare scenarios with directly-provided data."""
        validate_multi_scenario_request(scenarios)

        if not baseline_projections:
            raise ValueError("At least one baseline projection is required")

        results = run_multi_scenario_comparison(
            baseline_projections=baseline_projections,
            scenarios=scenarios,
            existing_obligations=existing_obligations,
            household_expense=household_expense,
        )

        for result in results:
            object.__setattr__(result, "profile_id", profile_id)
            await self._repo.save_simulation(result)

        return results

    # -----------------------------------------------------------------------
    # Queries — Simulations
    # -----------------------------------------------------------------------
    async def get_simulation(self, simulation_id: str) -> SimulationResult | None:
        return await self._repo.find_simulation_by_id(simulation_id)

    async def get_simulation_history(
        self, profile_id: ProfileId, limit: int = 20,
    ) -> list[SimulationResult]:
        return await self._repo.find_simulations_by_profile(profile_id, limit)
