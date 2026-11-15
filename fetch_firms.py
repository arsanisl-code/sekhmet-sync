"""
fetch_firms.py — Sekhmet Sync data acquisition

Downloads MODIS_SP, VIIRS_NOAA20_SP, and VIIRS_NOAA21_SP active-fire detections
for California (bbox: -124.5, 32.5, -114.0, 42.0) for 2020-01-01 to 2024-12-31.
Applies per-sensor confidence filtering and logs results.

Reads FIRMS_MAP_KEY from the environment (or .env file).
If the key is absent or any request fails, prints a manual download checklist and exits.

Usage:
    python fetch_firms.py
"""

import os
import sys
import time
import logging
from datetime import date, timedelta
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BBOX = "-124.5,32.5,-114.0,42.0"  # west,south,east,north
DATE_START = date(2020, 1, 1)
DATE_END = date(2024, 12, 31)
CHUNK_DAYS = 5  # API limit is 10; use 5 for safety (see DECISIONS D08)
DATA_RAW = Path("data/raw")
BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# Products and their available date ranges (confirmed via data_availability API)
# VIIRS_NOAA21_SP starts 2023-03-01 (see DECISIONS D09)
PRODUCTS = {
    "MODIS_SP":          (date(2020, 1, 1), date(2024, 12, 31)),
    "VIIRS_NOAA20_SP":   (date(2020, 1, 1), date(2024, 12, 31)),
    "VIIRS_NOAA21_SP":   (date(2023, 3, 1), date(2024, 12, 31)),
}

# Confidence filters (see DECISIONS D04, D05)
# MODIS: numeric; drop if confidence < 30
# VIIRS: categorical; drop if confidence == 'l'
CONFIDENCE_FILTERS = {
    "MODIS_SP":         lambda df: df["confidence"].astype(float) >= 30,
    "VIIRS_NOAA20_SP":  lambda df: df["confidence"].astype(str).str.lower() != "l",
    "VIIRS_NOAA21_SP":  lambda df: df["confidence"].astype(str).str.lower() != "l",
}

# Bounding box for post-download spatial filter
LAT_MIN, LAT_MAX = 32.5, 42.0
LON_MIN, LON_MAX = -124.5, -114.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fetch_firms")


# ---------------------------------------------------------------------------
# Manual download checklist (printed when key is absent or fetch fails)
# ---------------------------------------------------------------------------

