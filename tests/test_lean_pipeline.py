"""
test_lean_pipeline.py — Active unit and integration tests for Sekhmet Sync.

Validates:
1. Daily time series integrity (1,827 days, zero missing dates, reconciled totals).
2. Per-detection dataset integrity (347,174 rows, spatial bounds, sensor breakdown).
3. Sub-region filtering and preset bounding boxes.
4. Out-of-coverage boundary guard rules.
5. Search-matched sliced CSV export logic.
6. Multi-scale calendar view rendering via Streamlit AppTest.
"""

from pathlib import Path
from datetime import date
import pandas as pd
import pytest


def test_daily_series_harmonised_integrity():
    """Verify daily_series_harmonised.csv satisfies all challenge constraints."""
    csv_path = Path("data/daily_series_harmonised.csv")
    assert csv_path.exists(), "daily_series_harmonised.csv must exist"

    df = pd.read_csv(csv_path, parse_dates=["date"])
    assert len(df) == 1827, f"Expected exactly 1,827 days (2020-2024), got {len(df)}"
    assert df["date"].min() == pd.Timestamp("2020-01-01")
    assert df["date"].max() == pd.Timestamp("2024-12-31")
    assert df["date"].isna().sum() == 0, "No dates should be missing"

    # Reconciled in-state sums
    assert df["raw_modis_hotspots"].sum() == 113795
    assert df["raw_viirs_hotspots"].sum() == 608801
    assert df["harmonised_hotspots"].sum() == 347174

    # Peak day must be 2020-09-09 with 10,320 hotspots
    pk_row = df.loc[df["harmonised_hotspots"].idxmax()]
    assert pk_row["date"] == pd.Timestamp("2020-09-09")
    assert pk_row["harmonised_hotspots"] == 10320

    # Leap day handling: DOY 60 is Feb 29 in leap years
    leap_days = df[df["date"].dt.strftime("%m-%d") == "02-29"]
    assert len(leap_days) == 2, "Expected Feb 29 in 2020 and 2024"
    assert set(leap_days["date"].dt.year) == {2020, 2024}


def test_detections_integrity():
    """Verify harmonised_detections.csv satisfies spatial bounds and sensor counts."""
    csv_path = Path("data/harmonised_detections.csv")
    assert csv_path.exists(), "harmonised_detections.csv must exist"

    df = pd.read_csv(csv_path, parse_dates=["date"])
    assert len(df) == 347174, f"Expected 347,174 rows, got {len(df)}"
    assert set(df["sensor"].unique()) == {"MODIS", "VIIRS"}
    assert (df["frp"] >= 0).all(), "All detections must have FRP >= 0"

    # California spatial envelope check
    assert (df["latitude"].between(32.5, 42.0)).all()
    assert (df["longitude"].between(-124.5, -114.0)).all()

    # Sensor breakdown
    modis_count = (df["sensor"] == "MODIS").sum()
    viirs_count = (df["sensor"] == "VIIRS").sum()
    assert modis_count == 113795
    assert viirs_count == 233379

    # VIIRS 6.5 MW threshold compliance
    viirs_df = df[df["sensor"] == "VIIRS"]
    assert (viirs_df["frp"] >= 6.5).all(), "All harmonised VIIRS detections must have FRP >= 6.5 MW"


def test_subregion_filtering():
    """Verify spatial sub-region slicing produces expected subsets."""
    from app import REGIONS, filter_data, load_statewide_daily, load_detections

    daily = load_statewide_daily()
    detections = load_detections()
    assert daily is not None and detections is not None

    full_dates = (date(2020, 1, 1), date(2024, 12, 31))

    # Northern Forests (Klamath)
    d_klam, det_klam, cov, _ = filter_data(
        daily, detections, "California — Northern Forests (Klamath)", None, full_dates
    )
    assert cov == "FULL_COVERAGE"
    assert len(det_klam) == 182441
    assert d_klam["harmonised_hotspots"].sum() == 182441

    # Sierra Nevada / Central
    d_sierra, det_sierra, cov, _ = filter_data(
        daily, detections, "California — Sierra Nevada / Central", None, full_dates
    )
    assert cov == "FULL_COVERAGE"
    assert len(det_sierra) == 73757
    assert d_sierra["harmonised_hotspots"].sum() == 73757


