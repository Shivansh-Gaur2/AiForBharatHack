"""Unit tests for Guidance Service domain service (async orchestration)."""

from __future__ import annotations

import pytest

from services.guidance.app.domain.models import (
    CreditGuidance,
    GuidanceStatus,
    LoanPurpose,
)
from services.guidance.app.domain.services import GuidanceService
from services.shared.events import AsyncInMemoryEventPublisher
from services.shared.models import AmountRange

# ---------------------------------------------------------------------------
# In-memory test doubles
# ---------------------------------------------------------------------------


class InMemoryGuidanceRepository:
    def __init__(self):
        self._store: dict[str, CreditGuidance] = {}

    async def save_guidance(self, guidance: CreditGuidance) -> None:
        self._store[guidance.guidance_id] = guidance

    async def find_guidance_by_id(self, guidance_id: str) -> CreditGuidance | None:
        return self._store.get(guidance_id)

    async def find_guidance_by_profile(
        self, profile_id: str, limit: int = 20,
    ) -> list[CreditGuidance]:
        items = [g for g in self._store.values() if g.profile_id == profile_id]
        items.sort(key=lambda g: g.created_at, reverse=True)
        return items[:limit]

    async def find_active_guidance(self, profile_id: str) -> list[CreditGuidance]:
        return [
            g for g in self._store.values()
            if g.profile_id == profile_id and g.is_active()
        ]


class FakeRiskDataProvider:
    def __init__(self, category: str = "MEDIUM", score: float = 450.0):
        self._cat = category
        self._score = score

    async def get_risk_category(self, profile_id: str) -> str:
        return self._cat

    async def get_risk_score(self, profile_id: str) -> float:
        return self._score


class FakeCashFlowDataProvider:
    def __init__(self, projections=None):
        self._projections = projections or [
            (m, 2026, 15000, 8000) for m in range(1, 13)
        ]

    async def get_forecast_projections(self, profile_id: str):
        return self._projections

    async def get_repayment_capacity(self, profile_id: str) -> dict:
        return {"recommended_emi": 3500, "max_emi": 5000}


class FakeLoanDataProvider:
    def __init__(self, exposure=None):
        self._exposure = exposure or {
            "total_outstanding": 50000,
            "monthly_obligations": 4000,
            "dti_ratio": 0.3,
        }

    async def get_debt_exposure(self, profile_id: str) -> dict:
        return self._exposure


class FakeProfileDataProvider:
    async def get_profile_summary(self, profile_id: str) -> dict:
        return {"occupation": "FARMER"}

    async def get_household_expense(self, profile_id: str) -> float:
        return 8000.0


class FakeAlertDataProvider:
    async def get_active_alerts(self, profile_id: str) -> list[dict]:
        return []


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def service():
    return GuidanceService(
        repo=InMemoryGuidanceRepository(),
        risk_provider=FakeRiskDataProvider(),
        cashflow_provider=FakeCashFlowDataProvider(),
        loan_provider=FakeLoanDataProvider(),
        profile_provider=FakeProfileDataProvider(),
        alert_provider=FakeAlertDataProvider(),
        events=AsyncInMemoryEventPublisher(),
    )


# ---------------------------------------------------------------------------
# Tests: Generate Guidance (cross-service)
# ---------------------------------------------------------------------------
class TestGenerateGuidance:
    @pytest.mark.asyncio()
    async def test_generate_guidance(self, service: GuidanceService):
        guidance = await service.generate_guidance(
            profile_id="test-prof",
            loan_purpose="CROP_CULTIVATION",
            requested_amount=50000,
        )
        assert guidance.profile_id == "test-prof"
        assert guidance.loan_purpose == LoanPurpose.CROP_CULTIVATION
        assert guidance.recommended_amount.max_amount > 0
        assert guidance.status == GuidanceStatus.ACTIVE
        assert len(guidance.explanation.reasoning_steps) == 5

    @pytest.mark.asyncio()
    async def test_generates_timing(self, service: GuidanceService):
        guidance = await service.generate_guidance(
            profile_id="test-prof",
            loan_purpose="LIVESTOCK_PURCHASE",
        )
        assert guidance.optimal_timing.start_month >= 1
        assert guidance.optimal_timing.suitability

    @pytest.mark.asyncio()
    async def test_persisted(self, service: GuidanceService):
        guidance = await service.generate_guidance(
            profile_id="test-prof",
            loan_purpose="CROP_CULTIVATION",
        )
        fetched = await service.get_guidance(guidance.guidance_id)
        assert fetched is not None
        assert fetched.guidance_id == guidance.guidance_id

    @pytest.mark.asyncio()
    async def test_publishes_event(self, service: GuidanceService):
        await service.generate_guidance("prof-1", "CROP_CULTIVATION")
        assert len(service._events.events) == 1
        assert service._events.events[0].event_type == "guidance.generated"


