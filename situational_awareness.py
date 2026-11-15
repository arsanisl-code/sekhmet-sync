"""
situational_awareness.py — Operational Near Real-Time (NRT) ingestion & harmonization

Provides:
- Safe, non-blocking NASA FIRMS Area API client for provisional NRT data (last 30 days)
- Lean harmonization filter (MODIS conf >= 30, VIIRS conf != 'l' and FRP >= 6.5 MW)
- Historical median overlay for the active region
- Provenance and fallback banners complying with NASA Space Apps integrity rules
"""

import os
import io
import time
import logging
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

log = logging.getLogger("situational_awareness")

BASE_FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
NRT_SOURCES = ["MODIS_NRT", "VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]

FALLBACK_BANNER_TEXT = (
    "ℹ️ Live API query unavailable — displaying historical baseline only. "
    "The FIRMS key may be unconfigured, rate-limited, or NASA may have timed out. "
    "No live data was fetched."
)

PROVENANCE_BANNER_TEXT = (
    "⚠️ PROVISIONAL NRT DATA — SITUATIONAL AWARENESS ONLY\n\n"
    "NRT active fire detections are processed within 1–3 hours using predicted satellite ephemeris. "
    "Standard Processing (SP) replaces NRT with a lag of up to several months following definitive "
    "orbital calibration. NRT data should not be used for multi-year trend analysis.\n\n"
    "The current-month count is from NRT data and may not be directly comparable to the SP-derived "
    "historical median. This panel is for situational awareness, not for trend analysis."
)

THRESHOLD_LABEL_TEXT = (
    "VIIRS ≥6.5 MW threshold — experimental, fitted on California 2012–2013 monthly overlap "
    "(r = 0.9974, monthly only). Not validated on daily 2020–2024 data, and not validated outside California."
)

EMPTY_STATE_TEXT = (
    "No live data fetched yet — historical median shown. "
    "Use 'Fetch Live FIRMS NRT' below to check recent activity."
)

CAPTION_TEXT = (
    "Median is from Standard Processing (SP) 2020–2024, same calendar day. "
    "NRT and SP are not directly comparable — see provenance banner."
)


def get_firms_key() -> str | None:
    """Retrieve NASA FIRMS MAP key strictly from environment or Streamlit secrets."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    key = os.environ.get("FIRMS_MAP_KEY")
    if not key or key.strip() in ("", "PASTE_YOUR_KEY_HERE"):
        try:
            from pathlib import Path
            app_dir = Path(__file__).resolve().parent
            local_secrets = app_dir / ".streamlit" / "secrets.toml"
            user_secrets = Path.home() / ".streamlit" / "secrets.toml"
            if local_secrets.exists() or user_secrets.exists():
                import streamlit as st
                if "FIRMS_MAP_KEY" in st.secrets:
                    key = st.secrets["FIRMS_MAP_KEY"]
        except Exception:
            key = None

    if key and key.strip() not in ("", "PASTE_YOUR_KEY_HERE"):
        return key.strip()
    return None


def fetch_nrt_data(
    bounds: dict,
    key: str | None = None,
    timeout: int = 15,
    today_override: date | None = None,
) -> tuple[bool, str, pd.DataFrame | None]:
    """
    Fetch last 30 days of NRT data across 4 sensors via NASA FIRMS Area API.
    Uses 6 chunks of 5 days (FIRMS Area API limits day_range to [1..5]).
    Returns:
      (success: bool, status_code: str, raw_df: pd.DataFrame | None)
    """
    api_key = key if key is not None else get_firms_key()
    if not api_key or api_key.strip() in ("", "PASTE_YOUR_KEY_HERE"):
        return False, "NO_KEY", None

    min_lat = bounds["min_lat"]
    max_lat = bounds["max_lat"]
    min_lon = bounds["min_lon"]
    max_lon = bounds["max_lon"]
    bbox_str = f"{min_lon:.4f},{min_lat:.4f},{max_lon:.4f},{max_lat:.4f}"

    today = today_override or date.today()
    start_date = today - timedelta(days=29)

    # 6 chunks of 5 days covering [start_date, today]
    chunk_starts = [start_date + timedelta(days=i * 5) for i in range(6)]

    tasks = []
    for source in NRT_SOURCES:
        for c_start in chunk_starts:
            tasks.append((source, c_start))

    def fetch_single(task):
        src, c_dt = task
        url = f"{BASE_FIRMS_URL}/{api_key}/{src}/{bbox_str}/5/{c_dt.isoformat()}"
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code != 200:
                log.warning("FIRMS API returned HTTP %d for %s", resp.status_code, src)
                return False, resp.status_code, None
            txt = resp.text.strip()
            if not txt:
                return True, 200, None
            # Check for error responses returned as text
            if txt.startswith("Not Found") or "invalid" in txt.lower()[:30] or "error" in txt.lower()[:30]:
                log.warning("FIRMS API returned error message: %s", txt[:100])
                return False, "API_ERROR", None
            try:
                df = pd.read_csv(io.StringIO(txt))
                # Add metadata columns if missing
                if "source_product" not in df.columns:
                    df["source_product"] = src
                return True, 200, df
            except Exception as e:
                log.warning("Failed to parse CSV response: %s", e)
                return False, "PARSE_ERROR", None
        except requests.exceptions.RequestException as e:
            log.warning("FIRMS API request failed: %s", e)
            return False, "REQUEST_EXCEPTION", None

    collected_dfs = []
    # Execute with worker pool for fast non-blocking retrieval
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(fetch_single, tasks))

    for ok, status, df in results:
        if not ok:
            log.warning("Sub-query failed with status %s; triggering fallback banner", status)
            return False, str(status), None
        if df is not None and not df.empty:
            collected_dfs.append(df)

    if collected_dfs:
        combined_df = pd.concat(collected_dfs, ignore_index=True)
    else:
        combined_df = pd.DataFrame(
            columns=[
                "latitude", "longitude", "scan", "track", "acq_date",
                "acq_time", "satellite", "instrument", "confidence", "frp"
            ]
        )

    return True, "OK", combined_df


def harmonize_nrt_data(raw_df: pd.DataFrame | None) -> tuple[pd.DataFrame, dict]:
    """
    Apply the lean harmonization rule to provisional NRT data:
    - MODIS: confidence >= 30, counted as-is
    - VIIRS: confidence != 'l' AND frp >= 6.5 MW, counted
    - acq_time: zero-padded string ('0944' instead of '944')
    Returns:
      (harmonised_df, stats_dict)
    """
    if raw_df is None or raw_df.empty:
        empty_df = pd.DataFrame(
            columns=["date", "latitude", "longitude", "acq_time", "sensor", "satellite", "frp"]
        )
        stats = {
            "raw_total": 0,
            "harmonised_total": 0,
            "modis_kept": 0,
            "viirs_kept": 0,
            "filtered_sub_threshold": 0,
        }
        return empty_df, stats

    df = raw_df.copy()

    # Normalize instrument identification
    if "instrument" in df.columns:
        inst = df["instrument"].astype(str).str.upper()
    else:
        inst = df["satellite"].astype(str).map(
            lambda s: "MODIS" if s in ["Terra", "Aqua", "T", "A", "1", "2"] else "VIIRS"
        )

    is_modis = inst == "MODIS"
    is_viirs = inst == "VIIRS"

    # MODIS filter: confidence >= 30
    modis_conf = pd.to_numeric(df["confidence"], errors="coerce").fillna(0)
    modis_mask = is_modis & (modis_conf >= 30)

    # VIIRS filter: confidence != 'l' and FRP >= 6.5 MW
    viirs_conf = df["confidence"].astype(str).str.lower() != "l"
    viirs_frp = pd.to_numeric(df["frp"], errors="coerce").fillna(0)
    viirs_mask = is_viirs & viirs_conf & (viirs_frp >= 6.5)

    kept_mask = modis_mask | viirs_mask
    harmonised = df[kept_mask].copy()

    # Zero-pad acq_time (FIRMS drops leading zeros)
    harmonised["acq_time"] = (
        harmonised["acq_time"].astype(str).str.split(".").str[0].str.strip().str.zfill(4)
    )

    # Standardize date and sensor
    harmonised["date"] = pd.to_datetime(harmonised["acq_date"]).dt.strftime("%Y-%m-%d")
    harmonised["sensor"] = inst[kept_mask].values
    harmonised["frp"] = pd.to_numeric(harmonised["frp"], errors="coerce").fillna(0)

    stats = {
        "raw_total": int(len(df)),
        "harmonised_total": int(len(harmonised)),
        "modis_kept": int(modis_mask.sum()),
        "viirs_kept": int(viirs_mask.sum()),
        "filtered_sub_threshold": int(len(df) - len(harmonised)),
    }

    cols = [
        col for col in ["date", "latitude", "longitude", "acq_time", "sensor", "satellite", "frp"]
        if col in harmonised.columns
    ]
    return harmonised[cols], stats


def build_comparison_series(
    harmonised_nrt_df: pd.DataFrame | None,
    daily_historical: pd.DataFrame | None,
    cov_status: str,
    today_override: date | None = None,
) -> pd.DataFrame:
    """
    Build daily comparison dataframe over the last 30 calendar days:
    - date (last 30 days)
    - doy (day of year)
    - nrt_hotspots (None if no NRT fetched yet; otherwise daily count)
    - median_hotspots (None if OUT_OF_COVERAGE; otherwise SP 2020-2024 median)
    """
    today = today_override or date.today()
    start_date = today - timedelta(days=29)
    spine = pd.date_range(start_date, today, freq="D")

    comp_df = pd.DataFrame({"date_dt": spine})
    comp_df["date"] = comp_df["date_dt"].dt.strftime("%Y-%m-%d")
    comp_df["doy"] = comp_df["date_dt"].dt.dayofyear

    # 1. Historical Median
    if cov_status != "OUT_OF_COVERAGE" and daily_historical is not None and not daily_historical.empty:
        # Group by DOY from daily_historical
        dh = daily_historical.copy()
        if "doy" not in dh.columns:
            dh["doy"] = dh["date"].dt.dayofyear
        doy_median = dh.groupby("doy")["median_hotspots"].first()
        comp_df["median_hotspots"] = comp_df["doy"].map(doy_median).fillna(0)
    else:
        comp_df["median_hotspots"] = None

    # 2. Provisional NRT Hotspots
    if harmonised_nrt_df is not None and not harmonised_nrt_df.empty:
        nrt_daily = harmonised_nrt_df.groupby("date").size().rename("nrt_hotspots")
        comp_df = comp_df.merge(nrt_daily, on="date", how="left")
        comp_df["nrt_hotspots"] = comp_df["nrt_hotspots"].fillna(0).astype(int)
    else:
        comp_df["nrt_hotspots"] = None

    return comp_df[["date", "doy", "nrt_hotspots", "median_hotspots"]]
