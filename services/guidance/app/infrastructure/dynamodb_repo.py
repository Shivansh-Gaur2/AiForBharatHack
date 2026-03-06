"""DynamoDB single-table repository for the Guidance Service."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from services.shared.models import ProfileId

from ..domain.models import (
    AlternativeOption,
    AmountRange,
    ConfidenceLevel,
    CreditGuidance,
    GuidanceExplanation,
    GuidanceStatus,
    LoanPurpose,
    ReasoningStep,
    RiskSummary,
    SuggestedTerms,
    TimingSuitability,
    TimingWindow,
)

logger = logging.getLogger(__name__)
UTC = UTC


class DynamoDBGuidanceRepository:
    """Single-table DynamoDB repository.

    Access patterns:
      PK=GUIDANCE#{id}   SK=METADATA         -> guidance record
      PK=PROFILE_GUIDANCE#{profile_id}  SK=TS#{iso}#{id}  -> profile index
    """

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    async def save_guidance(self, guidance: CreditGuidance) -> None:
        item = self._to_item(guidance)
        self._table.put_item(Item=item)

        # Profile index item
        ts = guidance.created_at.isoformat()
        self._table.put_item(Item={
            "PK": f"PROFILE_GUIDANCE#{guidance.profile_id}",
            "SK": f"TS#{ts}#{guidance.guidance_id}",
            "guidance_id": guidance.guidance_id,
            "profile_id": guidance.profile_id,
            "loan_purpose": guidance.loan_purpose,
            "recommended_max": str(guidance.recommended_amount.max_amount),
            "risk_category": guidance.risk_summary.risk_category,
            "status": guidance.status,
            "created_at": ts,
        })

    # ------------------------------------------------------------------
    # Find
    # ------------------------------------------------------------------

    async def find_guidance_by_id(self, guidance_id: str) -> CreditGuidance | None:
        resp = self._table.get_item(Key={
            "PK": f"GUIDANCE#{guidance_id}",
            "SK": "METADATA",
        })
        item = resp.get("Item")
        if not item:
            return None
        return self._from_item(item)

    async def find_guidance_by_profile(
        self,
        profile_id: ProfileId,
        limit: int = 20,
    ) -> list[CreditGuidance]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"PROFILE_GUIDANCE#{profile_id}"},
            ScanIndexForward=False,
            Limit=limit,
        )
        result: list[CreditGuidance] = []
        for index_item in resp.get("Items", []):
            gid = index_item["guidance_id"]
            guidance = await self.find_guidance_by_id(gid)
            if guidance:
                result.append(guidance)
        return result

    async def find_active_guidance(
        self,
        profile_id: ProfileId,
    ) -> list[CreditGuidance]:
        all_guidance = await self.find_guidance_by_profile(profile_id, limit=50)
        return [g for g in all_guidance if g.is_active()]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _to_item(self, g: CreditGuidance) -> dict:
        return {
            "PK": f"GUIDANCE#{g.guidance_id}",
            "SK": "METADATA",
            "guidance_id": g.guidance_id,
            "profile_id": g.profile_id,
            "loan_purpose": g.loan_purpose,
            "requested_amount": str(g.requested_amount) if g.requested_amount is not None else None,
            "recommended_amount": json.dumps({
                "min_amount": g.recommended_amount.min_amount,
                "max_amount": g.recommended_amount.max_amount,
                "currency": g.recommended_amount.currency,
            }),
            "optimal_timing": json.dumps({
                "start_month": g.optimal_timing.start_month,
                "start_year": g.optimal_timing.start_year,
                "end_month": g.optimal_timing.end_month,
                "end_year": g.optimal_timing.end_year,
                "suitability": g.optimal_timing.suitability,
                "reason": g.optimal_timing.reason,
                "expected_surplus": g.optimal_timing.expected_surplus,
            }),
            "suggested_terms": json.dumps({
                "tenure_months": g.suggested_terms.tenure_months,
                "interest_rate_max_pct": g.suggested_terms.interest_rate_max_pct,
                "emi_amount": g.suggested_terms.emi_amount,
                "total_repayment": g.suggested_terms.total_repayment,
                "source_recommendation": g.suggested_terms.source_recommendation,
            }),
            "risk_summary": json.dumps({
                "risk_category": g.risk_summary.risk_category,
                "risk_score": g.risk_summary.risk_score,
                "dti_ratio": g.risk_summary.dti_ratio,
                "repayment_capacity_pct": g.risk_summary.repayment_capacity_pct,
                "key_risk_factors": g.risk_summary.key_risk_factors,
            }),
            "alternative_options": json.dumps([
                {
                    "option_type": o.option_type,
                    "description": o.description,
                    "estimated_amount": o.estimated_amount,
                    "advantages": o.advantages,
                    "disadvantages": o.disadvantages,
                }
                for o in g.alternative_options
            ]),
            "explanation": json.dumps({
                "summary": g.explanation.summary,
                "reasoning_steps": [
                    {
                        "step_number": s.step_number,
                        "factor": s.factor,
                        "observation": s.observation,
                        "impact": s.impact,
                    }
                    for s in g.explanation.reasoning_steps
                ],
                "confidence": g.explanation.confidence,
                "caveats": g.explanation.caveats,
            }),
            "status": g.status,
            "created_at": g.created_at.isoformat(),
            "expires_at": g.expires_at.isoformat() if g.expires_at else None,
        }

    def _from_item(self, item: dict) -> CreditGuidance:
        amt = json.loads(item["recommended_amount"])
        timing = json.loads(item["optimal_timing"])
        terms = json.loads(item["suggested_terms"])
        risk = json.loads(item["risk_summary"])
        alts = json.loads(item["alternative_options"])
        expl = json.loads(item["explanation"])

        return CreditGuidance(
            guidance_id=item["guidance_id"],
            profile_id=item["profile_id"],
            loan_purpose=LoanPurpose(item["loan_purpose"]),
            requested_amount=float(item["requested_amount"]) if item.get("requested_amount") else None,
            recommended_amount=AmountRange(
                min_amount=amt["min_amount"],
                max_amount=amt["max_amount"],
                currency=amt.get("currency", "INR"),
            ),
            optimal_timing=TimingWindow(
                start_month=timing["start_month"],
                start_year=timing["start_year"],
                end_month=timing["end_month"],
                end_year=timing["end_year"],
                suitability=TimingSuitability(timing["suitability"]),
                reason=timing["reason"],
                expected_surplus=timing.get("expected_surplus", 0.0),
            ),
            suggested_terms=SuggestedTerms(
                tenure_months=terms["tenure_months"],
                interest_rate_max_pct=terms["interest_rate_max_pct"],
                emi_amount=terms["emi_amount"],
                total_repayment=terms["total_repayment"],
                source_recommendation=terms["source_recommendation"],
            ),
            risk_summary=RiskSummary(
                risk_category=risk["risk_category"],
                risk_score=risk["risk_score"],
                dti_ratio=risk["dti_ratio"],
                repayment_capacity_pct=risk["repayment_capacity_pct"],
                key_risk_factors=risk["key_risk_factors"],
            ),
            alternative_options=[
                AlternativeOption(
                    option_type=o["option_type"],
                    description=o["description"],
                    estimated_amount=o["estimated_amount"],
                    advantages=o["advantages"],
                    disadvantages=o["disadvantages"],
                )
                for o in alts
            ],
            explanation=GuidanceExplanation(
                summary=expl["summary"],
                reasoning_steps=[
                    ReasoningStep(
                        step_number=s["step_number"],
                        factor=s["factor"],
                        observation=s["observation"],
                        impact=s["impact"],
                    )
                    for s in expl["reasoning_steps"]
                ],
                confidence=ConfidenceLevel(expl["confidence"]),
                caveats=expl["caveats"],
            ),
            status=GuidanceStatus(item["status"]),
            created_at=datetime.fromisoformat(item["created_at"]),
            expires_at=datetime.fromisoformat(item["expires_at"]) if item.get("expires_at") else None,
        )
