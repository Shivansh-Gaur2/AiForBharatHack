"""Seed realistic 12-month historical cashflow records for every existing profile.

Run after seed_profiles.py:
    python seed_cashflow.py

Each profile gets monthly INFLOW + OUTFLOW records across multiple categories
following a realistic Rabi-Kharif seasonal pattern, with per-profile variation.
"""

import random
import requests

PROFILE_URL = "http://127.0.0.1:8001/api/v1/profiles"
CASHFLOW_URL = "http://127.0.0.1:8004/api/v1/cashflow/records/batch"

# ── Per-profile seasonal templates ──────────────────────────────────────────
# Each profile has a base monthly income range and expense range, with
# seasonal multipliers that mimic Kharif (Jun-Oct), Rabi (Nov-Mar), Zaid
# (Apr-May) cycles.

PROFILE_TEMPLATES: dict[str, dict] = {
    # Diversified large farmer with livestock
    "FARMER_LARGE": {
        "inflows": {
            "CROP_INCOME":        {"base": (10000, 14000), "kharif": 1.4, "rabi": 1.2, "zaid": 0.3},
            "LIVESTOCK_INCOME":    {"base": (3000, 5000),   "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "GOVERNMENT_SUBSIDY":  {"base": (500, 1500),    "kharif": 1.5, "rabi": 1.0, "zaid": 0.5},
        },
        "outflows": {
            "SEED_FERTILIZER":  {"base": (3000, 5000),  "kharif": 1.5, "rabi": 1.2, "zaid": 0.4},
            "LABOUR_EXPENSE":   {"base": (2000, 3500),  "kharif": 1.3, "rabi": 1.1, "zaid": 0.5},
            "HOUSEHOLD":        {"base": (4000, 6000),  "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "HEALTHCARE":       {"base": (500, 1500),   "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
    },
    # Medium farmer with secondary livestock
    "FARMER_MEDIUM": {
        "inflows": {
            "CROP_INCOME":        {"base": (7000, 10000), "kharif": 1.3, "rabi": 1.1, "zaid": 0.3},
            "LIVESTOCK_INCOME":    {"base": (5000, 8000),  "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "OTHER_INCOME":       {"base": (500, 1000),   "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
        "outflows": {
            "SEED_FERTILIZER":  {"base": (2000, 3500),  "kharif": 1.4, "rabi": 1.2, "zaid": 0.3},
            "LABOUR_EXPENSE":   {"base": (1500, 2500),  "kharif": 1.2, "rabi": 1.1, "zaid": 0.4},
            "HOUSEHOLD":        {"base": (3500, 5000),  "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "EDUCATION":        {"base": (500, 1000),   "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
    },
    # Small farmer with limited income
    "FARMER_SMALL": {
        "inflows": {
            "CROP_INCOME":          {"base": (5000, 8000),  "kharif": 1.5, "rabi": 1.2, "zaid": 0.2},
            "LABOUR_INCOME":        {"base": (2000, 3000),  "kharif": 0.8, "rabi": 1.0, "zaid": 1.5},
            "GOVERNMENT_SUBSIDY":   {"base": (500, 1000),   "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
        "outflows": {
            "SEED_FERTILIZER":  {"base": (1500, 3000),  "kharif": 1.5, "rabi": 1.3, "zaid": 0.3},
            "HOUSEHOLD":        {"base": (3000, 4500),  "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "HEALTHCARE":       {"base": (300, 800),    "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
    },
    # Livestock-primary
    "LIVESTOCK_PRIMARY": {
        "inflows": {
            "LIVESTOCK_INCOME":    {"base": (12000, 18000), "kharif": 1.0, "rabi": 1.1, "zaid": 0.9},
            "CROP_INCOME":         {"base": (3000, 5000),   "kharif": 1.3, "rabi": 1.0, "zaid": 0.2},
            "OTHER_INCOME":        {"base": (1000, 2000),   "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
        "outflows": {
            "SEED_FERTILIZER":  {"base": (1000, 2000),  "kharif": 1.3, "rabi": 1.0, "zaid": 0.5},
            "LABOUR_EXPENSE":   {"base": (2000, 4000),  "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "HOUSEHOLD":        {"base": (4000, 6000),  "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
            "HEALTHCARE":       {"base": (800, 2000),   "kharif": 1.0, "rabi": 1.0, "zaid": 1.0},
        },
    },
}


def _season_for_month(m: int) -> str:
    if m in (6, 7, 8, 9, 10):
        return "kharif"
    elif m in (11, 12, 1, 2, 3):
        return "rabi"
    else:
        return "zaid"


def _season_enum(m: int) -> str:
    return {"kharif": "KHARIF", "rabi": "RABI", "zaid": "ZAID"}[_season_for_month(m)]


def generate_records(profile_id: str, template_key: str) -> list[dict]:
    """Generate 12 months of records (Mar 2025 – Feb 2026) for one profile."""
    tpl = PROFILE_TEMPLATES[template_key]
    records = []

    for offset in range(12):
        # Go from March 2025 to February 2026
        m = ((2 + offset) % 12) + 1  # 3,4,5,...,12,1,2
        y = 2025 if m >= 3 else 2026

        season = _season_for_month(m)

        for cat, cfg in tpl["inflows"].items():
            lo, hi = cfg["base"]
            mult = cfg[season]
            amount = round(random.uniform(lo, hi) * mult, 2)
            records.append({
                "profile_id": profile_id,
                "category": cat,
                "direction": "INFLOW",
                "amount": amount,
                "month": m,
                "year": y,
                "season": _season_enum(m),
                "notes": f"Seeded {cat.lower().replace('_', ' ')}",
            })

        for cat, cfg in tpl["outflows"].items():
            lo, hi = cfg["base"]
            mult = cfg[season]
            amount = round(random.uniform(lo, hi) * mult, 2)
            records.append({
                "profile_id": profile_id,
                "category": cat,
                "direction": "OUTFLOW",
                "amount": amount,
                "month": m,
                "year": y,
                "season": _season_enum(m),
                "notes": f"Seeded {cat.lower().replace('_', ' ')}",
            })

    return records


# ── Name-to-template mapping ───────────────────────────────────────────────
NAME_MAP = {
    "Ramesh Kumar":  "FARMER_LARGE",      # 8 acres owned, wheat+rice, buffalo
    "Sunita Devi":   "FARMER_MEDIUM",     # 4 acres, cotton+mustard, cows
    "Arjun Singh":   "FARMER_LARGE",      # 12 acres, bajra+gram, goats
    "Priya Sharma":  "FARMER_SMALL",      # 3 acres, sugarcane+potato
    "Vikram Patel":  "LIVESTOCK_PRIMARY",  # livestock-primary, groundnut
}


def main():
    # 1. Fetch all profiles
    print("Fetching profiles...")
    r = requests.get(f"{PROFILE_URL}?limit=200")
    r.raise_for_status()
    profiles = r.json()["items"]
    print(f"  Found {len(profiles)} profiles\n")

    for p in profiles:
        name = p["name"]
        pid = p["profile_id"]
        occ = p.get("occupation", "FARMER")

        # Pick template
        template_key = NAME_MAP.get(name)
        if template_key is None:
            # Fallback based on occupation
            if "LIVESTOCK" in occ:
                template_key = "LIVESTOCK_PRIMARY"
            else:
                template_key = "FARMER_MEDIUM"

        records = generate_records(pid, template_key)
        print(f"  {name} ({pid[:8]}…): {len(records)} records using {template_key}")

        # 2. POST batch
        resp = requests.post(CASHFLOW_URL, json={"records": records})
        if resp.status_code == 201:
            saved = resp.json().get("count", len(records))
            print(f"    ✓ Saved {saved} records")
        else:
            print(f"    ✗ Failed ({resp.status_code}): {resp.text[:200]}")

    # 3. Auto-generate forecasts for every profile
    print("\nGenerating forecasts...")
    FORECAST_URL = "http://127.0.0.1:8004/api/v1/cashflow/forecast"
    for p in profiles:
        pid = p["profile_id"]
        name = p["name"]
        resp = requests.post(FORECAST_URL, json={"profile_id": pid, "horizon_months": 12})
        if resp.status_code == 201:
            fid = resp.json().get("forecast_id", "?")
            print(f"  ✓ {name}: forecast {fid[:8]}…")
        else:
            print(f"  ✗ {name}: {resp.status_code} — {resp.text[:150]}")

    print("\nDone! Cash flow records and forecasts seeded for all profiles.")


if __name__ == "__main__":
    main()
