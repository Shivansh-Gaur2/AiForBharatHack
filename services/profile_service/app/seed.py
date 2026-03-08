"""Auto-seed demonstration profiles on service startup.

Called from the lifespan handler in main.py when AUTO_SEED=true.
Uses the domain service directly — no HTTP dependency.
Idempotent: only seeds when the profile table is empty.
"""

from __future__ import annotations

import logging

from .domain.models import (
    CropInfo,
    LandDetails,
    LivelihoodInfo,
    LivestockInfo,
    PersonalInfo,
    SeasonalFactor,
)
from .domain.services import ProfileService
from services.shared.models import OccupationType, Season

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed data — mirrors seed_profiles.py but as native domain objects
# ---------------------------------------------------------------------------

_PROFILES: list[dict] = [
    {
        "personal_info": PersonalInfo(
            name="Ramesh Kumar",
            age=45,
            gender="male",
            location="Karnal",
            district="Karnal",
            state="Haryana",
            phone="9876543210",
            dependents=4,
        ),
        "livelihood_info": LivelihoodInfo(
            primary_occupation=OccupationType.FARMER,
            secondary_occupations=[],
            land_holding=LandDetails(
                total_acres=10.0,
                irrigated_acres=8.0,
                rain_fed_acres=2.0,
                ownership_type="OWNED",
            ),
            crop_patterns=[
                CropInfo("Wheat", Season.RABI, 5.0, 25, 2200),
                CropInfo("Rice", Season.KHARIF, 5.0, 30, 2000),
            ],
            livestock=[
                LivestockInfo("Buffalo", 3, monthly_income=4000, monthly_expense=2000)
            ],
            migration_patterns=[],
        ),
        "seasonal_factors": [
            SeasonalFactor(Season.KHARIF, 1.3, 1.4, notes="Monsoon cultivation"),
            SeasonalFactor(Season.RABI, 1.1, 1.0, notes="Winter cultivation"),
            SeasonalFactor(Season.ZAID, 0.6, 0.6, notes="Summer off-season"),
        ],
    },
    {
        "personal_info": PersonalInfo(
            name="Sunita Devi",
            age=38,
            gender="female",
            location="Amritsar",
            district="Amritsar",
            state="Punjab",
            phone="9123456780",
            dependents=3,
        ),
        "livelihood_info": LivelihoodInfo(
            primary_occupation=OccupationType.FARMER,
            secondary_occupations=[OccupationType.LIVESTOCK_REARER],
            land_holding=LandDetails(
                total_acres=5.0,
                irrigated_acres=3.0,
                rain_fed_acres=2.0,
                ownership_type="LEASED",
            ),
            crop_patterns=[
                CropInfo("Cotton", Season.KHARIF, 3.0, 10, 6500),
                CropInfo("Mustard", Season.RABI, 2.0, 8, 5400),
            ],
            livestock=[
                LivestockInfo("Cow", 5, monthly_income=8000, monthly_expense=3500)
            ],
            migration_patterns=[],
        ),
        "seasonal_factors": [
            SeasonalFactor(Season.KHARIF, 1.4, 1.3, notes="Monsoon cultivation"),
            SeasonalFactor(Season.RABI, 1.0, 0.9, notes="Winter cultivation"),
            SeasonalFactor(Season.ZAID, 0.5, 0.5, notes="Summer off-season"),
        ],
    },
    {
        "personal_info": PersonalInfo(
            name="Arjun Singh",
            age=52,
            gender="male",
            location="Jaipur",
            district="Jaipur",
            state="Rajasthan",
            phone="9988776655",
            dependents=5,
        ),
        "livelihood_info": LivelihoodInfo(
            primary_occupation=OccupationType.FARMER,
            secondary_occupations=[OccupationType.ARTISAN],
            land_holding=LandDetails(
                total_acres=15.0,
                irrigated_acres=6.0,
                rain_fed_acres=9.0,
                ownership_type="OWNED",
            ),
            crop_patterns=[
                CropInfo("Bajra", Season.KHARIF, 8.0, 15, 2350),
                CropInfo("Gram", Season.RABI, 7.0, 12, 5200),
            ],
            livestock=[
                LivestockInfo("Goat", 10, monthly_income=3000, monthly_expense=1500)
            ],
            migration_patterns=[],
        ),
        "seasonal_factors": [
            SeasonalFactor(Season.KHARIF, 1.2, 1.3, notes="Monsoon cultivation"),
            SeasonalFactor(Season.RABI, 1.1, 1.0, notes="Winter cultivation"),
            SeasonalFactor(Season.ZAID, 0.4, 0.5, notes="Summer off-season"),
        ],
    },
    {
        "personal_info": PersonalInfo(
            name="Priya Sharma",
            age=29,
            gender="female",
            location="Lucknow",
            district="Lucknow",
            state="Uttar Pradesh",
            phone="9112233445",
            dependents=1,
        ),
        "livelihood_info": LivelihoodInfo(
            primary_occupation=OccupationType.FARMER,
            secondary_occupations=[],
            land_holding=LandDetails(
                total_acres=3.0,
                irrigated_acres=2.7,
                rain_fed_acres=0.3,
                ownership_type="OWNED",
            ),
            crop_patterns=[
                CropInfo("Sugarcane", Season.KHARIF, 2.0, 60, 350),
                CropInfo("Potato", Season.RABI, 1.0, 20, 1200),
            ],
            livestock=[],
            migration_patterns=[],
        ),
        "seasonal_factors": [
            SeasonalFactor(Season.KHARIF, 1.5, 1.4, notes="Monsoon cultivation"),
            SeasonalFactor(Season.RABI, 1.2, 1.1, notes="Winter cultivation"),
            SeasonalFactor(Season.ZAID, 0.7, 0.6, notes="Summer off-season"),
        ],
    },
    {
        "personal_info": PersonalInfo(
            name="Vikram Patel",
            age=41,
            gender="male",
            location="Anand",
            district="Anand",
            state="Gujarat",
            phone="9334455667",
            dependents=3,
        ),
        "livelihood_info": LivelihoodInfo(
            primary_occupation=OccupationType.LIVESTOCK_REARER,
            secondary_occupations=[OccupationType.FARMER],
            land_holding=LandDetails(
                total_acres=3.0,
                irrigated_acres=3.0,
                rain_fed_acres=0.0,
                ownership_type="LEASED",
            ),
            crop_patterns=[
                CropInfo("Groundnut", Season.KHARIF, 2.0, 10, 5800),
            ],
            livestock=[
                LivestockInfo("Buffalo", 8, monthly_income=15000, monthly_expense=6000),
                LivestockInfo("Cow", 4, monthly_income=8000, monthly_expense=3000),
            ],
            migration_patterns=[],
        ),
        "seasonal_factors": [
            SeasonalFactor(Season.KHARIF, 1.1, 1.2, notes="Monsoon season"),
            SeasonalFactor(Season.RABI, 1.0, 1.0, notes="Winter season"),
            SeasonalFactor(Season.ZAID, 0.8, 0.8, notes="Summer season"),
        ],
    },
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------

def seed_if_empty(profile_service: ProfileService) -> None:
    """Seed demo profiles if the store is empty. Safe to call on every startup."""
    try:
        existing, _ = profile_service.list_profiles(limit=1)
        if existing:
            logger.info("Seed check: %d profile(s) already exist — skipping seed", len(existing))
            return

        logger.info("Seed check: table empty — seeding %d demo profiles", len(_PROFILES))
        for entry in _PROFILES:
            try:
                profile = profile_service.create_profile(
                    personal_info=entry["personal_info"],
                    livelihood_info=entry["livelihood_info"],
                    seasonal_factors=entry["seasonal_factors"],
                )
                logger.info("Seeded profile: %s (%s)", entry["personal_info"].name, profile.profile_id)
            except Exception as exc:
                logger.warning("Failed to seed profile %s: %s", entry["personal_info"].name, exc)

        logger.info("Seeding complete.")
    except Exception as exc:
        # Never crash startup due to seeding failure
        logger.warning("Seed skipped (store not ready or error): %s", exc)
