"""
test_extended_pipeline.py
Tests for the extended harmonised series 2000-2024.
Reads committed output files — does NOT re-run the pipeline.
"""
import pandas as pd
import pytest
from pathlib import Path
from shapely.geometry import shape, Point
import json

DAILY_EXT    = Path("data/daily_series_harmonised_extended.csv")
DET_EXT      = Path("data/harmonised_detections_extended.csv")
CA_GEOJSON   = Path("data/california.geojson")

FROZEN_HARM_TOTAL  = 347_174
FROZEN_PEAK_DATE   = "2020-09-09"
FROZEN_PEAK_COUNT  = 10_320
NEVADA_POINT       = Point(-119.0, 39.0)   # Reno NV — outside CA
CALIFORNIA_PT      = Point(-119.5, 37.3)   # Central CA — inside CA


@pytest.fixture(scope="module")
def daily():
    return pd.read_csv(DAILY_EXT, parse_dates=["date"])


@pytest.fixture(scope="module")
def det():
    return pd.read_csv(DET_EXT)


@pytest.fixture(scope="module")
def ca_poly():
    return shape(json.loads(CA_GEOJSON.read_text())["features"][0]["geometry"])


# --- 1. File existence ---

def test_extended_files_exist():
    assert DAILY_EXT.exists(), f"Missing {DAILY_EXT}"
    assert DET_EXT.exists(),   f"Missing {DET_EXT}"


# --- 2. Daily integrity ---

def test_extended_daily_row_count(daily):
    assert len(daily) == 8827, f"Expected 8827 rows, got {len(daily)}"


def test_extended_daily_date_range(daily):
    assert daily["date"].min().strftime("%Y-%m-%d") == "2000-11-01"
    assert daily["date"].max().strftime("%Y-%m-%d") == "2024-12-31"


def test_extended_daily_no_duplicate_dates(daily):
    assert daily["date"].duplicated().sum() == 0


def test_extended_daily_no_dates_outside_range(daily):
    assert (daily["date"] >= "2000-11-01").all()
    assert (daily["date"] <= "2024-12-31").all()


def test_extended_daily_sum_equals_detections(daily, det):
    assert int(daily["harmonised_hotspots"].sum()) == len(det)


# --- 3. Gate 2: 2020-2024 subset matches frozen baseline ---

def test_2020_2024_subset_matches_frozen(daily):
    sub = daily[(daily["date"] >= "2020-01-01") & (daily["date"] <= "2024-12-31")]
    ext_sum = int(sub["harmonised_hotspots"].sum())
    assert ext_sum == FROZEN_HARM_TOTAL, (
        f"2020-2024 sum {ext_sum} != frozen {FROZEN_HARM_TOTAL} (delta {ext_sum - FROZEN_HARM_TOTAL})"
    )


def test_2020_2024_peak_matches_frozen(daily):
    sub = daily[(daily["date"] >= "2020-01-01") & (daily["date"] <= "2024-12-31")]
    pk = sub.loc[sub["harmonised_hotspots"].idxmax()]
    assert pk["date"].strftime("%Y-%m-%d") == FROZEN_PEAK_DATE
    assert int(pk["harmonised_hotspots"]) == FROZEN_PEAK_COUNT


# --- 4. Required columns ---

def test_extended_daily_required_columns(daily):
    required = [
        "date", "raw_modis_hotspots", "raw_viirs_hotspots",
        "harmonised_hotspots", "harmonised_hotspots_satnorm",
        "n_satellites_viirs", "n_satellites_total", "era",
        "median_hotspots", "anomaly_hotspots",
    ]
    for col in required:
        assert col in daily.columns, f"Missing column: {col}"


def test_extended_detections_required_columns(det):
    for col in ["date","latitude","longitude","frp","sensor","satellite"]:
        assert col in det.columns, f"Missing column: {col}"


# --- 5. Polygon clip ---

def test_nevada_point_outside_ca(ca_poly):
    assert not ca_poly.contains(NEVADA_POINT)


def test_california_point_inside_ca(ca_poly):
    assert ca_poly.contains(CALIFORNIA_PT)


def test_no_detections_at_nevada_point(det):
    hits = det[
        (det["latitude"].round(1)  == round(NEVADA_POINT.y, 1)) &
        (det["longitude"].round(1) == round(NEVADA_POINT.x, 1))
    ]
    assert len(hits) == 0, f"Found {len(hits)} detections at Nevada test point"


