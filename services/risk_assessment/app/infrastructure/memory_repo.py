"""In-memory repository implementation for the Risk Assessment service.

Default storage backend for local development and testing — no AWS needed.
"""

from __future__ import annotations

from services.risk_assessment.app.domain.models import RiskAssessment
from services.shared.models import ProfileId


class InMemoryRiskRepository:
    """Thread-unsafe in-memory store; suitable for single-process local dev."""

    def __init__(self) -> None:
        # assessment_id → RiskAssessment
        self._assessments: dict[str, RiskAssessment] = {}
        # profile_id → list of assessment_ids (insertion order = time order)
        self._by_profile: dict[ProfileId, list[str]] = {}

    # ------------------------------------------------------------------
    # RiskAssessmentRepository protocol (all async)
    # ------------------------------------------------------------------

    async def save(self, assessment: RiskAssessment) -> None:
        self._assessments[assessment.assessment_id] = assessment
        bucket = self._by_profile.setdefault(assessment.profile_id, [])
        if assessment.assessment_id not in bucket:
            bucket.append(assessment.assessment_id)

    async def find_latest(self, profile_id: ProfileId) -> RiskAssessment | None:
        ids = self._by_profile.get(profile_id, [])
        if not ids:
            return None
        return self._assessments.get(ids[-1])

    async def find_by_id(self, assessment_id: str) -> RiskAssessment | None:
        return self._assessments.get(assessment_id)

    async def find_history(
        self,
        profile_id: ProfileId,
        limit: int = 10,
    ) -> list[RiskAssessment]:
        ids = self._by_profile.get(profile_id, [])
        recent = ids[-limit:][::-1]  # most recent first
        return [self._assessments[aid] for aid in recent if aid in self._assessments]

    async def delete_by_profile(self, profile_id: ProfileId) -> int:
        ids = self._by_profile.pop(profile_id, [])
        for aid in ids:
            self._assessments.pop(aid, None)
        return len(ids)