# ---------------------------------------------------------------------------
# Tests: Generate Guidance Direct
# ---------------------------------------------------------------------------
class TestGenerateGuidanceDirect:
    @pytest.mark.asyncio()
    async def test_direct_guidance(self, service: GuidanceService):
        projections = [(m, 2026, 15000, 8000) for m in range(1, 13)]
        guidance = await service.generate_guidance_direct(
            profile_id="direct-prof",
            loan_purpose="WORKING_CAPITAL",
            projections=projections,
            risk_category="LOW",
            risk_score=200,
            dti_ratio=0.15,
            existing_obligations=2000,
            requested_amount=80000,
        )
        assert guidance.profile_id == "direct-prof"
        assert guidance.risk_summary.risk_category == "LOW"

    @pytest.mark.asyncio()
    async def test_direct_validation_error(self, service: GuidanceService):
        with pytest.raises(ValueError, match=r"projections must not be empty"):
            await service.generate_guidance_direct(
                profile_id="prof-1",
                loan_purpose="CROP_CULTIVATION",
                projections=[],
                risk_category="MEDIUM",
                risk_score=450,
                dti_ratio=0.3,
                existing_obligations=0,
            )


# ---------------------------------------------------------------------------
# Tests: Timing Only
# ---------------------------------------------------------------------------
class TestGetOptimalTiming:
    @pytest.mark.asyncio()
    async def test_timing(self, service: GuidanceService):
        timing = await service.get_optimal_timing("prof-1", 50000, 12)
        assert timing.start_month >= 1
        assert timing.reason

    @pytest.mark.asyncio()
    async def test_timing_validation_error(self, service: GuidanceService):
        with pytest.raises(ValueError, match=r"positive"):
            await service.get_optimal_timing("prof-1", 0)


# ---------------------------------------------------------------------------
# Tests: Amount Only
# ---------------------------------------------------------------------------
class TestGetRecommendedAmount:
    @pytest.mark.asyncio()
    async def test_amount(self, service: GuidanceService):
        amount = await service.get_recommended_amount("prof-1", 12, 9.0)
        assert isinstance(amount, AmountRange)
        assert amount.max_amount >= 0

    @pytest.mark.asyncio()
    async def test_amount_validation_error(self, service: GuidanceService):
        with pytest.raises(ValueError, match=r"profile_id"):
            await service.get_recommended_amount("")


# ---------------------------------------------------------------------------
# Tests: Lifecycle
# ---------------------------------------------------------------------------
class TestGuidanceLifecycle:
    @pytest.mark.asyncio()
    async def test_supersede(self, service: GuidanceService):
        guidance = await service.generate_guidance("prof-1", "CROP_CULTIVATION")
        updated = await service.supersede_guidance(guidance.guidance_id)
        assert updated.status == GuidanceStatus.SUPERSEDED

    @pytest.mark.asyncio()
    async def test_expire(self, service: GuidanceService):
        guidance = await service.generate_guidance("prof-1", "CROP_CULTIVATION")
        updated = await service.expire_guidance(guidance.guidance_id)
        assert updated.status == GuidanceStatus.EXPIRED

    @pytest.mark.asyncio()
    async def test_supersede_not_found(self, service: GuidanceService):
        with pytest.raises(ValueError, match=r"not found"):
            await service.supersede_guidance("nonexistent-id")

    @pytest.mark.asyncio()
    async def test_expire_not_found(self, service: GuidanceService):
        with pytest.raises(ValueError, match=r"not found"):
            await service.expire_guidance("nonexistent-id")


# ---------------------------------------------------------------------------
# Tests: Queries
# ---------------------------------------------------------------------------
class TestGuidanceQueries:
    @pytest.mark.asyncio()
    async def test_get_history(self, service: GuidanceService):
        for _ in range(3):
            await service.generate_guidance("history-prof", "CROP_CULTIVATION")
        history = await service.get_guidance_history("history-prof")
        assert len(history) == 3

    @pytest.mark.asyncio()
    async def test_get_active(self, service: GuidanceService):
        g1 = await service.generate_guidance("active-prof", "CROP_CULTIVATION")
        await service.generate_guidance("active-prof", "LIVESTOCK_PURCHASE")
        await service.expire_guidance(g1.guidance_id)
        active = await service.get_active_guidance("active-prof")
        assert len(active) == 1
        assert active[0].loan_purpose == LoanPurpose.LIVESTOCK_PURCHASE

    @pytest.mark.asyncio()
    async def test_get_nonexistent(self, service: GuidanceService):
        result = await service.get_guidance("no-such-id")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Different risk levels affect guidance
# ---------------------------------------------------------------------------
class TestRiskInfluence:
    @pytest.mark.asyncio()
    async def test_low_risk_higher_amount(self):
        low_svc = GuidanceService(
            repo=InMemoryGuidanceRepository(),
            risk_provider=FakeRiskDataProvider("LOW", 200),
            cashflow_provider=FakeCashFlowDataProvider(),
            loan_provider=FakeLoanDataProvider(),
            profile_provider=FakeProfileDataProvider(),
            alert_provider=FakeAlertDataProvider(),
            events=AsyncInMemoryEventPublisher(),
        )
        high_svc = GuidanceService(
            repo=InMemoryGuidanceRepository(),
            risk_provider=FakeRiskDataProvider("HIGH", 700),
            cashflow_provider=FakeCashFlowDataProvider(),
            loan_provider=FakeLoanDataProvider(),
            profile_provider=FakeProfileDataProvider(),
            alert_provider=FakeAlertDataProvider(),
            events=AsyncInMemoryEventPublisher(),
        )

        low_g = await low_svc.generate_guidance("p1", "CROP_CULTIVATION")
        high_g = await high_svc.generate_guidance("p1", "CROP_CULTIVATION")

        assert low_g.recommended_amount.max_amount > high_g.recommended_amount.max_amount
