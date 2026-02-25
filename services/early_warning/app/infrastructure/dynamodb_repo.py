"""DynamoDB repository for Early Warning alerts and simulations.

Single-table design following the same pattern as other services.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from services.shared.models import AlertSeverity, AlertType

from ..domain.models import (
    ActionableRecommendation,
    Alert,
    AlertStatus,
    CapacityImpact,
    RecommendationPriority,
    RiskFactorSnapshot,
    ScenarioParameters,
    ScenarioProjection,
    ScenarioRecommendation,
    ScenarioType,
    SimulationResult,
)

logger = logging.getLogger(__name__)


class DynamoDBAlertRepository:
    """DynamoDB-backed repository for alerts and simulations.

    Access patterns:
      PK: ALERT#{alert_id}           SK: METADATA         → full alert
      PK: PROFILE_ALERTS#{profile_id} SK: TS#{iso}         → alert index
      PK: SIM#{simulation_id}        SK: METADATA         → full simulation
      PK: PROFILE_SIMS#{profile_id}  SK: TS#{iso}         → simulation index
    """

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)

    # -----------------------------------------------------------------------
    # Alert persistence
    # -----------------------------------------------------------------------
    async def save_alert(self, alert: Alert) -> None:
        item = self._alert_to_item(alert)
        self._table.put_item(Item=item)

        # Also put an index item for profile-based queries
        self._table.put_item(Item={
            "PK": f"PROFILE_ALERTS#{alert.profile_id}",
            "SK": f"TS#{alert.created_at.isoformat()}#{alert.alert_id}",
            "alert_id": alert.alert_id,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "status": alert.status,
            "title": alert.title,
            "created_at": alert.created_at.isoformat(),
        })

    async def find_alert_by_id(self, alert_id: str) -> Alert | None:
        resp = self._table.get_item(Key={"PK": f"ALERT#{alert_id}", "SK": "METADATA"})
        item = resp.get("Item")
        return self._alert_from_item(item) if item else None

    async def find_alerts_by_profile(
        self, profile_id: str, limit: int = 50,
    ) -> list[Alert]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"PROFILE_ALERTS#{profile_id}"},
            ScanIndexForward=False,
            Limit=limit,
        )
        alerts: list[Alert] = []
        for index_item in resp.get("Items", []):
            alert = await self.find_alert_by_id(index_item["alert_id"])
            if alert:
                alerts.append(alert)
        return alerts

    async def find_active_alerts(self, profile_id: str) -> list[Alert]:
        all_alerts = await self.find_alerts_by_profile(profile_id, limit=100)
        return [a for a in all_alerts if a.is_active()]

    # -----------------------------------------------------------------------
    # Simulation persistence
    # -----------------------------------------------------------------------
    async def save_simulation(self, result: SimulationResult) -> None:
        item = self._simulation_to_item(result)
        self._table.put_item(Item=item)

        self._table.put_item(Item={
            "PK": f"PROFILE_SIMS#{result.profile_id}",
            "SK": f"TS#{result.created_at.isoformat()}#{result.simulation_id}",
            "simulation_id": result.simulation_id,
            "scenario_name": result.scenario.name,
            "scenario_type": result.scenario.scenario_type,
            "overall_risk_level": result.overall_risk_level,
            "created_at": result.created_at.isoformat(),
        })

    async def find_simulation_by_id(self, simulation_id: str) -> SimulationResult | None:
        resp = self._table.get_item(Key={"PK": f"SIM#{simulation_id}", "SK": "METADATA"})
        item = resp.get("Item")
        return self._simulation_from_item(item) if item else None

    async def find_simulations_by_profile(
        self, profile_id: str, limit: int = 20,
    ) -> list[SimulationResult]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"PROFILE_SIMS#{profile_id}"},
            ScanIndexForward=False,
            Limit=limit,
        )
        results: list[SimulationResult] = []
        for index_item in resp.get("Items", []):
            sim = await self.find_simulation_by_id(index_item["simulation_id"])
            if sim:
                results.append(sim)
        return results

    # -----------------------------------------------------------------------
    # Serialization — Alert
    # -----------------------------------------------------------------------
    @staticmethod
    def _alert_to_item(alert: Alert) -> dict:
        return {
            "PK": f"ALERT#{alert.alert_id}",
            "SK": "METADATA",
            "alert_id": alert.alert_id,
            "profile_id": alert.profile_id,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "status": alert.status,
            "title": alert.title,
            "description": alert.description,
            "risk_factors": json.dumps([
                {
                    "factor_name": f.factor_name,
                    "current_value": float(f.current_value),
                    "threshold": float(f.threshold),
                    "severity_contribution": f.severity_contribution,
                }
                for f in alert.risk_factors
            ]),
            "recommendations": json.dumps([
                {
                    "action": r.action,
                    "rationale": r.rationale,
                    "priority": r.priority,
                    "estimated_impact": r.estimated_impact,
                }
                for r in alert.recommendations
            ]),
            "created_at": alert.created_at.isoformat(),
            "updated_at": alert.updated_at.isoformat(),
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        }

    @staticmethod
    def _alert_from_item(item: dict) -> Alert:
        risk_factors = [
            RiskFactorSnapshot(
                factor_name=f["factor_name"],
                current_value=float(f["current_value"]),
                threshold=float(f["threshold"]),
                severity_contribution=f["severity_contribution"],
            )
            for f in json.loads(item.get("risk_factors", "[]"))
        ]
        recommendations = [
            ActionableRecommendation(
                action=r["action"],
                rationale=r["rationale"],
                priority=RecommendationPriority(r["priority"]),
                estimated_impact=r["estimated_impact"],
            )
            for r in json.loads(item.get("recommendations", "[]"))
        ]
        return Alert(
            alert_id=item["alert_id"],
            profile_id=item["profile_id"],
            alert_type=AlertType(item["alert_type"]),
            severity=AlertSeverity(item["severity"]),
            status=AlertStatus(item["status"]),
            title=item["title"],
            description=item["description"],
            risk_factors=risk_factors,
            recommendations=recommendations,
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
            acknowledged_at=datetime.fromisoformat(item["acknowledged_at"]) if item.get("acknowledged_at") else None,
            resolved_at=datetime.fromisoformat(item["resolved_at"]) if item.get("resolved_at") else None,
        )

    # -----------------------------------------------------------------------
    # Serialization — Simulation
    # -----------------------------------------------------------------------
    @staticmethod
    def _simulation_to_item(result: SimulationResult) -> dict:
        return {
            "PK": f"SIM#{result.simulation_id}",
            "SK": "METADATA",
            "simulation_id": result.simulation_id,
            "profile_id": result.profile_id,
            "scenario": json.dumps({
                "scenario_type": result.scenario.scenario_type,
                "name": result.scenario.name,
                "description": result.scenario.description,
                "income_reduction_pct": float(result.scenario.income_reduction_pct),
                "weather_adjustment": float(result.scenario.weather_adjustment),
                "market_price_change_pct": float(result.scenario.market_price_change_pct),
                "duration_months": result.scenario.duration_months,
                "existing_monthly_obligations": float(result.scenario.existing_monthly_obligations),
                "household_monthly_expense": float(result.scenario.household_monthly_expense),
            }),
            "projections": json.dumps([
                {
                    "month": p.month, "year": p.year,
                    "baseline_inflow": float(p.baseline_inflow),
                    "stressed_inflow": float(p.stressed_inflow),
                    "baseline_outflow": float(p.baseline_outflow),
                    "stressed_outflow": float(p.stressed_outflow),
                    "baseline_net": float(p.baseline_net),
                    "stressed_net": float(p.stressed_net),
                }
                for p in result.projections
            ]),
            "capacity_impact": json.dumps({
                "original_recommended_emi": float(result.capacity_impact.original_recommended_emi),
                "stressed_recommended_emi": float(result.capacity_impact.stressed_recommended_emi),
                "original_max_emi": float(result.capacity_impact.original_max_emi),
                "stressed_max_emi": float(result.capacity_impact.stressed_max_emi),
                "original_dscr": float(result.capacity_impact.original_dscr),
                "stressed_dscr": float(result.capacity_impact.stressed_dscr),
                "emi_reduction_pct": float(result.capacity_impact.emi_reduction_pct),
                "can_still_repay": result.capacity_impact.can_still_repay,
            }),
            "recommendations": json.dumps([
                {
                    "recommendation": r.recommendation,
                    "risk_level": r.risk_level,
                    "confidence": r.confidence,
                    "rationale": r.rationale,
                }
                for r in result.recommendations
            ]),
            "overall_risk_level": result.overall_risk_level,
            "created_at": result.created_at.isoformat(),
        }

    @staticmethod
    def _simulation_from_item(item: dict) -> SimulationResult:
        scenario_data = json.loads(item["scenario"])
        projections_data = json.loads(item["projections"])
        capacity_data = json.loads(item["capacity_impact"])
        recs_data = json.loads(item["recommendations"])

        return SimulationResult(
            simulation_id=item["simulation_id"],
            profile_id=item["profile_id"],
            scenario=ScenarioParameters(
                scenario_type=ScenarioType(scenario_data["scenario_type"]),
                name=scenario_data["name"],
                description=scenario_data.get("description", ""),
                income_reduction_pct=float(scenario_data.get("income_reduction_pct", 0)),
                weather_adjustment=float(scenario_data.get("weather_adjustment", 1.0)),
                market_price_change_pct=float(scenario_data.get("market_price_change_pct", 0)),
                duration_months=int(scenario_data.get("duration_months", 6)),
                existing_monthly_obligations=float(scenario_data.get("existing_monthly_obligations", 0)),
                household_monthly_expense=float(scenario_data.get("household_monthly_expense", 5000)),
            ),
            projections=[
                ScenarioProjection(
                    month=p["month"], year=p["year"],
                    baseline_inflow=float(p["baseline_inflow"]),
                    stressed_inflow=float(p["stressed_inflow"]),
                    baseline_outflow=float(p["baseline_outflow"]),
                    stressed_outflow=float(p["stressed_outflow"]),
                    baseline_net=float(p["baseline_net"]),
                    stressed_net=float(p["stressed_net"]),
                )
                for p in projections_data
            ],
            capacity_impact=CapacityImpact(
                original_recommended_emi=float(capacity_data["original_recommended_emi"]),
                stressed_recommended_emi=float(capacity_data["stressed_recommended_emi"]),
                original_max_emi=float(capacity_data["original_max_emi"]),
                stressed_max_emi=float(capacity_data["stressed_max_emi"]),
                original_dscr=float(capacity_data["original_dscr"]),
                stressed_dscr=float(capacity_data["stressed_dscr"]),
                emi_reduction_pct=float(capacity_data["emi_reduction_pct"]),
                can_still_repay=bool(capacity_data["can_still_repay"]),
            ),
            recommendations=[
                ScenarioRecommendation(
                    recommendation=r["recommendation"],
                    risk_level=r["risk_level"],
                    confidence=r["confidence"],
                    rationale=r["rationale"],
                )
                for r in recs_data
            ],
            overall_risk_level=item["overall_risk_level"],
            created_at=datetime.fromisoformat(item["created_at"]),
        )