# --- 6. Constellation columns ---

def test_n_satellites_viirs_zero_before_2012(daily):
    before = daily[daily["date"].dt.year <= 2011]
    assert (before["n_satellites_viirs"] == 0).all()


def test_n_satellites_viirs_one_for_2012_to_2017(daily):
    yr = daily[(daily["date"].dt.year >= 2012) & (daily["date"].dt.year <= 2017)]
    assert (yr["n_satellites_viirs"] == 1).all()


def test_n_satellites_viirs_two_from_2018(daily):
    yr = daily[daily["date"].dt.year >= 2018]
    assert (yr["n_satellites_viirs"] == 2).all()


def test_era_terra_only_before_2002(daily):
    assert (daily[daily["date"].dt.year <= 2001]["era"] == "Terra-only").all()


def test_era_correct_for_2020(daily):
    assert (daily[daily["date"].dt.year == 2020]["era"] == "Terra+Aqua+S-NPP+NOAA-20").all()


def test_era_correct_for_2023(daily):
    assert (daily[daily["date"].dt.year == 2023]["era"] == "Terra+Aqua+NOAA-20+NOAA-21").all()


# --- 7. No forbidden methods in pipeline script ---

def test_no_085_factor_applied_in_script():
    script = Path("build_daily_harmonized_extended.py").read_text(encoding="utf-8")
    # Flag only lines that apply 0.85 numerically (multiply or assign)
    bad = [l for l in script.splitlines()
           if "0.85" in l and ("*" in l or "= 0.85" in l)
           and not l.strip().startswith("#")]
    assert len(bad) == 0, f"Found 0.85 factor applied in code: {bad}"


def test_no_clustering_in_script():
    script = Path("build_daily_harmonized_extended.py").read_text(encoding="utf-8")
    for token in ["KDTree", "union_find", "UnionFind"]:
        assert token not in script, f"Found forbidden token '{token}' in script"


def test_no_nrt_in_detections(det):
    nrt = det[det["satellite"].astype(str).str.upper().str.contains("NRT")]
    assert len(nrt) == 0, f"Found {len(nrt)} NRT rows in extended detections"


# --- 8. Satnorm sanity ---

def test_satnorm_equals_harmonised_in_modis_only_era(daily):
    modis_only = daily[daily["date"].dt.year <= 2011].copy()
    diff = (modis_only["harmonised_hotspots"] - modis_only["harmonised_hotspots_satnorm"]).abs()
    assert (diff < 0.01).all(), "satnorm should equal harmonised in MODIS-only era (divisor=1)"


def test_satnorm_lte_harmonised_in_viirs_era(daily):
    viirs = daily[(daily["date"].dt.year >= 2012) & (daily["harmonised_hotspots"] > 0)]
    assert (viirs["harmonised_hotspots_satnorm"] <= viirs["harmonised_hotspots"] + 0.01).all()


# --- 9. In-App Horizon Toggle ---

def test_app_test_horizon_toggle():
    """Verify in-app switching between Core Baseline and 25-Yr Climatology."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("app.py", default_timeout=30)
    app.run()
    assert not app.exception

    # Locate horizon radio in sidebar
    horizon_radios = [r for r in app.sidebar.radio if "Climatology" in str(r.options)]
    assert len(horizon_radios) == 1, "Expected horizon selector in sidebar"
    h_radio = horizon_radios[0]

    # Switch to 25-Yr Climatology
    h_radio.set_value(h_radio.options[1]).run()
    assert not app.exception

    # Harmonised hotspots must reflect the 25-year total (704,911)
    metrics_map = {m.label: m.value for m in app.metric}
    assert metrics_map.get("Harmonised Hotspots") == "704,911"
    assert metrics_map.get("Peak Day") == "2020-09-09"

    # Verify calendar options update to 25 years
    cal_radios = [r for r in app.radio if "Daily Matrix" in str(r.options)]
    assert len(cal_radios) >= 1
    cal_radio = cal_radios[0]
    assert "25×366" in cal_radio.options[0]
    assert "25×12" in cal_radio.options[1]

    # Test monthly heatmap and daily line under extended horizon
    cal_radio.set_value(cal_radio.options[1]).run()
    assert not app.exception
    cal_radio.set_value(cal_radio.options[2]).run()
    assert not app.exception