MANUAL_CHECKLIST = """
=== MANUAL DOWNLOAD CHECKLIST (Gate 1 fallback) ===

The FIRMS_MAP_KEY environment variable is not set or the API request failed.

To obtain a key: https://firms.modaps.eosdis.nasa.gov/api/

Alternatively, download the archive CSVs manually from:
  https://firms.modaps.eosdis.nasa.gov/country/

For each product, select:
  - Country: United States
  - Or use the Area API with bbox -124.5,32.5,-114.0,42.0 by year

Place files in data/raw/ with EXACTLY these names:
  MODIS_SP_2020.csv
  MODIS_SP_2021.csv
  MODIS_SP_2022.csv
  MODIS_SP_2023.csv
  MODIS_SP_2024.csv
  VIIRS_NOAA20_SP_2020.csv
  VIIRS_NOAA20_SP_2021.csv
  VIIRS_NOAA20_SP_2022.csv
  VIIRS_NOAA20_SP_2023.csv
  VIIRS_NOAA20_SP_2024.csv
  VIIRS_NOAA21_SP_2023.csv
  VIIRS_NOAA21_SP_2024.csv

After placing the files, re-run: python fetch_firms.py --skip-download
Or proceed directly to: python cluster.py

NOTE: VIIRS_NOAA21_SP is only available from 2023-03-01. Only 2023 and 2024
files are needed for NOAA-21.

=== END CHECKLIST ===
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def date_chunks(start: date, end: date, chunk: int):
    """Yield (chunk_start, days) pairs covering [start, end]."""
    cur = start
    while cur <= end:
        days = min(chunk, (end - cur).days + 1)
        yield cur, days
        cur += timedelta(days=days)


def download_chunk(key: str, product: str, start: date, days: int) -> pd.DataFrame | None:
    """
    Download one chunk from the FIRMS area API.
    Returns a DataFrame or None on failure.
    """
    url = f"{BASE_URL}/{key}/{product}/{BBOX}/{days}/{start.isoformat()}"
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        content = resp.text.strip()
        if not content or content.startswith("Not Found") or "error" in content.lower()[:50]:
            log.warning("Empty or error response for %s %s: %s", product, start, content[:100])
            return None
        from io import StringIO
        df = pd.read_csv(StringIO(content))
        return df
    except requests.RequestException as e:
        log.error("Request failed for %s %s: %s", product, start, e)
        return None


def filter_bbox(df: pd.DataFrame, product: str) -> tuple[pd.DataFrame, int]:
    """Drop rows outside the California bounding box. Returns (filtered_df, n_dropped)."""
    before = len(df)
    mask = (
        (df["latitude"] >= LAT_MIN) & (df["latitude"] <= LAT_MAX) &
        (df["longitude"] >= LON_MIN) & (df["longitude"] <= LON_MAX)
    )
    df = df[mask].copy()
    dropped = before - len(df)
    return df, dropped


def apply_confidence_filter(df: pd.DataFrame, product: str) -> tuple[pd.DataFrame, int]:
    """Apply per-sensor confidence filter. Returns (filtered_df, n_dropped)."""
    before = len(df)
    mask = CONFIDENCE_FILTERS[product](df)
    df = df[mask].copy()
    dropped = before - len(df)
    return df, dropped


def log_file_summary(product: str, year: int, df: pd.DataFrame,
                     n_bbox_dropped: int, n_conf_dropped: int) -> None:
    """Print the Gate 1 log line for one file."""
    if df.empty:
        log.info("G1 | %-22s %d | EMPTY after filters", product, year)
        return
    date_col = pd.to_datetime(df["acq_date"])
    log.info(
        "G1 | %-22s %d | rows=%7d | dates=%s to %s | bbox_dropped=%d | conf_dropped=%d",
        product, year, len(df),
        date_col.min().date(), date_col.max().date(),
        n_bbox_dropped, n_conf_dropped,
    )
    if "confidence" in df.columns:
        try:
            conf_vals = df["confidence"].value_counts().to_dict()
            log.info("     confidence distribution: %s", conf_vals)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main download routine
# ---------------------------------------------------------------------------

def fetch_product_year(key: str, product: str, year: int,
                       prod_start: date, prod_end: date) -> bool:
    """
    Download all chunks for one product × year, apply filters, write CSV.
    Returns True on success, False on any failure.
    """
    out_path = DATA_RAW / f"{product}_{year}.csv"
    if out_path.exists():
        log.info("Skipping %s %d — file already exists: %s", product, year, out_path)
        return True

    year_start = max(date(year, 1, 1), prod_start)
    year_end = min(date(year, 12, 31), prod_end)

    if year_start > year_end:
        log.info("Skipping %s %d — no data in range (product starts %s)",
                 product, year, prod_start)
        return True  # Not a failure; just no data expected

    log.info("Downloading %s %d (%s to %s) ...", product, year, year_start, year_end)

    chunks: list[pd.DataFrame] = []
    failed_chunks = 0

    for chunk_start, days in date_chunks(year_start, year_end, CHUNK_DAYS):
        chunk_df = download_chunk(key, product, chunk_start, days)
        if chunk_df is None:
            log.warning("Failed chunk %s %s+%dd", product, chunk_start, days)
            failed_chunks += 1
            continue
        if not chunk_df.empty:
            chunks.append(chunk_df)
        time.sleep(0.3)  # polite rate limiting

    if failed_chunks > 0:
        log.error("Product %s year %d had %d failed chunks. "
                  "Consider re-running or using manual fallback.",
                  product, year, failed_chunks)
        if not chunks:
            return False

    if not chunks:
        log.info("No data returned for %s %d (may be expected)", product, year)
        # Write an empty file so we don't re-fetch
        empty_header = get_expected_header(product)
        out_path.write_text(empty_header + "\n")
        return True

    df = pd.concat(chunks, ignore_index=True)
    df = df.drop_duplicates()

    # Apply filters
    df, n_bbox = filter_bbox(df, product)
    df, n_conf = apply_confidence_filter(df, product)

    df.to_csv(out_path, index=False)
    log_file_summary(product, year, df, n_bbox, n_conf)
    return True


def get_expected_header(product: str) -> str:
    """Return the CSV header for a given product."""
    if product == "MODIS_SP":
        return ("latitude,longitude,brightness,scan,track,acq_date,acq_time,"
                "satellite,instrument,confidence,version,bright_t31,frp,daynight,type")
    else:
        return ("latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,"
                "satellite,instrument,confidence,version,bright_ti5,frp,daynight,type")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(skip_download: bool = False) -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    if skip_download:
        log.info("--skip-download flag set; verifying existing files only.")
        verify_existing_files()
        return

    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not key:
        print(MANUAL_CHECKLIST)
        log.error("FIRMS_MAP_KEY is not set. Exiting at Gate 1.")
        sys.exit(1)

    all_ok = True

    for product, (prod_start, prod_end) in PRODUCTS.items():
        for year in range(2020, 2025):
            ok = fetch_product_year(key, product, year, prod_start, prod_end)
            if not ok:
                all_ok = False

    if not all_ok:
        log.error("One or more product-year downloads failed. See above for details.")
        log.error("If the network blocks FIRMS, use the manual fallback:")
        print(MANUAL_CHECKLIST)
        sys.exit(1)

    log.info("Gate 1 data acquisition complete. All files in %s", DATA_RAW)
    verify_existing_files()


def verify_existing_files() -> None:
    """
    Scan data/raw/ and emit a summary of what is present.
    Used both after download and with --skip-download.
    """
    log.info("=== Gate 1 file verification ===")
    expected = []
    for product, (prod_start, prod_end) in PRODUCTS.items():
        for year in range(2020, 2025):
            year_start = max(date(year, 1, 1), prod_start)
            year_end = min(date(year, 12, 31), prod_end)
            if year_start <= year_end:
                expected.append(f"{product}_{year}.csv")

    total_rows = 0
    for fname in expected:
        fpath = DATA_RAW / fname
        if not fpath.exists():
            log.warning("MISSING: %s", fpath)
            continue
        try:
            df = pd.read_csv(fpath)
            total_rows += len(df)
            if df.empty:
                log.info("  %-35s  EMPTY (no detections after filtering)", fname)
            else:
                date_col = pd.to_datetime(df["acq_date"])
                log.info("  %-35s  rows=%7d  dates=%s to %s",
                         fname, len(df), date_col.min().date(), date_col.max().date())
        except Exception as e:
            log.error("  %-35s  UNREADABLE: %s", fname, e)

    log.info("Total rows across all files: %d", total_rows)
    log.info("=== End Gate 1 verification ===")


if __name__ == "__main__":
    skip = "--skip-download" in sys.argv
    main(skip_download=skip)
