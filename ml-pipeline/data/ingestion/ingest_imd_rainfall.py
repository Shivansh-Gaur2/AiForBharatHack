"""Fetch IMD district-level rainfall and drought data.

Stores as partitioned CSVs:
  raw/imd/monthly/YYYY/MM/district_rainfall.csv
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# NASA POWER API is free and doesn't require auth — good proxy for IMD
NASA_POWER_API = "https://power.larc.nasa.gov/api/temporal/monthly/point"

# Representative coordinates for key agricultural districts (lat, lon)
DISTRICT_COORDS: dict[str, tuple[float, float]] = {
    "anantapur": (14.68, 77.60),
    "bellary": (15.14, 76.93),
    "dharwad": (15.46, 75.01),
    "jaipur": (26.92, 75.79),
    "jodhpur": (26.24, 73.02),
    "wardha": (20.73, 78.60),
    "varanasi": (25.32, 83.01),
    "lucknow": (26.85, 80.95),
    "nagpur": (21.14, 79.09),
    "mysore": (12.30, 76.64),
}


def fetch_nasa_power_rainfall(
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Fetch monthly precipitation from NASA POWER API."""
    import requests

    params = {
        "parameters": "PRECTOTCORR",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": f"{start_year}0101",
        "end": f"{end_year}1231",
        "format": "JSON",
    }

    try:
        resp = requests.get(NASA_POWER_API, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.warning("NASA POWER API failed for (%.2f, %.2f)", lat, lon, exc_info=True)
        return pd.DataFrame()

    prcp_data = data.get("properties", {}).get("parameter", {}).get("PRECTOTCORR", {})
    if not prcp_data:
        return pd.DataFrame()

    records = []
    for key, value in prcp_data.items():
        if len(key) == 6 and value != -999:
            records.append({
                "year": int(key[:4]),
                "month": int(key[4:6]),
                "precipitation_mm": float(value),
                "latitude": lat,
                "longitude": lon,
            })

    return pd.DataFrame(records)


def generate_synthetic_rainfall(
    districts: dict[str, tuple[float, float]],
    start_year: int = 2019,
    end_year: int = 2024,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic rainfall data calibrated to regional patterns.

    Used when NASA POWER API is unavailable.
    """
    rng = np.random.default_rng(seed)
    rows = []

    # Southwest monsoon distribution (Jun-Sep gets ~80% of annual rainfall)
    _MONTH_FRACTION = {
        1: 0.02, 2: 0.02, 3: 0.02, 4: 0.03, 5: 0.04,
        6: 0.15, 7: 0.25, 8: 0.22, 9: 0.13,
        10: 0.06, 11: 0.04, 12: 0.02,
    }

    for district, (lat, lon) in districts.items():
        annual_mean = rng.uniform(500, 1200)  # mm
        for year in range(start_year, end_year + 1):
            annual_actual = annual_mean * rng.uniform(0.6, 1.4)  # year-to-year variability
            for month in range(1, 13):
                base = annual_actual * _MONTH_FRACTION[month]
                noise = rng.normal(1.0, 0.3)
                precip = max(0, base * noise)
                rows.append({
                    "district": district,
                    "year": year,
                    "month": month,
                    "precipitation_mm": round(precip, 1),
                    "latitude": lat,
                    "longitude": lon,
                })

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest IMD/NASA rainfall data")
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--output", default="ml-pipeline/data/raw")
    parser.add_argument("--synthetic", action="store_true", help="Use synthetic data")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    output = Path(args.output) / "imd"
    output.mkdir(parents=True, exist_ok=True)

    if args.synthetic:
        df = generate_synthetic_rainfall(DISTRICT_COORDS, args.start_year, args.end_year)
    else:
        frames = []
        for district, (lat, lon) in DISTRICT_COORDS.items():
            result = fetch_nasa_power_rainfall(lat, lon, args.start_year, args.end_year)
            if not result.empty:
                result["district"] = district
                frames.append(result)
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    if not df.empty:
        fpath = output / "district_rainfall.parquet"
        df.to_parquet(fpath, index=False)
        logger.info("Saved %d rainfall records → %s", len(df), fpath)


if __name__ == "__main__":
    main()
