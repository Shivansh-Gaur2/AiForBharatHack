"""Unit tests for external data adapters (circuit breaker, weather, market)."""

from __future__ import annotations

import time

import pytest

from services.cashflow_service.app.infrastructure.data_providers import (
    StubLoanDataProvider,
    StubMarketDataProvider,
    StubProfileDataProvider,
    StubWeatherDataProvider,
)
from services.cashflow_service.app.infrastructure.external_data import (
    CircuitBreaker,
    CircuitState,
    HttpMarketDataProvider,
    HttpWeatherDataProvider,
)


# ---------------------------------------------------------------------------
# Tests: Circuit Breaker
# ---------------------------------------------------------------------------
class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_call_permitted()

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.is_call_permitted()

    def test_success_resets_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(
            name="test", failure_threshold=1, recovery_timeout_seconds=0.1,
        )
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.is_call_permitted()

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(
            name="test", failure_threshold=1, recovery_timeout_seconds=0.1,
        )
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# Tests: Stub Providers
# ---------------------------------------------------------------------------
class TestStubProviders:
    @pytest.mark.asyncio
    async def test_weather_default(self):
        provider = StubWeatherDataProvider()
        adj = await provider.get_weather_adjustment("test", "KHARIF")
        assert adj == 1.0

    @pytest.mark.asyncio
    async def test_weather_custom(self):
        provider = StubWeatherDataProvider()
        provider.set_adjustment("varanasi", "KHARIF", 0.8)
        adj = await provider.get_weather_adjustment("varanasi", "KHARIF")
        assert adj == 0.8

    @pytest.mark.asyncio
    async def test_market_default(self):
        provider = StubMarketDataProvider()
        adj = await provider.get_market_adjustment("rice", "varanasi")
        assert adj == 1.0

    @pytest.mark.asyncio
    async def test_market_custom(self):
        provider = StubMarketDataProvider()
        provider.set_adjustment("rice", "varanasi", 1.2)
        adj = await provider.get_market_adjustment("rice", "varanasi")
        assert adj == 1.2

    @pytest.mark.asyncio
    async def test_profile_default(self):
        provider = StubProfileDataProvider()
        data = await provider.get_profile_summary("test")
        assert data["district"] == "unknown"
        assert data["primary_crop"] == "rice"

    @pytest.mark.asyncio
    async def test_profile_custom(self):
        provider = StubProfileDataProvider()
        provider.set_profile_data("farmer-001", {
            "district": "varanasi",
            "primary_crop": "wheat",
        })
        data = await provider.get_profile_summary("farmer-001")
        assert data["district"] == "varanasi"

    @pytest.mark.asyncio
    async def test_loan_default(self):
        provider = StubLoanDataProvider()
        amt = await provider.get_monthly_obligations("test")
        assert amt == 0.0

    @pytest.mark.asyncio
    async def test_loan_custom(self):
        provider = StubLoanDataProvider()
        provider.set_monthly_obligations("farmer-001", 5000)
        amt = await provider.get_monthly_obligations("farmer-001")
        assert amt == 5000.0


# ---------------------------------------------------------------------------
# Tests: HTTP providers (no API key → fallback)
# ---------------------------------------------------------------------------
class TestHttpProviderFallbacks:
    @pytest.mark.asyncio
    async def test_weather_no_api_key_returns_neutral(self):
        provider = HttpWeatherDataProvider(api_key=None)
        adj = await provider.get_weather_adjustment("test", "KHARIF")
        assert adj == 1.0

    @pytest.mark.asyncio
    async def test_market_no_url_returns_neutral(self):
        provider = HttpMarketDataProvider(base_url=None)
        adj = await provider.get_market_adjustment("rice", "test")
        assert adj == 1.0
