"""Fetch daily wholesale prices from Agmarknet / data.gov.in.

Stores as partitioned CSVs in S3 or local filesystem:
  raw/agmarknet/daily/YYYY/MM/prices.csv
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

AGMARKNET_API = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
DEFAULT_API_KEY = ""  # set via env or arg


def fetch_daily_prices(
    api_key: str,
    target_date: date | None = None,
    limit: int = 5000,
) -> pd.DataFrame:
    """Fetch mandi prices for a given date from data.gov.in Agmarknet API.

    Returns DataFrame with columns:
      state, district, market, commodity, variety,
      min_price, max_price, modal_price, arrival_date
    """
    target_date = target_date or date.today() - timedelta(days=1)
    date_str = target_date.strftime("%d/%m/%Y")

    params = {
        "api-key": api_key,
        "format": "json",
        "limit": limit,
        "filters[arrival_date]": date_str,
    }

    try:
        resp = requests.get(AGMARKNET_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.warning("Agmarknet API call failed for %s", date_str, exc_info=True)
        return pd.DataFrame()

    records = data.get("records", [])
    if not records:
        logger.info("No records for %s", date_str)
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    logger.info("Fetched %d price records for %s", len(df), date_str)
    return df


def save_prices(df: pd.DataFrame, output_dir: str, target_date: date) -> Path:
    """Save prices in partitioned directory structure."""
    out = Path(output_dir) / "agmarknet" / "daily" / str(target_date.year) / f"{target_date.month:02d}"
    out.mkdir(parents=True, exist_ok=True)
    fpath = out / f"prices_{target_date.isoformat()}.csv"
    df.to_csv(fpath, index=False)
    logger.info("Saved → %s", fpath)
    return fpath


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Agmarknet prices")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--output", default="ml-pipeline/data/raw")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    target = date.fromisoformat(args.date) if args.date else date.today() - timedelta(days=1)
    df = fetch_daily_prices(args.api_key, target)
    if not df.empty:
        save_prices(df, args.output, target)


if __name__ == "__main__":
    main()
