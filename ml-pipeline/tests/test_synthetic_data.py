"""Tests for synthetic data generation module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


class TestSyntheticDataGenerator:
    def test_generate_farmer_profiles(self):
        from data.synthetic.generate_synthetic_data import generate_farmer_profiles

        df = generate_farmer_profiles(n=100, seed=42)
        assert isinstance(df, pd.DataFrame)
        assert len(df) >= 90  # May not be exactly 100 due to segment fractions
        for col in [
            "profile_id", "annual_income", "age", "dependents",
            "land_holding_acres", "has_irrigation",
        ]:
            assert col in df.columns, f"Missing column: {col}"

    def test_generate_cashflow_time_series(self):
        from data.synthetic.generate_synthetic_data import (
            generate_cashflow_time_series,
            generate_farmer_profiles,
        )

        profiles = generate_farmer_profiles(n=10, seed=42)
        records = generate_cashflow_time_series(profiles, months=12)
        assert isinstance(records, pd.DataFrame)
        assert len(records) > 0

    def test_generate_early_warning_events(self):
        from data.synthetic.generate_synthetic_data import (
            generate_cashflow_time_series,
            generate_early_warning_events,
            generate_farmer_profiles,
        )

        profiles = generate_farmer_profiles(n=20, seed=42)
        cashflows = generate_cashflow_time_series(profiles, months=24, seed=42)
        events = generate_early_warning_events(profiles, cashflows, seed=42)
        assert isinstance(events, pd.DataFrame)
        assert len(events) > 0

    def test_risk_labels_present(self):
        from data.synthetic.generate_synthetic_data import generate_farmer_profiles

        df = generate_farmer_profiles(n=50, seed=42)
        assert "risk_score" in df.columns
        assert "risk_category" in df.columns
        assert set(df["risk_category"].unique()).issubset(
            {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}
        )

    def test_reproducibility_with_seed(self):
        from data.synthetic.generate_synthetic_data import generate_farmer_profiles

        df1 = generate_farmer_profiles(n=50, seed=42)
        df2 = generate_farmer_profiles(n=50, seed=42)
        pd.testing.assert_frame_equal(df1, df2)

    def test_profiles_have_realistic_ranges(self):
        from data.synthetic.generate_synthetic_data import generate_farmer_profiles

        df = generate_farmer_profiles(n=500, seed=42)
        assert (df["annual_income"] > 0).all()
        assert (df["age"] >= 18).all()
        assert (df["age"] <= 80).all()
        assert (df["land_holding_acres"] >= 0).all()

    def test_risk_score_range(self):
        from data.synthetic.generate_synthetic_data import generate_farmer_profiles

        df = generate_farmer_profiles(n=500, seed=42)
        assert (df["risk_score"] >= 0).all()
        assert (df["risk_score"] <= 1000).all()
