"""DynamoDB repository — implements RiskAssessmentRepository port.

Access patterns:
- PK: RISK#{assessment_id}       SK: METADATA        → Assessment data
- PK: PROFILE_RISK#{profile_id}  SK: TS#{iso_ts}     → Profile → assessments (sorted by time)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from services.risk_assessment.app.domain.models import (
    RiskAssessment,
    RiskExplanation,
    RiskFactor,
    RiskFactorType,
)
from services.shared.models import RiskCategory

logger = logging.getLogger(__name__)


class DynamoDBRiskRepository:
    """Concrete adapter implementing RiskAssessmentRepository port."""

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)

    async def save(self, assessment: RiskAssessment) -> None:
        item = self._to_item(assessment)
        self._table.put_item(Item=item)

        # Time-sorted index: profile → assessments
        self._table.put_item(Item={
            "PK": f"PROFILE_RISK#{assessment.profile_id}",
            "SK": f"TS#{assessment.created_at.isoformat()}",
            "assessment_id": assessment.assessment_id,
            "risk_score": assessment.risk_score,
            "risk_category": assessment.risk_category.value,
            "confidence_level": str(assessment.confidence_level),
            "created_at": assessment.created_at.isoformat(),
        })

        logger.debug("Saved risk assessment %s", assessment.assessment_id)

    async def find_by_id(self, assessment_id: str) -> RiskAssessment | None:
        response = self._table.get_item(
            Key={"PK": f"RISK#{assessment_id}", "SK": "METADATA"}
        )
        item = response.get("Item")
        if not item:
            return None
        return self._from_item(item)

    async def find_latest(self, profile_id: str) -> RiskAssessment | None:
        response = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={
                ":pk": f"PROFILE_RISK#{profile_id}",
                ":prefix": "TS#",
            },
            ScanIndexForward=False,  # newest first
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            return None
        return await self.find_by_id(items[0]["assessment_id"])

    async def find_history(
        self, profile_id: str, limit: int = 10,
    ) -> list[RiskAssessment]:
        response = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={
                ":pk": f"PROFILE_RISK#{profile_id}",
                ":prefix": "TS#",
            },
            ScanIndexForward=False,
            Limit=limit,
        )
        items = response.get("Items", [])
        assessments = []
        for idx_item in items:
            a = await self.find_by_id(idx_item["assessment_id"])
            if a:
                assessments.append(a)
        return assessments

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def _to_item(self, a: RiskAssessment) -> dict[str, Any]:
        factors_data = [
            {
                "factor_type": f.factor_type.value,
                "score": str(f.score),
                "weight": str(f.weight),
                "description": f.description,
                "data_points": {k: str(v) for k, v in f.data_points.items()},
            }
            for f in a.factors
        ]
        return {
            "PK": f"RISK#{a.assessment_id}",
            "SK": "METADATA",
            "assessment_id": a.assessment_id,
            "profile_id": a.profile_id,
            "risk_score": a.risk_score,
            "risk_category": a.risk_category.value,
            "confidence_level": str(a.confidence_level),
            "factors": json.dumps(factors_data),
            "explanation_summary": a.explanation.summary,
            "explanation_key_factors": json.dumps(a.explanation.key_factors),
            "explanation_recommendations": json.dumps(a.explanation.recommendations),
            "explanation_confidence_note": a.explanation.confidence_note,
            "valid_until": a.valid_until.isoformat(),
            "model_version": a.model_version,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
        }

    def _from_item(self, item: dict[str, Any]) -> RiskAssessment:
        factors_raw = json.loads(item.get("factors", "[]"))
        factors = [
            RiskFactor(
                factor_type=RiskFactorType(f["factor_type"]),
                score=float(f["score"]),
                weight=float(f["weight"]),
                description=f["description"],
                data_points={k: float(v) for k, v in f.get("data_points", {}).items()},
            )
            for f in factors_raw
        ]

        explanation = RiskExplanation(
            summary=item.get("explanation_summary", ""),
            key_factors=json.loads(item.get("explanation_key_factors", "[]")),
            recommendations=json.loads(item.get("explanation_recommendations", "[]")),
            confidence_note=item.get("explanation_confidence_note", ""),
        )

        return RiskAssessment(
            assessment_id=item["assessment_id"],
            profile_id=item["profile_id"],
            risk_score=int(item["risk_score"]),
            risk_category=RiskCategory(item["risk_category"]),
            confidence_level=float(item["confidence_level"]),
            factors=factors,
            explanation=explanation,
            valid_until=datetime.fromisoformat(item["valid_until"]),
            model_version=item.get("model_version", "rules-v1"),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )
