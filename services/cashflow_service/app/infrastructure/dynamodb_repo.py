"""DynamoDB repository — implements CashFlowRepository port.

Single-table design with access patterns:
- PK: FORECAST#{id}                 SK: METADATA      → Forecast data
- PK: PROFILE_FORECASTS#{profile_id} SK: TS#{iso}      → Profile → forecasts index
- PK: RECORD#{id}                   SK: METADATA      → CashFlow record
- PK: PROFILE_RECORDS#{profile_id}  SK: REC#{id}      → Profile → records index
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from services.cashflow_service.app.domain.models import (
    CashFlowCategory,
    CashFlowForecast,
    CashFlowRecord,
    FlowDirection,
    ForecastAssumption,
    ForecastConfidence,
    MonthlyProjection,
    RepaymentCapacity,
    SeasonalPattern,
    TimingWindow,
    UncertaintyBand,
)
from services.shared.models import Season

logger = logging.getLogger(__name__)


class DynamoDBCashFlowRepository:
    """Concrete adapter implementing the CashFlowRepository port."""

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)
        self._table_name = table_name

    # ------------------------------------------------------------------
    # Forecast persistence
    # ------------------------------------------------------------------

    async def save_forecast(self, forecast: CashFlowForecast) -> None:
        item = self._forecast_to_item(forecast)
        self._table.put_item(Item=item)

        # Time-sorted index for profile → forecasts
        self._table.put_item(Item={
            "PK": f"PROFILE_FORECASTS#{forecast.profile_id}",
            "SK": f"TS#{forecast.created_at.isoformat()}",
            "forecast_id": forecast.forecast_id,
            "profile_id": forecast.profile_id,
            "total_inflow": str(forecast.get_total_projected_inflow()),
            "total_outflow": str(forecast.get_total_projected_outflow()),
            "recommended_emi": str(forecast.repayment_capacity.recommended_emi),
            "model_version": forecast.model_version,
            "created_at": forecast.created_at.isoformat(),
        })

        logger.debug("Saved forecast %s to DynamoDB", forecast.forecast_id)

    async def find_forecast_by_id(self, forecast_id: str) -> CashFlowForecast | None:
        response = self._table.get_item(
            Key={"PK": f"FORECAST#{forecast_id}", "SK": "METADATA"},
        )
        item = response.get("Item")
        if not item:
            return None
        return self._forecast_from_item(item)

    async def find_latest_forecast(self, profile_id: str) -> CashFlowForecast | None:
        response = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"PROFILE_FORECASTS#{profile_id}",
                ":sk_prefix": "TS#",
            },
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            return None
        return await self.find_forecast_by_id(items[0]["forecast_id"])

    async def find_forecast_history(
        self, profile_id: str, limit: int = 10,
    ) -> list[CashFlowForecast]:
        response = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"PROFILE_FORECASTS#{profile_id}",
                ":sk_prefix": "TS#",
            },
            ScanIndexForward=False,
            Limit=limit,
        )
        items = response.get("Items", [])
        forecasts: list[CashFlowForecast] = []
        for idx_item in items:
            fc = await self.find_forecast_by_id(idx_item["forecast_id"])
            if fc:
                forecasts.append(fc)
        return forecasts

    # ------------------------------------------------------------------
    # Record persistence
    # ------------------------------------------------------------------

    async def save_record(self, record: CashFlowRecord) -> None:
        item = self._record_to_item(record)
        self._table.put_item(Item=item)

        # Index: profile → records
        self._table.put_item(Item={
            "PK": f"PROFILE_RECORDS#{record.profile_id}",
            "SK": f"REC#{record.record_id}",
            "record_id": record.record_id,
            "category": record.category.value,
            "direction": record.direction.value,
            "amount": str(record.amount),
            "month": record.month,
            "year": record.year,
        })

        logger.debug("Saved record %s to DynamoDB", record.record_id)

    async def save_records(self, records: list[CashFlowRecord]) -> None:
        for record in records:
            await self.save_record(record)

    async def find_records_by_profile(
        self, profile_id: str, limit: int = 200,
    ) -> list[CashFlowRecord]:
        response = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"PROFILE_RECORDS#{profile_id}",
                ":sk_prefix": "REC#",
            },
            Limit=limit,
        )
        index_items = response.get("Items", [])

        records: list[CashFlowRecord] = []
        for idx_item in index_items:
            rec = await self._find_record_by_id(idx_item["record_id"])
            if rec:
                records.append(rec)
        return records

    async def _find_record_by_id(self, record_id: str) -> CashFlowRecord | None:
        response = self._table.get_item(
            Key={"PK": f"RECORD#{record_id}", "SK": "METADATA"},
        )
        item = response.get("Item")
        if not item:
            return None
        return self._record_from_item(item)

    # ------------------------------------------------------------------
    # Serialization — Forecast
    # ------------------------------------------------------------------

    def _forecast_to_item(self, fc: CashFlowForecast) -> dict[str, Any]:
        return {
            "PK": f"FORECAST#{fc.forecast_id}",
            "SK": "METADATA",
            "forecast_id": fc.forecast_id,
            "profile_id": fc.profile_id,
            "start_month": fc.forecast_period_start_month,
            "start_year": fc.forecast_period_start_year,
            "end_month": fc.forecast_period_end_month,
            "end_year": fc.forecast_period_end_year,
            "projections": json.dumps([
                {
                    "month": p.month, "year": p.year,
                    "inflow": str(p.projected_inflow),
                    "outflow": str(p.projected_outflow),
                    "net": str(p.net_cash_flow),
                    "confidence": p.confidence.value,
                    "notes": p.notes,
                }
                for p in fc.monthly_projections
            ]),
            "seasonal_patterns": json.dumps([
                {
                    "category": s.category.value,
                    "direction": s.direction.value,
                    "season": s.season.value,
                    "months": s.months,
                    "avg_amount": str(s.average_monthly_amount),
                    "peak_month": s.peak_month,
                    "cv": str(s.variability_cv),
                }
                for s in fc.seasonal_patterns
            ]),
            "uncertainty_bands": json.dumps([
                {
                    "month": u.month, "year": u.year,
                    "lower": str(u.lower_bound),
                    "expected": str(u.expected),
                    "upper": str(u.upper_bound),
                }
                for u in fc.uncertainty_bands
            ]),
            "assumptions": json.dumps([
                {"factor": a.factor, "description": a.description, "impact": a.impact}
                for a in fc.assumptions
            ]),
            "capacity": json.dumps({
                "profile_id": fc.repayment_capacity.profile_id,
                "surplus_avg": str(fc.repayment_capacity.monthly_surplus_avg),
                "surplus_min": str(fc.repayment_capacity.monthly_surplus_min),
                "max_emi": str(fc.repayment_capacity.max_affordable_emi),
                "rec_emi": str(fc.repayment_capacity.recommended_emi),
                "emergency": str(fc.repayment_capacity.emergency_reserve),
                "annual_cap": str(fc.repayment_capacity.annual_repayment_capacity),
                "dscr": str(fc.repayment_capacity.debt_service_coverage_ratio),
                "computed_at": fc.repayment_capacity.computed_at.isoformat(),
            }),
            "timing_windows": json.dumps([
                {
                    "start_month": t.start_month, "start_year": t.start_year,
                    "end_month": t.end_month, "end_year": t.end_year,
                    "score": str(t.suitability_score), "reason": t.reason,
                }
                for t in fc.timing_windows
            ]),
            "model_version": fc.model_version,
            "created_at": fc.created_at.isoformat(),
            "updated_at": fc.updated_at.isoformat(),
        }

    def _forecast_from_item(self, item: dict[str, Any]) -> CashFlowForecast:
        projs_raw = json.loads(item.get("projections", "[]"))
        projections = [
            MonthlyProjection(
                month=p["month"], year=p["year"],
                projected_inflow=float(p["inflow"]),
                projected_outflow=float(p["outflow"]),
                net_cash_flow=float(p["net"]),
                confidence=ForecastConfidence(p["confidence"]),
                notes=p.get("notes", ""),
            )
            for p in projs_raw
        ]

        patterns_raw = json.loads(item.get("seasonal_patterns", "[]"))
        patterns = [
            SeasonalPattern(
                category=CashFlowCategory(s["category"]),
                direction=FlowDirection(s["direction"]),
                season=Season(s["season"]),
                months=s["months"],
                average_monthly_amount=float(s["avg_amount"]),
                peak_month=s["peak_month"],
                variability_cv=float(s["cv"]),
            )
            for s in patterns_raw
        ]

        bands_raw = json.loads(item.get("uncertainty_bands", "[]"))
        bands = [
            UncertaintyBand(
                month=u["month"], year=u["year"],
                lower_bound=float(u["lower"]),
                expected=float(u["expected"]),
                upper_bound=float(u["upper"]),
            )
            for u in bands_raw
        ]

        assumptions_raw = json.loads(item.get("assumptions", "[]"))
        assumptions = [
            ForecastAssumption(
                factor=a["factor"], description=a["description"], impact=a["impact"],
            )
            for a in assumptions_raw
        ]

        cap_raw = json.loads(item.get("capacity", "{}"))
        capacity = RepaymentCapacity(
            profile_id=cap_raw["profile_id"],
            monthly_surplus_avg=float(cap_raw["surplus_avg"]),
            monthly_surplus_min=float(cap_raw["surplus_min"]),
            max_affordable_emi=float(cap_raw["max_emi"]),
            recommended_emi=float(cap_raw["rec_emi"]),
            emergency_reserve=float(cap_raw["emergency"]),
            annual_repayment_capacity=float(cap_raw["annual_cap"]),
            debt_service_coverage_ratio=float(cap_raw["dscr"]),
            computed_at=datetime.fromisoformat(cap_raw["computed_at"]),
        )

        timing_raw = json.loads(item.get("timing_windows", "[]"))
        timing = [
            TimingWindow(
                start_month=t["start_month"], start_year=t["start_year"],
                end_month=t["end_month"], end_year=t["end_year"],
                suitability_score=float(t["score"]), reason=t["reason"],
            )
            for t in timing_raw
        ]

        return CashFlowForecast(
            forecast_id=item["forecast_id"],
            profile_id=item["profile_id"],
            forecast_period_start_month=int(item["start_month"]),
            forecast_period_start_year=int(item["start_year"]),
            forecast_period_end_month=int(item["end_month"]),
            forecast_period_end_year=int(item["end_year"]),
            monthly_projections=projections,
            seasonal_patterns=patterns,
            uncertainty_bands=bands,
            assumptions=assumptions,
            repayment_capacity=capacity,
            timing_windows=timing,
            model_version=item.get("model_version", "seasonal-avg-v1"),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )

    # ------------------------------------------------------------------
    # Serialization — Record
    # ------------------------------------------------------------------

    def _record_to_item(self, record: CashFlowRecord) -> dict[str, Any]:
        return {
            "PK": f"RECORD#{record.record_id}",
            "SK": "METADATA",
            "record_id": record.record_id,
            "profile_id": record.profile_id,
            "category": record.category.value,
            "direction": record.direction.value,
            "amount": str(record.amount),
            "month": record.month,
            "year": record.year,
            "season": record.season.value if record.season else "",
            "notes": record.notes,
            "recorded_at": record.recorded_at.isoformat(),
        }

    def _record_from_item(self, item: dict[str, Any]) -> CashFlowRecord:
        season_str = item.get("season", "")
        season = Season(season_str) if season_str else None

        return CashFlowRecord(
            record_id=item["record_id"],
            profile_id=item["profile_id"],
            category=CashFlowCategory(item["category"]),
            direction=FlowDirection(item["direction"]),
            amount=float(item["amount"]),
            month=int(item["month"]),
            year=int(item["year"]),
            season=season,
            notes=item.get("notes", ""),
            recorded_at=datetime.fromisoformat(item["recorded_at"]),
        )
