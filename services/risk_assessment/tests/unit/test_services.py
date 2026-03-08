"""Unit tests for RiskAssessmentService."""

import pytest

from services.risk_assessment.app.domain.models import RiskInput
from services.risk_assessment.app.domain.services import RiskAssessmentService
from services.risk_assessment.app.infrastructure.data_providers import (
    StubLoanDataProvider,
    StubProfileDataProvider,
)
from services.shared.events import AsyncInMemoryEventPublisher
from services.shared.models import RiskCategory


# ---------------------------------------------------------------------------
# In-memory repository test double
# ---------------------------------------------------------------------------
class InMemoryRiskRepository:
    def __init__(self):
        self._store = {}
        self._by_profile = {}  # profile_id → list of assessments (newest first)

    async def save(self, assessment):
        self._store[assessment.assessment_id] = assessment
        self._by_profile.setdefault(assessment.profile_id, []).insert(0, assessment)

    async def find_by_id(self, assessment_id):
        return self._store.get(assessment_id)

    async def find_latest(self, profile_id):
        history = self._by_profile.get(profile_id, [])
        return history[0] if history else None

    async def find_history(self, profile_id, limit=10):
        return self._by_profile.get(profile_id, [])[:limit]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def repo():
    return InMemoryRiskRepository()


@pytest.fixture
def profile_provider():
    provider = StubProfileDataProvider()
    provider.set_profile_data("p1",
        volatility={
            "coefficient_of_variation": 0.3,
            "annual_income": 120000,
            "months_below_average": 4,
            "seasonal_variance": 200,
        },
        personal={
            "age": 40,
            "dependents": 3,
            "has_irrigation": False,
            "crop_diversification_index": 0.4,
        },
    )
    return provider


@pytest.fixture
def loan_provider():
    provider = StubLoanDataProvider()
    provider.set_loan_data("p1",
        exposure={
            "debt_to_income_ratio": 0.35,
            "total_outstanding": 50000,
            "active_loan_count": 2,
            "credit_utilisation": 0.5,
        },
        repayment={
            "on_time_ratio": 0.8,
            "has_defaults": False,
        },
    )
    return provider


@pytest.fixture
def events():
    return AsyncInMemoryEventPublisher()


@pytest.fixture
def service(repo, profile_provider, loan_provider, events):
    return RiskAssessmentService(
        repo=repo,
        profile_provider=profile_provider,
        loan_provider=loan_provider,
        events=events,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestAssessRisk:
    @pytest.mark.asyncio
    async def test_assess_risk_produces_valid_assessment(self, service, events):
        assessment = await service.assess_risk("p1")
        assert assessment.profile_id == "p1"
        assert 0 <= assessment.risk_score <= 1000
        assert assessment.risk_category in list(RiskCategory)
        assert len(assessment.factors) == 8

        # Event published
        assert any(e.event_type == "risk.assessed" for e in events.events)

    @pytest.mark.asyncio
    async def test_assessment_persisted(self, service, repo):
        assessment = await service.assess_risk("p1")
        stored = await repo.find_by_id(assessment.assessment_id)
        assert stored is not None
        assert stored.risk_score == assessment.risk_score


class TestDirectScoring:
    @pytest.mark.asyncio
    async def test_score_with_direct_input(self, service):
        risk_input = RiskInput(
            profile_id="p2",
            income_volatility_cv=0.1,
            annual_income=200000,
            months_below_average=1,
            debt_to_income_ratio=0.1,
            total_outstanding=10000,
            active_loan_count=1,
            credit_utilisation=0.1,
            on_time_repayment_ratio=1.0,
            has_defaults=False,
        )
        assessment = await service.assess_risk_with_input(risk_input)
        # ML model output varies by version; a low-risk input should be LOW or MEDIUM
        assert assessment.risk_category in (RiskCategory.LOW, RiskCategory.MEDIUM)


class TestQueries:
    @pytest.mark.asyncio
    async def test_latest_assessment(self, service):
        await service.assess_risk("p1")
        latest = await service.get_latest_assessment("p1")
        assert latest is not None
        assert latest.profile_id == "p1"

    @pytest.mark.asyncio
    async def test_assessment_history(self, service):
        await service.assess_risk("p1")
        await service.assess_risk("p1")
        history = await service.get_assessment_history("p1")
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_no_assessment_returns_none(self, service):
        result = await service.get_latest_assessment("nonexistent")
        assert result is None


class TestExplain:
    @pytest.mark.asyncio
    async def test_explain_risk(self, service):
        assessment = await service.assess_risk("p1")
        explanation = await service.explain_risk(assessment.assessment_id)
        assert explanation is not None
        assert "risk_score" in explanation
        assert "recommendations" in explanation
        assert len(explanation["top_factors"]) <= 3

    @pytest.mark.asyncio
    async def test_explain_nonexistent_returns_none(self, service):
        result = await service.explain_risk("nonexistent")
        assert result is None
