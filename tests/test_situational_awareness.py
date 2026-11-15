"""
test_situational_awareness.py — Unit and integration tests for Situational Awareness tab.

Validates:
1. NRT harmonisation filter with synthetic detections (MODIS conf 25/35, VIIRS FRP 3.0/6.5/10.0, VIIRS conf 'l'/'n').
2. API failure handling: missing key, HTTP 429, timeout returns fallback status without raising or modifying historical data.
3. Safe comparison dataframe generation across in-coverage and out-of-coverage bounding boxes.
4. Streamlit AppTest verifies tab renders cleanly on startup with zero API calls.
"""

from datetime import date, timedelta
import pandas as pd
import pytest
import requests

from situational_awareness import (
    fetch_nrt_data,
    harmonize_nrt_data,
    build_comparison_series,
    FALLBACK_BANNER_TEXT,
    PROVENANCE_BANNER_TEXT,
    THRESHOLD_LABEL_TEXT,
    EMPTY_STATE_TEXT,
)


def test_nrt_harmonisation_filter_synthetic():
    """Verify synthetic NRT sample produces exact expected kept/dropped counts."""
    sample_data = {
        "latitude": [37.1, 37.2, 37.3, 37.4, 37.5, 37.6],
        "longitude": [-120.1, -120.2, -120.3, -120.4, -120.5, -120.6],
        "acq_date": ["2026-11-10", "2026-11-10", "2026-11-11", "2026-11-11", "2026-11-12", "2026-11-12"],
        "acq_time": ["944", "945", "45", "215", "1400", "330"],
        "satellite": ["Terra", "Aqua", "N20", "N20", "N21", "SNPP"],
        "instrument": ["MODIS", "MODIS", "VIIRS", "VIIRS", "VIIRS", "VIIRS"],
        "confidence": [25, 35, "l", "n", "h", "n"],
        "frp": [12.0, 15.0, 10.0, 3.0, 6.5, 14.2],
    }
    raw_df = pd.DataFrame(sample_data)

    harmonised_df, stats = harmonize_nrt_data(raw_df)

    # Total: 6 rows.
    # Row 0: MODIS conf 25 -> DROPPED (conf < 30)
    # Row 1: MODIS conf 35 (acq_time '945') -> KEPT -> padded to '0945'
    # Row 2: VIIRS conf 'l', FRP 10.0 -> DROPPED (conf == 'l')
    # Row 3: VIIRS conf 'n', FRP 3.0 -> DROPPED (FRP < 6.5)
    # Row 4: VIIRS conf 'h', FRP 6.5 (acq_time '1400') -> KEPT
    # Row 5: VIIRS conf 'n', FRP 14.2 (acq_time '330') -> KEPT -> padded to '0330'
    assert stats["raw_total"] == 6
    assert stats["harmonised_total"] == 3
    assert stats["modis_kept"] == 1
    assert stats["viirs_kept"] == 2
    assert stats["filtered_sub_threshold"] == 3

    # Verify acq_time padding
    assert list(harmonised_df["acq_time"]) == ["0945", "1400", "0330"]
    assert set(harmonised_df["satellite"]) == {"Aqua", "N21", "SNPP"}


def test_api_failure_handling_and_fallback(monkeypatch):
    """Verify missing key, HTTP 429, and network timeouts trigger safe fallback without raising."""
    bounds = {"min_lat": 32.5, "max_lat": 42.0, "min_lon": -124.5, "max_lon": -114.0}

    # 1. Missing Key
    ok, status, df = fetch_nrt_data(bounds, key="", today_override=date(2026, 11, 14))
    assert ok is False
    assert status == "NO_KEY"
    assert df is None

    # 2. HTTP 429 Rate Limit
    class Mock429Response:
        status_code = 429
        text = "Too Many Requests"

    def mock_get_429(url, **kwargs):
        return Mock429Response()

    monkeypatch.setattr(requests, "get", mock_get_429)
    ok_429, status_429, df_429 = fetch_nrt_data(bounds, key="dummy_key", today_override=date(2026, 11, 14))
    assert ok_429 is False
    assert status_429 == "429"
    assert df_429 is None

    # 3. Network Timeout
    def mock_get_timeout(url, **kwargs):
        raise requests.exceptions.Timeout("Connection timed out")

    monkeypatch.setattr(requests, "get", mock_get_timeout)
    ok_to, status_to, df_to = fetch_nrt_data(bounds, key="dummy_key", today_override=date(2026, 11, 14))
    assert ok_to is False
    assert status_to == "REQUEST_EXCEPTION"
    assert df_to is None


def test_comparison_series_generation():
    """Verify 30-day spine and median alignment under in-coverage and out-of-coverage modes."""
    from app import load_statewide_daily
    daily = load_statewide_daily()
    assert daily is not None

    fixed_today = date(2026, 11, 14)

    # 1. In-coverage with NO NRT data fetched yet (empty state)
    comp_empty = build_comparison_series(
        harmonised_nrt_df=None,
        daily_historical=daily,
        cov_status="FULL_COVERAGE",
        today_override=fixed_today,
    )
    assert len(comp_empty) == 30
    assert comp_empty["nrt_hotspots"].isna().all()
    assert not comp_empty["median_hotspots"].isna().any()

    # 2. In-coverage WITH NRT data
    sample_nrt = pd.DataFrame({
        "date": ["2026-11-10", "2026-11-10", "2026-11-12"],
        "acq_time": ["0944", "1330", "1400"],
        "sensor": ["MODIS", "MODIS", "VIIRS"],
        "satellite": ["Terra", "Aqua", "N20"],
        "frp": [12.0, 15.0, 25.0],
    })
    comp_with_nrt = build_comparison_series(
        harmonised_nrt_df=sample_nrt,
        daily_historical=daily,
        cov_status="FULL_COVERAGE",
        today_override=fixed_today,
    )
    assert len(comp_with_nrt) == 30
    assert comp_with_nrt.loc[comp_with_nrt["date"] == "2026-11-10", "nrt_hotspots"].iloc[0] == 2
    assert comp_with_nrt.loc[comp_with_nrt["date"] == "2026-11-12", "nrt_hotspots"].iloc[0] == 1
    assert comp_with_nrt.loc[comp_with_nrt["date"] == "2026-11-11", "nrt_hotspots"].iloc[0] == 0

    # 3. OUT_OF_COVERAGE (Greece)
    comp_ooc = build_comparison_series(
        harmonised_nrt_df=sample_nrt,
        daily_historical=None,
        cov_status="OUT_OF_COVERAGE",
        today_override=fixed_today,
    )
    assert len(comp_ooc) == 30
    assert comp_ooc["median_hotspots"].isna().all()
    assert comp_ooc.loc[comp_ooc["date"] == "2026-11-10", "nrt_hotspots"].iloc[0] == 2


def test_app_test_situational_awareness_tab_load():
    """Verify that app renders with Situational Awareness tab on load with zero exceptions and empty state."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("app.py", default_timeout=30)
    app.run()
    assert not app.exception, f"App raised exception on load: {app.exception}"

    # Verify 5 tabs
    assert len(app.tabs) == 5

    # Verify provenance banner and empty state are present on startup
    warnings = [w.value for w in app.warning]
    infos = [i.value for i in app.info]

    assert any("PROVISIONAL NRT DATA — SITUATIONAL AWARENESS ONLY" in str(w) for w in warnings)
    assert any("No live data fetched yet — historical median shown" in str(i) for i in infos)

