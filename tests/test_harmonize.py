"""
test_harmonize.py — Unit tests for harmonize.py

SYNTHETIC TEST DATA — not real FIRMS data.
All test DataFrames are constructed inline; no real FIRMS data is used.

Tests cover:
  - daily_series row count (1,827 for 2020–2024)
  - Required column order
  - FRP sum reconciliation (G3.4)
  - Historical median computation
  - Anomaly sign (positive anomaly on a day with fires above median)
  - FRP correction factors per sensor
"""

import sys
from pathlib import Path
from datetime import date

import pandas as pd
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from harmonize import (
    apply_frp_correction,
    build_daily_series,
    compute_historical_median,
    compute_per_fire_sensor_frp,
    MODIS_FRP_FACTOR,
    VIIRS_FRP_FACTOR,
    EXPECTED_DAILY_ROWS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fires_df(rows: list[dict]) -> pd.DataFrame:
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    Build a minimal fires DataFrame with required columns.
    """
    defaults = {
        "fire_id": "CA-2021-08-01-001",
        "date": "2021-08-01",
        "centroid_lat": 38.0,
        "centroid_lon": -120.0,
        "n_detections": 1,
        "n_modis": 1,
        "n_viirs": 0,
        "sensors_present": "modis_only",
        "total_frp": 10.0,
        "max_frp": 10.0,
        "mean_brightness": 320.0,
        "first_acq_time": "1200",
        "last_acq_time": "1200",
    }
    result = []
    for i, row in enumerate(rows):
        d = defaults.copy()
        d["fire_id"] = f"CA-2021-08-01-{i+1:03d}"
        d.update(row)
        result.append(d)
    return pd.DataFrame(result)


# ---------------------------------------------------------------------------
# Test: EXPECTED_DAILY_ROWS constant
# ---------------------------------------------------------------------------

def test_expected_daily_rows():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    2020: 366 (leap), 2021: 365, 2022: 365, 2023: 365, 2024: 366 (leap)
    Total: 1827.
    """
    date_range = pd.date_range("2020-01-01", "2024-12-31", freq="D")
    assert len(date_range) == EXPECTED_DAILY_ROWS == 1827


# ---------------------------------------------------------------------------
# Test: build_daily_series row count
# ---------------------------------------------------------------------------

def test_build_daily_series_row_count():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    daily_series must have exactly 1,827 rows for 2020–2024, even if
    the input fires only cover a subset of dates.
    """
    # Only two fire records; all other dates should be zero
    fires = make_fires_df([
        {"date": "2020-01-15", "fire_id": "CA-2020-01-15-001", "total_frp": 20.0},
        {"date": "2024-12-31", "fire_id": "CA-2024-12-31-001", "total_frp": 15.0},
    ])
    fires = apply_frp_correction(fires)
    daily = build_daily_series(fires)

    assert len(daily) == EXPECTED_DAILY_ROWS, (
        f"Expected {EXPECTED_DAILY_ROWS} rows, got {len(daily)}"
    )


# ---------------------------------------------------------------------------
# Test: required column order
# ---------------------------------------------------------------------------

def test_daily_series_column_order():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    The first six columns of daily_series must be in the specified order.
    """
    fires = make_fires_df([
        {"date": "2021-06-01", "fire_id": "CA-2021-06-01-001", "total_frp": 10.0},
    ])
    fires = apply_frp_correction(fires)
    daily = build_daily_series(fires)

    required = ["date", "raw_modis", "raw_viirs", "harmonised_fires",
                "total_frp_corrected", "total_frp_raw", "median_fires"]

    for i, col in enumerate(required):
        assert daily.columns[i] == col, (
            f"Column {i} should be '{col}', got '{daily.columns[i]}'"
        )


# ---------------------------------------------------------------------------
# Test: FRP sum reconciliation (G3.4)
# ---------------------------------------------------------------------------

def test_frp_sum_reconciliation():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    sum(total_frp_raw in daily) == sum(total_frp in fires) within rtol=1e-5.
    """
    fires = make_fires_df([
        {"date": "2021-08-01", "fire_id": "CA-2021-08-01-001",
         "sensors_present": "modis_only", "total_frp": 100.0, "n_detections": 2,
         "n_modis": 2, "n_viirs": 0},
        {"date": "2021-08-01", "fire_id": "CA-2021-08-01-002",
         "sensors_present": "viirs_only", "total_frp": 50.0, "n_detections": 3,
         "n_modis": 0, "n_viirs": 3},
        {"date": "2021-08-02", "fire_id": "CA-2021-08-02-001",
         "sensors_present": "both", "total_frp": 80.0, "n_detections": 4,
         "n_modis": 2, "n_viirs": 2},
    ])
    fires = apply_frp_correction(fires)
    daily = build_daily_series(fires)

    fires_frp_sum = float(fires["total_frp"].sum())
    daily_frp_sum = float(daily["total_frp_raw"].sum())
    rel_err = abs(daily_frp_sum - fires_frp_sum) / max(fires_frp_sum, 1e-9)
    assert rel_err < 1e-5, (
        f"FRP sum mismatch: daily={daily_frp_sum:.6f}, fires={fires_frp_sum:.6f}, "
        f"rel_err={rel_err:.2e}"
    )


# ---------------------------------------------------------------------------
# Test: harmonised_fires count matches fire row count
# ---------------------------------------------------------------------------

def test_harmonised_fires_count():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    sum(harmonised_fires) in daily must equal the number of rows in fires.
    """
    n_fires = 5
    rows = [
        {"date": "2021-08-01", "fire_id": f"CA-2021-08-01-{i+1:03d}",
         "total_frp": float(10 + i)}
        for i in range(3)
    ] + [
        {"date": "2021-08-02", "fire_id": f"CA-2021-08-02-{i+1:03d}",
         "total_frp": float(20 + i)}
        for i in range(2)
    ]
    fires = make_fires_df(rows)
    fires = apply_frp_correction(fires)
    daily = build_daily_series(fires)

    assert int(daily["harmonised_fires"].sum()) == n_fires


# ---------------------------------------------------------------------------
# Test: FRP correction factors
# ---------------------------------------------------------------------------

def test_frp_correction_modis_only():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    MODIS-only fire should have frp_correction_factor == 1.0.
    """
    fires = make_fires_df([{
        "sensors_present": "modis_only",
        "total_frp": 100.0,
        "n_detections": 2,
        "n_modis": 2,
        "n_viirs": 0,
    }])
    fires = apply_frp_correction(fires)
    assert pytest.approx(fires.iloc[0]["frp_correction_factor"]) == MODIS_FRP_FACTOR
    assert pytest.approx(fires.iloc[0]["total_frp_corrected"]) == 100.0 * MODIS_FRP_FACTOR


def test_frp_correction_viirs_only():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    VIIRS-only fire should have frp_correction_factor == 0.85.
    """
    fires = make_fires_df([{
        "sensors_present": "viirs_only",
        "total_frp": 100.0,
        "n_detections": 3,
        "n_modis": 0,
        "n_viirs": 3,
    }])
    fires = apply_frp_correction(fires)
    assert pytest.approx(fires.iloc[0]["frp_correction_factor"]) == VIIRS_FRP_FACTOR
    assert pytest.approx(fires.iloc[0]["total_frp_corrected"]) == 100.0 * VIIRS_FRP_FACTOR


def test_frp_correction_both_sensors():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    'both' fire: factor = weighted average of MODIS and VIIRS factors.
    """
    fires = make_fires_df([{
        "sensors_present": "both",
        "total_frp": 100.0,
        "n_detections": 4,
        "n_modis": 2,
        "n_viirs": 2,
    }])
    fires = apply_frp_correction(fires)
    expected_factor = (2 * MODIS_FRP_FACTOR + 2 * VIIRS_FRP_FACTOR) / 4
    assert pytest.approx(fires.iloc[0]["frp_correction_factor"]) == expected_factor


# ---------------------------------------------------------------------------
# Test: historical median and anomaly
# ---------------------------------------------------------------------------

def test_historical_median_and_anomaly():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    For a day with more fires than the median, anomaly_fires should be positive.
    For a day with no fires, anomaly_fires should be negative (or zero).

    We seed fires only on Jan 1 of 2020 and 2021 to test median computation.
    2020: 10 fires, 2021: 2 fires → median for DOY 1 = (10+2)/2 = 6.0
    2022: 8 fires → anomaly = 8 - 6 = +2
    """
    # Build a minimal fires dataset
    rows = []
    for i in range(10):
        rows.append({
            "date": "2020-01-01",
            "fire_id": f"CA-2020-01-01-{i+1:03d}",
            "total_frp": 10.0,
            "sensors_present": "modis_only",
            "n_detections": 1, "n_modis": 1, "n_viirs": 0,
        })
    for i in range(2):
        rows.append({
            "date": "2021-01-01",
            "fire_id": f"CA-2021-01-01-{i+1:03d}",
            "total_frp": 10.0,
            "sensors_present": "modis_only",
            "n_detections": 1, "n_modis": 1, "n_viirs": 0,
        })
    for i in range(8):
        rows.append({
            "date": "2022-01-01",
            "fire_id": f"CA-2022-01-01-{i+1:03d}",
            "total_frp": 10.0,
            "sensors_present": "modis_only",
            "n_detections": 1, "n_modis": 1, "n_viirs": 0,
        })

    fires = make_fires_df(rows)
    # Override fire_id to avoid make_fires_df default
    for i, row in enumerate(rows):
        fires.loc[i, "fire_id"] = row["fire_id"]
        fires.loc[i, "date"] = row["date"]
        fires.loc[i, "total_frp"] = row["total_frp"]
        fires.loc[i, "sensors_present"] = row["sensors_present"]
        fires.loc[i, "n_detections"] = row["n_detections"]
        fires.loc[i, "n_modis"] = row["n_modis"]
        fires.loc[i, "n_viirs"] = row["n_viirs"]

    fires = apply_frp_correction(fires)
    daily = build_daily_series(fires)
    daily = compute_historical_median(daily)

    # DOY 1 = Jan 1
    # Years with data: 2020 (10), 2021 (2), 2022 (8), 2023 (0), 2024 (0)
    # Median across [10, 2, 8, 0, 0] = 2.0
    jan1_rows = daily[daily["date"].dt.strftime("%m-%d") == "01-01"].copy()
    assert len(jan1_rows) == 5, "Should have 5 Jan-1 rows (one per year)"

    # median of [10, 2, 8, 0, 0] sorted = [0, 0, 2, 8, 10] → median = 2.0
    median_val = jan1_rows["median_fires"].iloc[0]
    assert pytest.approx(median_val) == 2.0, f"Expected median 2.0, got {median_val}"

    # 2022 has 8 fires, median = 2, anomaly should be +6
    row_2022 = jan1_rows[jan1_rows["date"].dt.year == 2022].iloc[0]
    assert pytest.approx(row_2022["anomaly_fires"]) == 6.0, (
        f"Expected anomaly +6, got {row_2022['anomaly_fires']}"
    )

    # 2023 has 0 fires, anomaly should be -2
    row_2023 = jan1_rows[jan1_rows["date"].dt.year == 2023].iloc[0]
    assert pytest.approx(row_2023["anomaly_fires"]) == -2.0, (
        f"Expected anomaly -2, got {row_2023['anomaly_fires']}"
    )


# ---------------------------------------------------------------------------
# Test: leap year rows present
# ---------------------------------------------------------------------------

def test_leap_year_rows():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    daily_series must include Feb 29 rows for 2020 and 2024.
    """
    fires = make_fires_df([{
        "date": "2020-02-29",
        "fire_id": "CA-2020-02-29-001",
        "total_frp": 5.0,
    }])
    fires = apply_frp_correction(fires)
    daily = build_daily_series(fires)

    feb29_2020 = daily[daily["date"].dt.strftime("%Y-%m-%d") == "2020-02-29"]
    assert len(feb29_2020) == 1

    feb29_2024 = daily[daily["date"].dt.strftime("%Y-%m-%d") == "2024-02-29"]
    assert len(feb29_2024) == 1
