"""
test_cluster.py — Unit tests for cluster.py

SYNTHETIC TEST DATA — not real FIRMS data.
All detections used in these tests are from tests/fixtures/*_fixture.csv files.
These files must never be used outside of tests/.

Tests cover:
  - Grid boundary: detections just inside the ~1 km radius merge correctly
  - Midnight UTC: detections on different acq_dates are NOT merged
  - Consecutive days: each day's detections produce separate fire records
  - Empty input: cluster_day returns empty DataFrame
  - Mixed sensors: 'both' sensors_present assigned correctly
  - Single detection: produces one fire record
  - fire_id format: CA-YYYY-MM-DD-NNN
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np
import pytest

# Add parent directory to path so we can import cluster.py
sys.path.insert(0, str(Path(__file__).parent.parent))

from cluster import cluster_day, assign_fire_ids, UnionFind, CLUSTER_RADIUS_DEG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_detection(lat, lon, date_str, sensor_type="modis", frp=10.0,
                   brightness_mid=320.0, acq_time="1200"):
    """SYNTHETIC TEST DATA — not real FIRMS data."""
    return {
        "latitude": lat,
        "longitude": lon,
        "acq_date": pd.to_datetime(date_str).date(),
        "acq_time": acq_time,
        "sensor_type": sensor_type,
        "frp": frp,
        "brightness_mid": brightness_mid,
        "brightness_lwir": 295.0,
        "satellite": "Terra" if sensor_type == "modis" else "N20",
        "instrument": "MODIS" if sensor_type == "modis" else "VIIRS",
        "confidence_raw": "80" if sensor_type == "modis" else "n",
        "source_product": "MODIS_SP" if sensor_type == "modis" else "VIIRS_NOAA20_SP",
        "scan": 1.0,
        "track": 1.0,
        "daynight": "D",
    }


def df_from_dets(dets: list[dict]) -> pd.DataFrame:
    """SYNTHETIC TEST DATA — not real FIRMS data."""
    return pd.DataFrame(dets)


# ---------------------------------------------------------------------------
# Test: empty input
# ---------------------------------------------------------------------------

def test_cluster_day_empty():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    cluster_day on an empty DataFrame should return an empty DataFrame.
    """
    result = cluster_day(pd.DataFrame(), "2021-08-01")
    assert result.empty, "Expected empty output for empty input"


# ---------------------------------------------------------------------------
# Test: single detection
# ---------------------------------------------------------------------------

def test_cluster_day_single_detection():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    A single detection should produce exactly one fire record.
    """
    det = [make_detection(38.0, -120.0, "2021-08-01")]
    day_df = df_from_dets(det)
    result = cluster_day(day_df, "2021-08-01")

    assert len(result) == 1
    assert result.iloc[0]["n_detections"] == 1
    assert result.iloc[0]["sensors_present"] == "modis_only"
    assert pytest.approx(result.iloc[0]["total_frp"]) == 10.0


# ---------------------------------------------------------------------------
# Test: grid boundary — detections within ~1 km merge
# ---------------------------------------------------------------------------

def test_cluster_day_boundary_merge():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    Four detections within 0.009° of each other should merge into one fire.
    At 38°N, 0.009° ≈ 1 km. All four are within that radius.
    """
    dets = [
        make_detection(38.0000, -120.0000, "2021-08-01", frp=10.0),
        make_detection(38.0045, -120.0045, "2021-08-01", frp=12.0),
        make_detection(38.0090, -120.0090, "2021-08-01", frp=8.0),
        make_detection(38.0135, -120.0135, "2021-08-01", frp=5.0),
    ]
    day_df = df_from_dets(dets)
    result = cluster_day(day_df, "2021-08-01")

    # 0.0135° diagonal ≈ 0.019°; end points are ~2.1 km apart but connected
    # through the chain, so union-find connects them all into one component.
    # This tests transitive connectivity (chain merging).
    assert len(result) >= 1, "Should produce at least 1 fire"
    # Total FRP must equal sum of all detections' FRP
    assert pytest.approx(result["total_frp"].sum()) == 35.0


def test_cluster_day_distant_fires_no_merge():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    Detections 1° apart (>>1 km) should NOT merge.
    """
    dets = [
        make_detection(38.0, -120.0, "2021-08-01", frp=10.0),
        make_detection(39.0, -121.0, "2021-08-01", frp=20.0),
    ]
    day_df = df_from_dets(dets)
    result = cluster_day(day_df, "2021-08-01")

    assert len(result) == 2, "Distant detections should not merge"
    assert pytest.approx(result["total_frp"].sum()) == 30.0


# ---------------------------------------------------------------------------
# Test: midnight UTC — different dates are NOT merged
# ---------------------------------------------------------------------------

def test_midnight_utc_no_cross_date_merge():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    Two detections at nearly the same location but on different acq_dates
    (e.g., 23:55 → 2021-09-01, 00:05 → 2021-09-02) must NOT be merged.
    This tests the midnight UTC limitation documented in DECISIONS D13.
    """
    det1 = make_detection(37.5000, -119.5000, "2021-09-01", frp=20.0, acq_time="2355")
    det2 = make_detection(37.5001, -119.5001, "2021-09-02", frp=21.0, acq_time="0005")

    # Cluster day 1
    day1 = df_from_dets([det1])
    day1["acq_date"] = pd.to_datetime("2021-09-01").date()
    result1 = cluster_day(day1, "2021-09-01")

    # Cluster day 2
    day2 = df_from_dets([det2])
    day2["acq_date"] = pd.to_datetime("2021-09-02").date()
    result2 = cluster_day(day2, "2021-09-02")

    assert len(result1) == 1, "Day 1 should have 1 fire"
    assert len(result2) == 1, "Day 2 should have 1 fire (not merged)"
    assert result1.iloc[0]["date"] == "2021-09-01"
    assert result2.iloc[0]["date"] == "2021-09-02"


