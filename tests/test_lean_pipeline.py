"""
test_lean_pipeline.py — Unit tests for the lean California harmonised dataset and app views.
"""

from pathlib import Path
import pandas as pd
import pytest


def test_daily_series_harmonised_integrity():
    csv_path = Path("data/daily_series_harmonised.csv")
    assert csv_path.exists(), "daily_series_harmonised.csv must exist"

    df = pd.read_csv(csv_path, parse_dates=["date"])
    assert len(df) == 1827, f"Expected exactly 1,827 days (2020-2024), got {len(df)}"
    assert df["date"].min() == pd.Timestamp("2020-01-01")
    assert df["date"].max() == pd.Timestamp("2024-12-31")
    assert df["date"].isna().sum() == 0, "No dates should be missing"

    # Total harmonised hotspots should match reconciled number
    total_harm = df["harmonised_hotspots"].sum()
    assert total_harm == 347174, f"Expected 347,174 harmonised hotspots, got {total_harm}"

    # Peak day must be 2020-09-09 with 10,320 hotspots
    pk_row = df.loc[df["harmonised_hotspots"].idxmax()]
    assert pk_row["date"] == pd.Timestamp("2020-09-09")
    assert pk_row["harmonised_hotspots"] == 10320


def test_detections_integrity():
    csv_path = Path("data/harmonised_detections.csv")
    assert csv_path.exists(), "harmonised_detections.csv must exist"

    df = pd.read_csv(csv_path, parse_dates=["date"])
    assert len(df) == 347174, f"Expected 347,174 rows, got {len(df)}"
    assert set(df["sensor"].unique()) == {"MODIS", "VIIRS"}
    assert (df["frp"] >= 0).all(), "All detections must have FRP >= 0"
    assert (df["latitude"].between(32.5, 42.0)).all()
    assert (df["longitude"].between(-124.5, -114.0)).all()


def test_app_test_execution():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("app.py", default_timeout=30)
    app.run()
    assert not app.exception, f"App crashed on startup: {app.exception}"

    # Verify all 3 calendar views
    radios = [r for r in app.radio if "Daily Matrix" in str(r.options)]
    assert len(radios) >= 1
    cal_radio = radios[0]

    # Test Monthly view
    cal_radio.set_value(cal_radio.options[1]).run()
    assert not app.exception

    # Test Daily Line view
    cal_radio.set_value(cal_radio.options[2]).run()
    assert not app.exception