def test_out_of_coverage_rule():
    """Verify that bounding box outside California halts with OUT_OF_COVERAGE."""
    from app import filter_data, load_statewide_daily, load_detections

    daily = load_statewide_daily()
    detections = load_detections()

    # Greece bounding box (outside California)
    greece_bbox = {"min_lat": 37.0, "max_lat": 39.0, "min_lon": 21.0, "max_lon": 24.0}
    full_dates = (date(2020, 1, 1), date(2024, 12, 31))

    d_out, det_out, cov, _ = filter_data(
        daily, detections, "Custom Lat / Lon Bounding Box", greece_bbox, full_dates
    )
    assert cov == "OUT_OF_COVERAGE"


def test_sliced_export_fidelity():
    """Verify that CSV export bytes match the active region and date slice."""
    from app import filter_data, get_csv_bytes, load_statewide_daily, load_detections

    daily = load_statewide_daily()
    detections = load_detections()

    # August 2021 Sierra Nevada
    aug_2021 = (date(2021, 8, 1), date(2021, 8, 31))
    d_sub, det_sub, cov, _ = filter_data(
        daily, detections, "California — Sierra Nevada / Central", None, aug_2021
    )

    assert len(d_sub) == 31, "August must have exactly 31 daily rows"
    daily_bytes = get_csv_bytes(d_sub)
    det_bytes = get_csv_bytes(det_sub)

    assert len(daily_bytes) > 0
    assert len(det_bytes) > 0

    # Ensure export contains August 2021 dates only
    export_daily_df = pd.read_csv(pd.io.common.BytesIO(daily_bytes))
    assert (export_daily_df["date"].str.startswith("2021-08")).all()


def test_app_test_execution_and_views():
    """Verify Streamlit app startup and all calendar view modes render with zero exceptions."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("app.py", default_timeout=30)
    app.run()
    assert not app.exception, f"App crashed on startup: {app.exception}"

    # Verify initial metric values
    metric_labels = [m.label for m in app.metric]
    assert "Raw Hotspots" in metric_labels
    assert "Harmonised Hotspots" in metric_labels

    # Verify all 3 calendar views
    radios = [r for r in app.radio if "Daily Matrix" in str(r.options)]
    assert len(radios) >= 1
    cal_radio = radios[0]

    # Test Monthly view (5x12)
    cal_radio.set_value(cal_radio.options[1]).run()
    assert not app.exception

    # Test Daily Line view
    cal_radio.set_value(cal_radio.options[2]).run()
    assert not app.exception


def test_spatial_footprint_rendering():
    """Verify spatial footprint sampling and map generation logic."""
    from app import filter_data, load_statewide_daily, load_detections, CALIFORNIA_BBOX

    daily = load_statewide_daily()
    detections = load_detections()
    full_dates = (date(2020, 1, 1), date(2024, 12, 31))

    _, det_klam, cov, bounds = filter_data(
        daily, detections, "California — Northern Forests (Klamath)", None, full_dates
    )
    assert len(det_klam) == 182441
    # Check sampling
    d_map = det_klam.sample(5000, random_state=42) if len(det_klam) > 5000 else det_klam
    assert len(d_map) == 5000
    assert set(d_map["sensor"].unique()).issubset({"MODIS", "VIIRS"})
    assert (d_map["latitude"].between(bounds["min_lat"], bounds["max_lat"])).all()
    assert (d_map["longitude"].between(bounds["min_lon"], bounds["max_lon"])).all()


def test_critical_periods_and_season_window():
    """Verify season window (p10 to p90) and sustained critical streak calculations."""
    from app import calculate_season_window, calculate_critical_streaks, load_statewide_daily

    daily = load_statewide_daily()
    assert daily is not None

    sw = calculate_season_window(daily)
    assert sw is not None
    assert sw["duration"] == 85
    assert sw["start_str"] == "Jul 11"
    assert sw["end_str"] == "Oct 03"

    streaks = calculate_critical_streaks(daily, multiplier=3.0, min_streak_len=3)
    assert not streaks.empty
    top_streak = streaks.iloc[0]
    assert top_streak["duration_days"] == 23
    assert top_streak["peak_daily_hotspots"] == 5452