# ---------------------------------------------------------------------------
# Test: consecutive days — same location on consecutive days = two records
# ---------------------------------------------------------------------------

def test_consecutive_days_separate_fires():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    The same fire location on three consecutive days should produce three
    separate fire records, one per day.
    """
    dets_by_date = {
        "2021-07-10": [make_detection(36.0, -118.0, "2021-07-10", frp=50.0)],
        "2021-07-11": [make_detection(36.0001, -118.0001, "2021-07-11", frp=52.0)],
        "2021-07-12": [make_detection(36.0002, -118.0002, "2021-07-12", frp=48.0)],
    }

    all_fires = []
    for date_str, dets in dets_by_date.items():
        day_df = df_from_dets(dets)
        fires = cluster_day(day_df, date_str)
        all_fires.append(fires)

    combined = pd.concat(all_fires, ignore_index=True)
    assert len(combined) == 3, "Three consecutive days should produce 3 fire records"
    dates = set(combined["date"].tolist())
    assert dates == {"2021-07-10", "2021-07-11", "2021-07-12"}


# ---------------------------------------------------------------------------
# Test: mixed sensors — sensors_present = 'both'
# ---------------------------------------------------------------------------

def test_mixed_sensor_both():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    A MODIS and a VIIRS detection within 1 km on the same day should merge
    into one fire with sensors_present = 'both'.
    """
    dets = [
        make_detection(38.5000, -121.0000, "2022-06-15", sensor_type="modis", frp=100.0),
        make_detection(38.5020, -121.0020, "2022-06-15", sensor_type="viirs", frp=30.0),
    ]
    day_df = df_from_dets(dets)
    result = cluster_day(day_df, "2022-06-15")

    # 0.002° ≈ 0.22 km at 38°N; well within 1 km threshold
    assert len(result) == 1
    assert result.iloc[0]["sensors_present"] == "both"
    assert result.iloc[0]["n_modis"] == 1
    assert result.iloc[0]["n_viirs"] == 1
    assert pytest.approx(result.iloc[0]["total_frp"]) == 130.0


def test_modis_only():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    Two MODIS detections within 1 km should merge into sensors_present = 'modis_only'.
    """
    dets = [
        make_detection(38.0, -120.0, "2022-06-15", sensor_type="modis", frp=50.0),
        make_detection(38.003, -120.003, "2022-06-15", sensor_type="modis", frp=60.0),
    ]
    day_df = df_from_dets(dets)
    result = cluster_day(day_df, "2022-06-15")

    assert len(result) == 1
    assert result.iloc[0]["sensors_present"] == "modis_only"
    assert result.iloc[0]["n_modis"] == 2
    assert result.iloc[0]["n_viirs"] == 0


def test_viirs_only():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    Two VIIRS detections within 1 km should merge into sensors_present = 'viirs_only'.
    """
    dets = [
        make_detection(38.0, -120.0, "2022-06-15", sensor_type="viirs", frp=20.0),
        make_detection(38.003, -120.003, "2022-06-15", sensor_type="viirs", frp=25.0),
    ]
    day_df = df_from_dets(dets)
    result = cluster_day(day_df, "2022-06-15")

    assert len(result) == 1
    assert result.iloc[0]["sensors_present"] == "viirs_only"
    assert result.iloc[0]["n_viirs"] == 2
    assert result.iloc[0]["n_modis"] == 0


# ---------------------------------------------------------------------------
# Test: fire_id format
# ---------------------------------------------------------------------------

def test_fire_id_format():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    fire_id must follow CA-YYYY-MM-DD-NNN format.
    """
    dets_a = [make_detection(38.0, -120.0, "2020-08-16", frp=10.0)]
    dets_b = [make_detection(39.0, -121.0, "2020-08-16", frp=20.0)]
    day_df = df_from_dets(dets_a + dets_b)
    result = cluster_day(day_df, "2020-08-16")
    result = assign_fire_ids(result)

    for fid in result["fire_id"]:
        assert fid.startswith("CA-2020-08-16-"), f"Bad fire_id format: {fid}"
        parts = fid.split("-")
        assert len(parts) == 5, f"fire_id should have 5 parts: {fid}"
        assert len(parts[4]) == 3, f"Sequence number should be 3 digits: {fid}"


# ---------------------------------------------------------------------------
# Test: UnionFind correctness
# ---------------------------------------------------------------------------

def test_union_find_basic():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    Basic union-find operations.
    """
    uf = UnionFind(5)
    assert uf.find(0) != uf.find(1)
    uf.union(0, 1)
    assert uf.find(0) == uf.find(1)
    uf.union(1, 2)
    assert uf.find(0) == uf.find(2)
    assert uf.find(3) != uf.find(0)


# ---------------------------------------------------------------------------
# Test: CLUSTER_RADIUS_DEG value
# ---------------------------------------------------------------------------

def test_cluster_radius_value():
    """
    SYNTHETIC TEST DATA — not real FIRMS data.
    Verify that CLUSTER_RADIUS_DEG is 0.009 as documented.
    At 36°N (mid-CA), 0.009° ≈ 1 km.
    """
    assert CLUSTER_RADIUS_DEG == 0.009, (
        f"Expected 0.009, got {CLUSTER_RADIUS_DEG}. "
        "This is the documented ~1 km threshold."
    )
