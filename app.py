"""
app.py — Sekhmet Sync Streamlit Web Application

Harmonized burning activity calendar for California (2020–2024).
NASA International Space Apps Challenge 2026: Harmonization of MODIS and VIIRS Hot Spots.

Reads precomputed files only:
  - data/daily_series_harmonised.csv
  - data/harmonised_detections.csv
  - exports/discontinuity.png (optional historical demo)

No NASA logos. Minimalist White Theme with 3D Globe & 2D Map.
"""

import sys
from pathlib import Path
from datetime import date, datetime
from zoneinfo import ZoneInfo

# Ensure the repository root is in sys.path regardless of execution working directory
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from situational_awareness import (
    fetch_nrt_data,
    harmonize_nrt_data,
    build_comparison_series,
    FALLBACK_BANNER_TEXT,
    PROVENANCE_BANNER_TEXT,
    THRESHOLD_LABEL_TEXT,
    EMPTY_STATE_TEXT,
    CAPTION_TEXT,
)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Sekhmet Sync",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

DAILY_CSV_CORE = APP_DIR / "data" / "daily_series_harmonised.csv"
DETECTIONS_CSV_CORE = APP_DIR / "data" / "harmonised_detections.csv"
DAILY_CSV_EXTENDED = APP_DIR / "data" / "daily_series_harmonised_extended.csv"
DETECTIONS_CSV_EXTENDED = APP_DIR / "data" / "harmonised_detections_extended.csv"
DISCONTINUITY_PNG = APP_DIR / "exports" / "discontinuity.png"

# Default for backward compatibility
DAILY_CSV = DAILY_CSV_CORE
DETECTIONS_CSV = DETECTIONS_CSV_CORE

# ---------------------------------------------------------------------------
# Sub-region bounding boxes (Single source of truth)
# ---------------------------------------------------------------------------

CALIFORNIA_BBOX = {
    "min_lat": 32.5,
    "max_lat": 42.0,
    "min_lon": -124.5,
    "max_lon": -114.0,
}

REGIONS = {
    "California — Statewide": {
        "min_lat": 32.5,
        "max_lat": 42.0,
        "min_lon": -124.5,
        "max_lon": -114.0,
        "desc": "Full California state boundary",
    },
    "California — Northern Forests (Klamath)": {
        "min_lat": 39.5,
        "max_lat": 42.0,
        "min_lon": -124.5,
        "max_lon": -120.0,
        "desc": "Klamath, Shasta-Trinity, Cascades, Modoc",
    },
    "California — Sierra Nevada / Central": {
        "min_lat": 36.5,
        "max_lat": 39.5,
        "min_lon": -121.5,
        "max_lon": -118.0,
        "desc": "Sierra Nevada, Tahoe, Creek Fire & Camp Fire zones",
    },
    "California — Southern Chaparral (LA / San Diego)": {
        "min_lat": 32.5,
        "max_lat": 35.5,
        "min_lon": -120.5,
        "max_lon": -115.5,
        "desc": "Transverse Ranges, LA Basin, San Diego chaparral",
    },
    "Custom Lat / Lon Bounding Box": None,
}

# ---------------------------------------------------------------------------
# Clean White Theme Design System
# ---------------------------------------------------------------------------

THEME = {
    "bg_app": "#FFFFFF",
    "bg_sidebar": "#F9FAFB",
    "bg_card": "#F9FAFB",
    "bg_card_solid": "#FFFFFF",
    "border_card": "#E5E7EB",
    "text_primary": "#111827",
    "text_secondary": "#4B5563",
    "text_muted": "#6B7280",
    "accent_flame": "#DC2626",
    "accent_gold": "#D97706",
    "accent_crimson": "#B91C1C",
    "modis_color": "#2563EB",
    "viirs_color": "#EA580C",
    "median_color": "#059669",
    "plotly_paper": "rgba(0,0,0,0)",
    "plotly_plot": "rgba(0,0,0,0)",
    "plotly_grid": "rgba(0, 0, 0, 0.06)",
    "plotly_text": "#111827",
    "btn_bg": "#111827",
    "btn_hover": "#1F2937",
    "btn_text": "#FFFFFF",
    "colorscale": [
        [0.00, "#FFFFFF"],
        [0.05, "#FEF3C7"],
        [0.30, "#F59E0B"],
        [0.70, "#DC2626"],
        [1.00, "#7F1D1D"],
    ],
}

def get_current_theme():
    return THEME

GLOBAL_CSS = """
<style>
/* Main Viewport */
.stApp {
    background-color: #FFFFFF !important;
    color: #111827 !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #F9FAFB !important;
    border-right: 1px solid #E5E7EB !important;
}

.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 1300px !important;
}

/* Stat Cards: Solid, Grounded, No Jumpy AI Shifts */
[data-testid="stMetric"] {
    background-color: #F9FAFB !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
    padding: 14px 18px !important;
    box-shadow: none !important;
    transform: none !important;
    transition: none !important;
}

[data-testid="stMetric"]:hover {
    background-color: #F9FAFB !important;
    border: 1px solid #E5E7EB !important;
    box-shadow: none !important;
    transform: none !important;
}

[data-testid="stMetricLabel"] {
    color: #4B5563 !important;
    font-size: 0.80rem !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
}

/* On hover: only make text letters bold, no box highlight or movement */
[data-testid="stMetric"]:hover [data-testid="stMetricLabel"] {
    font-weight: 700 !important;
    color: #111827 !important;
}

[data-testid="stMetricValue"] {
    color: #111827 !important;
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    white-space: nowrap !important;
}

[data-testid="stMetric"]:hover [data-testid="stMetricValue"] {
    font-weight: 800 !important;
}

/* Stable Number Inputs: Prevent Jitter When Clicking */
[data-testid="stNumberInput"], [data-testid="stTextInput"], [data-testid="stDateInput"], [data-testid="stSelectbox"] {
    transform: none !important;
    transition: none !important;
}

[data-testid="stNumberInput"] input, [data-testid="stTextInput"] input {
    box-shadow: none !important;
    transform: none !important;
    transition: none !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px !important;
    background: transparent !important;
    border-bottom: 1px solid #E5E7EB !important;
    padding-bottom: 2px !important;
}

.stTabs [data-baseweb="tab"] {
    color: #4B5563 !important;
    border-radius: 6px 6px 0 0 !important;
    font-weight: 500 !important;
    font-size: 0.90rem !important;
    padding: 8px 16px !important;
    border: none !important;
    background: transparent !important;
    transform: none !important;
    transition: none !important;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #111827 !important;
    font-weight: 700 !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #DC2626 !important;
    border-bottom: 2px solid #DC2626 !important;
    font-weight: 700 !important;
}

/* Radio Buttons */
[data-testid="stRadio"] label {
    background-color: #F9FAFB !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 6px !important;
    padding: 6px 12px !important;
    cursor: pointer !important;
    transform: none !important;
    transition: none !important;
}

[data-testid="stRadio"] label:hover {
    font-weight: 700 !important;
}

/* Buttons */
.stButton > button, .stDownloadButton > button {
    background-color: #111827 !important;
    color: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 6px !important;
    padding: 8px 16px !important;
    font-weight: 500 !important;
    box-shadow: none !important;
    transform: none !important;
    transition: none !important;
}

.stButton > button:hover, .stDownloadButton > button:hover {
    background-color: #1F2937 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
}

/* Tables / DataFrames */
[data-testid="stDataFrame"] {
    border-radius: 6px !important;
    border: 1px solid #E5E7EB !important;
}
</style>
"""

# ---------------------------------------------------------------------------
# Cached Data Loaders
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading statewide daily series …")
def load_statewide_daily(is_extended: bool = False):
    csv_path = DAILY_CSV_EXTENDED if is_extended else DAILY_CSV_CORE
    if not csv_path.exists():
        csv_path = DAILY_CSV_CORE
    if not csv_path.exists():
        return None
    df = pd.read_csv(csv_path, parse_dates=["date"])
    for col in ["raw_modis_hotspots", "raw_viirs_hotspots", "harmonised_hotspots",
                "median_hotspots", "anomaly_hotspots", "harmonised_hotspots_satnorm"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

@st.cache_data(show_spinner="Loading harmonised detections dataset …")
def load_detections(is_extended: bool = False):
    csv_path = DETECTIONS_CSV_EXTENDED if is_extended else DETECTIONS_CSV_CORE
    if not csv_path.exists():
        csv_path = DETECTIONS_CSV_CORE
    if not csv_path.exists():
        return None
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["frp"] = pd.to_numeric(df["frp"], errors="coerce").fillna(0)
    return df

@st.cache_data(show_spinner=False)
def get_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

# ---------------------------------------------------------------------------
# Regional Slicing & Daily Aggregation
# ---------------------------------------------------------------------------

def filter_data(daily_statewide, detections, region_choice, custom_bounds, date_range):
    """
    Filter data to selected region and date range.
    Returns:
      (daily_filtered, detections_filtered, coverage_status, active_bounds)
    """
    start_dt, end_dt = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])

    # Determine spatial bounding box
    if region_choice == "Custom Lat / Lon Bounding Box":
        min_lat = custom_bounds["min_lat"]
        max_lat = custom_bounds["max_lat"]
        min_lon = custom_bounds["min_lon"]
        max_lon = custom_bounds["max_lon"]
    else:
        cfg = REGIONS[region_choice]
        min_lat, max_lat = cfg["min_lat"], cfg["max_lat"]
        min_lon, max_lon = cfg["min_lon"], cfg["max_lon"]

    active_bounds = {"min_lat": min_lat, "max_lat": max_lat, "min_lon": min_lon, "max_lon": max_lon}

    # Coverage check against California domain
    c_min_lat, c_max_lat = CALIFORNIA_BBOX["min_lat"], CALIFORNIA_BBOX["max_lat"]
    c_min_lon, c_max_lon = CALIFORNIA_BBOX["min_lon"], CALIFORNIA_BBOX["max_lon"]

    # Completely outside
    if max_lat < c_min_lat or min_lat > c_max_lat or max_lon < c_min_lon or min_lon > c_max_lon:
        return None, None, "OUT_OF_COVERAGE", active_bounds

    # Check for partial overlap
    partially_clipped = False
    clipped_min_lat = max(min_lat, c_min_lat)
    clipped_max_lat = min(max_lat, c_max_lat)
    clipped_min_lon = max(min_lon, c_min_lon)
    clipped_max_lon = min(max_lon, c_max_lon)

    if (clipped_min_lat != min_lat or clipped_max_lat != max_lat or
        clipped_min_lon != min_lon or clipped_max_lon != max_lon):
        partially_clipped = True
        min_lat, max_lat = clipped_min_lat, clipped_max_lat
        min_lon, max_lon = clipped_min_lon, clipped_max_lon

    # Fast path: Statewide full extent
    if region_choice == "California — Statewide":
        d_slice = daily_statewide[(daily_statewide["date"] >= start_dt) & (daily_statewide["date"] <= end_dt)].copy()
        det_slice = detections[(detections["date"] >= start_dt) & (detections["date"] <= end_dt)].copy()
        status = "FULL_COVERAGE" if not partially_clipped else "PARTIAL_OVERLAP"
        return d_slice, det_slice, status, active_bounds

    # Sub-region or custom bbox: Filter detections and aggregate
    det_mask = (
        (detections["latitude"] >= min_lat) & (detections["latitude"] <= max_lat) &
        (detections["longitude"] >= min_lon) & (detections["longitude"] <= max_lon) &
        (detections["date"] >= start_dt) & (detections["date"] <= end_dt)
    )
    det_slice = detections[det_mask].copy()

    # Reconstruct daily series for the sub-region across the date spine
    spine = pd.date_range(start_dt, end_dt, freq="D")
    daily_spine = pd.DataFrame({"date": spine})

    if not det_slice.empty:
        m_counts = det_slice[det_slice["sensor"] == "MODIS"].groupby("date").size().rename("raw_modis_hotspots")
        v_harm_counts = det_slice[det_slice["sensor"] == "VIIRS"].groupby("date").size().rename("viirs_harmonised")

        d_agg = daily_spine.merge(m_counts, on="date", how="left").merge(v_harm_counts, on="date", how="left").fillna(0)
        d_agg["raw_modis_hotspots"] = d_agg["raw_modis_hotspots"].astype(int)
        d_agg["viirs_harmonised"] = d_agg["viirs_harmonised"].astype(int)
        d_agg["harmonised_hotspots"] = d_agg["raw_modis_hotspots"] + d_agg["viirs_harmonised"]

        # Estimate raw VIIRS proportionally based on Statewide 38.3% threshold ratio if raw un-thresholded VIIRS not present
        d_agg["raw_viirs_hotspots"] = (d_agg["viirs_harmonised"] / 0.383).round().astype(int)
    else:
        d_agg = daily_spine.copy()
        d_agg["raw_modis_hotspots"] = 0
        d_agg["raw_viirs_hotspots"] = 0
        d_agg["harmonised_hotspots"] = 0

    # Calculate DOY median for this sub-region
    d_agg["doy"] = d_agg["date"].dt.dayofyear
    median_by_doy = d_agg.groupby("doy")["harmonised_hotspots"].median().rename("median_hotspots")
    d_agg = d_agg.merge(median_by_doy, on="doy", how="left")
    d_agg["anomaly_hotspots"] = d_agg["harmonised_hotspots"] - d_agg["median_hotspots"]
    d_agg = d_agg.drop(columns=["doy"])

    status = "PARTIAL_OVERLAP" if partially_clipped else "FULL_COVERAGE"
    return d_agg, det_slice, status, active_bounds

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def render_header(is_extended: bool = False):
    sub_title = "California (2000–2024 Multi-Decadal Archive)" if is_extended else "California (2020–2024)"
    st.markdown(
        f"""
        <div style="background-color: #F9FAFB;
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                    padding: 16px 20px;
                    margin-bottom: 12px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    flex-wrap: wrap;
                    gap: 12px;">
          <div>
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span style="font-size: 1.45rem; font-weight: 700; color: #111827;">
                🔥 Sekhmet Sync
              </span>
              <span style="border: 1px solid #E5E7EB; color: #4B5563;
                           font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 4px;">
                NASA Space Apps 2026
              </span>
            </div>
            <div style="color: #4B5563; font-size: 0.88rem; margin-top: 4px;">
              Harmonized Satellite Hotspot Activity Calendar • {sub_title}
            </div>
          </div>
          <div>
            <a href="https://sekhmet-sync.streamlit.app/" target="_blank"
               style="color: #111827; text-decoration: none; font-size: 0.82rem; font-weight: 500;
                      border: 1px solid #E5E7EB; padding: 6px 12px; border-radius: 6px;
                      background-color: #FFFFFF;">
              sekhmet-sync.streamlit.app ↗
            </a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div style="background-color: #F9FAFB; border-left: 3px solid #D97706;
                    border-radius: 0 4px 4px 0; padding: 8px 12px; margin-bottom: 14px;
                    color: #4B5563; font-size: 0.82rem;">
          ⚠️ <strong>Harmonization Notice:</strong> Applies an experimental <strong>6.5 MW FRP threshold</strong> to VIIRS, aligning detection counts with pre-drift MODIS baseline sensitivity. See Method & Limitations tab.
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Sidebar Controls
# ---------------------------------------------------------------------------

def render_sidebar():
    st.sidebar.markdown("## Archive Horizon")
    scope_choice = st.sidebar.radio(
        "Temporal Scope",
        options=[
            "🔥 Core Baseline (2020–2024)",
            "🛰️ 25-Yr Climatology (2000–2024)",
        ],
        index=0,
        help="Core Baseline: 5-year frozen benchmark (347k harmonised, 1,827 days). 25-Yr Climatology: Full multi-decadal series (705k harmonised, 8,828 continuous days) across MODIS and VIIRS constellations.",
    )
    is_extended = "2000" in scope_choice

    st.sidebar.markdown("---")
    st.sidebar.markdown("## Region & Coordinates")

    region_choice = st.sidebar.selectbox(
        "Choose Region",
        options=list(REGIONS.keys()),
        index=0,
        help="Select a defined California fire regime or specify custom coordinates.",
    )

    custom_bounds = None
    if region_choice == "Custom Lat / Lon Bounding Box":
        st.sidebar.markdown("**Enter Coordinates (Degrees):**")
        c_lat1, c_lat2 = st.sidebar.columns(2)
        with c_lat1:
            min_lat = st.number_input("Min Lat", value=36.5, min_value=-90.0, max_value=90.0, step=0.5, format="%.2f")
        with c_lat2:
            max_lat = st.number_input("Max Lat", value=39.5, min_value=-90.0, max_value=90.0, step=0.5, format="%.2f")

        c_lon1, c_lon2 = st.sidebar.columns(2)
        with c_lon1:
            min_lon = st.number_input("Min Lon", value=-121.5, min_value=-180.0, max_value=180.0, step=0.5, format="%.2f")
        with c_lon2:
            max_lon = st.number_input("Max Lon", value=-118.0, min_value=-180.0, max_value=180.0, step=0.5, format="%.2f")

        if min_lat >= max_lat:
            st.sidebar.error("Min Lat must be less than Max Lat.")
            max_lat = min_lat + 0.5
        if min_lon >= max_lon:
            st.sidebar.error("Min Lon must be less than Max Lon.")
            max_lon = min_lon + 0.5

        custom_bounds = {"min_lat": min_lat, "max_lat": max_lat, "min_lon": min_lon, "max_lon": max_lon}
    else:
        desc = REGIONS[region_choice]["desc"]
        st.sidebar.caption(f"ℹ️ {desc}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Date Range")

    min_year = 2000 if is_extended else 2020
    max_year = 2024
    start_date = st.sidebar.date_input(
        "Start Date",
        value=date(min_year, 1, 1),
        min_value=date(min_year, 1, 1),
        max_value=date(max_year, 12, 31),
    )
    end_date = st.sidebar.date_input(
        "End Date",
        value=date(max_year, 12, 31),
        min_value=date(min_year, 1, 1),
        max_value=date(max_year, 12, 31),
    )

    if start_date > end_date:
        st.sidebar.error("Start Date must be on or before End Date.")
        end_date = start_date

    st.sidebar.markdown("---")
    if is_extended:
        st.sidebar.markdown(
            "**Sensors in Archive (2000–2024):**\n"
            "- MODIS Terra (from 2000-11)\n"
            "- MODIS Aqua (from 2002-07)\n"
            "- VIIRS Suomi-NPP (from 2012-01)\n"
            "- VIIRS NOAA-20 (from 2018-01)\n"
            "- VIIRS NOAA-21 (from 2023-03)\n\n"
            "**Harmonization Threshold:**\n"
            "`VIIRS FRP >= 6.5 MW` + Constellation Normalisation (`satnorm`)"
        )
    else:
        st.sidebar.markdown(
            "**Sensors in Archive:**\n"
            "- MODIS C6.1 (Terra + Aqua)\n"
            "- VIIRS NOAA-20 (375 m)\n"
            "- VIIRS NOAA-21 (from 2023-03-01)\n\n"
            "**Harmonization Threshold:**\n"
            "`VIIRS FRP >= 6.5 MW` (experimental)"
        )

    return region_choice, custom_bounds, (start_date, end_date), is_extended

# ---------------------------------------------------------------------------
# Stat Cards
# ---------------------------------------------------------------------------

def render_stat_cards(daily_f):
    """Render 4 core KPI cards."""
    total_raw = int(daily_f["raw_modis_hotspots"].sum() + daily_f["raw_viirs_hotspots"].sum())
    total_harm = int(daily_f["harmonised_hotspots"].sum())

    if total_raw > 0:
        pct_filtered = (total_raw - total_harm) / total_raw * 100
        pct_filtered_str = f"{pct_filtered:.1f}%"
    else:
        pct_filtered_str = "0.0%"

    if daily_f.empty or total_harm == 0:
        peak_day_str = "N/A"
        peak_count = 0
    else:
        peak_idx = daily_f["harmonised_hotspots"].idxmax()
        peak_day_str = daily_f.loc[peak_idx, "date"].strftime("%Y-%m-%d")
        peak_count = int(daily_f.loc[peak_idx, "harmonised_hotspots"])

    c1, c2, c3, c4 = st.columns([1.1, 1.1, 1.1, 1.3])
    c1.metric("Raw Hotspots", f"{total_raw:,}", help="Unfiltered satellite hotspot detections")
    c2.metric("Harmonised Hotspots", f"{total_harm:,}", help="MODIS as-is + VIIRS with FRP >= 6.5 MW")
    c3.metric("Filtered Sub-Threshold", pct_filtered_str, help="Faint VIIRS detections below MODIS sensitivity limit")
    c4.metric("Peak Day", peak_day_str, f"{peak_count:,} hotspots", delta_color="off")

# ---------------------------------------------------------------------------
# Calendar Views (Daily Matrix 5x366, Monthly Heatmap 5x12, Daily Line)
# ---------------------------------------------------------------------------

def get_plotly_config(filename="chart"):
    clean_name = filename.replace(" ", "_").replace("—", "").replace("/", "_").replace("(", "").replace(")", "").strip("_")
    return {
        "displayModeBar": True,
        "displaylogo": False,
        "toImageButtonOptions": {
            "format": "png",
            "filename": f"sekhmet_sync_{clean_name}",
            "height": 600,
            "width": 1100,
            "scale": 2,
        },
    }

def render_daily_matrix(daily_f, region_name):
    """Render Daily Burning Activity Calendar Matrix."""
    d = daily_f.copy()
    d["year"] = d["date"].dt.year
    d["doy"] = d["date"].dt.dayofyear
    years = sorted(d["year"].unique()) if not d.empty else [2020, 2021, 2022, 2023, 2024]
    n_years = len(years)

    matrix = np.full((n_years, 366), np.nan)
    for i, yr in enumerate(years):
        sub = d[d["year"] == yr]
        for _, row in sub.iterrows():
            doy_idx = int(row["doy"]) - 1
            if 0 <= doy_idx < 366:
                matrix[i, doy_idx] = float(row["harmonised_hotspots"])

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=list(range(1, 367)),
        y=[str(yr) for yr in years],
        colorscale=THEME["colorscale"],
        colorbar=dict(
            title=dict(text="Harmonised Hotspots", font=dict(color=THEME["plotly_text"], size=11)),
            tickfont=dict(color=THEME["plotly_text"], size=10),
            outlinecolor=THEME["border_card"],
            outlinewidth=1,
        ),
        xgap=0.5,
        ygap=1,
        zmin=0,
        hovertemplate="Year: %{y}<br>DOY: %{x}<br>Harmonised Hotspots: %{z:.0f}<extra></extra>",
    ))

    month_starts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for ms in month_starts:
        fig.add_vline(x=ms - 0.5, line_width=0.5, line_color=THEME["border_card"], opacity=0.8)

    if not d.empty and d["harmonised_hotspots"].sum() > 0:
        pk_row = d.loc[d["harmonised_hotspots"].idxmax()]
        pk_doy = int(pk_row["doy"])
        pk_year = str(pk_row["year"])
        pk_count = int(pk_row["harmonised_hotspots"])

        fig.add_annotation(
            x=pk_doy,
            y=pk_year,
            text=f"★ Peak: {pk_count:,} hotspots",
            showarrow=True,
            arrowhead=2,
            arrowcolor=THEME["accent_flame"],
            font=dict(color=THEME["accent_flame"], size=10),
            bgcolor=THEME["bg_card_solid"],
            bordercolor=THEME["border_card"],
            borderwidth=1,
        )

    calc_height = max(290, min(750, n_years * 20 + 190))
    fig.update_layout(
        title=dict(
            text=f"Burning Activity Calendar (Daily {n_years}×366) — {region_name}",
            font=dict(color=THEME["plotly_text"], size=13),
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=[ms + 10 for ms in month_starts],
            ticktext=month_labels,
            tickfont=dict(color=THEME["plotly_text"], size=9),
            showgrid=False,
        ),
        yaxis=dict(tickfont=dict(color=THEME["plotly_text"]), autorange="reversed"),
        paper_bgcolor=THEME["plotly_paper"],
        plot_bgcolor=THEME["plotly_plot"],
        height=calc_height,
        margin=dict(l=50, r=60, t=45, b=30),
    )

    st.plotly_chart(fig, use_container_width=True, config=get_plotly_config(f"daily_calendar_{region_name}"))
    min_yr = min(years)
    max_yr = max(years)
    yr_str = f"{min_yr}–{max_yr}" if min_yr != max_yr else f"{min_yr}"
    st.caption(
        f"Rows = years ({yr_str}). Columns = day-of-year 1–366. "
        "Base cells = zero hotspots detected. Grey cells (DOY 366 in non-leap years) = no data."
    )

def render_monthly_heatmap(daily_f, region_name):
    """Render Monthly Burning Activity Heatmap."""
    d = daily_f.copy()
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month
    years = sorted(d["year"].unique()) if not d.empty else [2020, 2021, 2022, 2023, 2024]
    n_years = len(years)
    months = list(range(1, 13))
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    monthly_agg = d.groupby(["year", "month"])["harmonised_hotspots"].sum().reset_index()
    matrix = np.zeros((n_years, 12))
    text_matrix = []

    for i, yr in enumerate(years):
        row_text = []
        for j, mo in enumerate(months):
            val = monthly_agg.loc[(monthly_agg["year"] == yr) & (monthly_agg["month"] == mo), "harmonised_hotspots"]
            count = float(val.iloc[0]) if not val.empty else 0.0
            matrix[i, j] = count
            if count >= 1000:
                row_text.append(f"{count/1000:.1f}k")
            elif count > 0:
                row_text.append(f"{int(count):,}")
            else:
                row_text.append("0")
        text_matrix.append(row_text)

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=month_labels,
        y=[str(yr) for yr in years],
        text=text_matrix,
        texttemplate="%{text}",
        textfont=dict(size=11, color=THEME["plotly_text"]),
        colorscale=THEME["colorscale"],
        colorbar=dict(
            title=dict(text="Hotspots / Mo", font=dict(color=THEME["plotly_text"], size=11)),
            tickfont=dict(color=THEME["plotly_text"], size=10),
            outlinecolor=THEME["border_card"],
            outlinewidth=1,
        ),
        xgap=2,
        ygap=2,
        zmin=0,
        hovertemplate="Year: %{y}<br>Month: %{x}<br>Harmonised Hotspots: %{z:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=f"Monthly Burning Activity Calendar (5×12) — {region_name}",
            font=dict(color=THEME["plotly_text"], size=13),
        ),
        xaxis=dict(title="Month", tickfont=dict(color=THEME["plotly_text"]), gridcolor=THEME["plotly_grid"]),
        yaxis=dict(title="Year", tickfont=dict(color=THEME["plotly_text"]), autorange="reversed"),
        paper_bgcolor=THEME["plotly_paper"],
        plot_bgcolor=THEME["plotly_plot"],
        height=310,
        margin=dict(l=50, r=60, t=45, b=40),
    )

    st.plotly_chart(fig, use_container_width=True, config=get_plotly_config(f"monthly_heatmap_{region_name}"))
    st.caption("Rows = years 2020–2024. Columns = months Jan–Dec. Cell values display total monthly harmonised hotspots.")

def render_daily_line(daily_f, region_name):
    """Daily hotspots vs multi-year median line chart."""
    d = daily_f.copy()
    fig = go.Figure()

    # Above median fill
    fig.add_trace(go.Scatter(
        x=pd.concat([d["date"], d["date"].iloc[::-1]]),
        y=pd.concat([
            d["harmonised_hotspots"].where(d["anomaly_hotspots"] > 0, d["median_hotspots"]),
            d["median_hotspots"].iloc[::-1],
        ]),
        fill="toself",
        fillcolor="rgba(220, 38, 38, 0.15)",
        line=dict(color="rgba(255,255,255,0)"),
        name="Above median",
    ))

    # Below median fill
    fig.add_trace(go.Scatter(
        x=pd.concat([d["date"], d["date"].iloc[::-1]]),
        y=pd.concat([
            d["harmonised_hotspots"].where(d["anomaly_hotspots"] < 0, d["median_hotspots"]),
            d["median_hotspots"].iloc[::-1],
        ]),
        fill="toself",
        fillcolor="rgba(37, 99, 235, 0.10)",
        line=dict(color="rgba(255,255,255,0)"),
        name="Below median",
    ))

    # 5-Year Median line
    fig.add_trace(go.Scatter(
        x=d["date"],
        y=d["median_hotspots"],
        name="5-Yr Median Baseline",
        line=dict(color=THEME["median_color"], width=2.0, dash="dash"),
    ))

    # Observed daily hotspots
    fig.add_trace(go.Scatter(
        x=d["date"],
        y=d["harmonised_hotspots"],
        name="Harmonised Hotspots",
        line=dict(color=THEME["accent_flame"], width=1.6),
    ))

    # Satellite-Normalized trace (satnorm) if present in dataset
    if "harmonised_hotspots_satnorm" in d.columns and d["harmonised_hotspots_satnorm"].sum() > 0:
        fig.add_trace(go.Scatter(
            x=d["date"],
            y=d["harmonised_hotspots_satnorm"],
            name="Satellite-Normalized (satnorm)",
            line=dict(color=THEME["accent_gold"], width=1.4, dash="dot"),
            visible="legendonly",
        ))

    # Top 5 anomaly days
    top5 = d.nlargest(5, "anomaly_hotspots")
    fig.add_trace(go.Scatter(
        x=top5["date"],
        y=top5["harmonised_hotspots"],
        mode="markers",
        marker=dict(color=THEME["accent_crimson"], size=9, symbol="star"),
        name="Top 5 Anomaly Peaks",
        hovertemplate="%{x}<br>Hotspots: %{y:,}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=f"Daily Burning Activity vs. Reference Median — {region_name}",
            font=dict(color=THEME["plotly_text"], size=13),
        ),
        xaxis=dict(title="Date", tickfont=dict(color=THEME["plotly_text"]), gridcolor=THEME["plotly_grid"]),
        yaxis=dict(title="Daily Hotspots", tickfont=dict(color=THEME["plotly_text"]), gridcolor=THEME["plotly_grid"]),
        height=360,
        paper_bgcolor=THEME["plotly_paper"],
        plot_bgcolor=THEME["plotly_plot"],
        legend=dict(
            x=0.99,
            y=0.99,
            xanchor="right",
            yanchor="top",
            font=dict(color=THEME["plotly_text"]),
            bgcolor=THEME["bg_card_solid"],
            bordercolor=THEME["border_card"],
            borderwidth=1,
        ),
        margin=dict(l=50, r=40, t=45, b=45),
    )
    st.plotly_chart(fig, use_container_width=True, config=get_plotly_config(f"anomaly_line_{region_name}"))

def render_calendar(daily_f, region_name):
    """Burning Activity Calendar container with clean view switcher."""
    years = sorted(daily_f["date"].dt.year.unique()) if not daily_f.empty else [2020, 2021, 2022, 2023, 2024]
    n_years = len(years)
    cal_mode = st.radio(
        "Calendar View",
        [
            f"📅 Daily Matrix ({n_years}×366)",
            f"🗓️ Monthly Heatmap ({n_years}×12)",
            "📈 Daily Line (Hotspots vs. Median)",
        ],
        horizontal=True,
    )

    if cal_mode.startswith("📅 Daily Matrix"):
        render_daily_matrix(daily_f, region_name)
    elif cal_mode.startswith("🗓️ Monthly Heatmap"):
        render_monthly_heatmap(daily_f, region_name)
    else:
        render_daily_line(daily_f, region_name)

# ---------------------------------------------------------------------------
# Spatial Footprint Tab (Clean, Uncomplicated 2D Map & 3D Globe)
# ---------------------------------------------------------------------------

def render_spatial_footprint(det_f, region_name, active_bounds):
    """
    Render clean spatial map with simple toggle:
    - 2D Interactive Map (Carto Positron)
    - 3D Interactive Globe (Click & drag to spin Earth freely)
    """
    if det_f.empty:
        st.info("No hotspots detected for the selected search filters.")
        return

    total_pts = len(det_f)
    sampled = False
    if total_pts > 5000:
        d_map = det_f.sample(5000, random_state=42).copy()
        sampled = True
    else:
        d_map = det_f.copy()

    # Simple, clear mode selector
    c_mode, c_info = st.columns([2, 3])
    with c_mode:
        map_mode = st.radio(
            "Map Perspective",
            ["🗺️ 2D Map", "🌍 3D Globe"],
            horizontal=True,
        )
    with c_info:
        if "3D" in map_mode:
            st.caption("💡 **Tip:** Click and drag the globe with your mouse to freely spin the Earth in 3D.")
        else:
            st.caption("💡 **Tip:** Scroll to zoom in/out, and drag to pan across California.")

    center_lat = (active_bounds["min_lat"] + active_bounds["max_lat"]) / 2.0
    center_lon = (active_bounds["min_lon"] + active_bounds["max_lon"]) / 2.0

    fig = go.Figure()

    for sensor, color, name in [
        ("MODIS", THEME["modis_color"], "MODIS (Reference)"),
        ("VIIRS", THEME["accent_flame"], "VIIRS (FRP ≥ 6.5 MW)"),
    ]:
        sub = d_map[d_map["sensor"] == sensor]
        if sub.empty:
            continue

        sub_sizes = np.clip(np.log1p(sub["frp"].fillna(1)) * 1.5, 3.0, 9.0)

        hover_text = [
            f"<b>{row.date.strftime('%Y-%m-%d') if hasattr(row.date, 'strftime') else row.date}</b><br>"
            f"Sensor: {row.sensor} ({row.satellite})<br>"
            f"FRP: {row.frp:.1f} MW<br>"
            f"Lat: {row.latitude:.3f}, Lon: {row.longitude:.3f}"
            for row in sub.itertuples()
        ]

        if "3D" in map_mode:
            # 3D Orthographic Globe
            fig.add_trace(go.Scattergeo(
                lat=sub["latitude"],
                lon=sub["longitude"],
                mode="markers",
                marker=dict(size=sub_sizes, color=color, opacity=0.75),
                name=f"{name} ({len(sub):,} pts)",
                text=hover_text,
                hoverinfo="text",
            ))
        else:
            # 2D Mapbox
            fig.add_trace(go.Scattermapbox(
                lat=sub["latitude"],
                lon=sub["longitude"],
                mode="markers",
                marker=dict(size=sub_sizes, color=color, opacity=0.70),
                name=f"{name} ({len(sub):,} pts)",
                text=hover_text,
                hoverinfo="text",
            ))

    if "3D" in map_mode:
        fig.update_geos(
            projection_type="orthographic",
            projection_rotation=dict(lon=center_lon, lat=center_lat, roll=0),
            showocean=True,
            oceancolor="#EFF6FF",
            showland=True,
            landcolor="#F3F4F6",
            showlakes=True,
            lakecolor="#EFF6FF",
            showcountries=True,
            countrycolor="#CBD5E1",
            showsubunits=True,
            subunitcolor="#E2E8F0",
            showcoastlines=True,
            coastlinecolor="#94A3B8",
            coastlinewidth=1,
            resolution=110,
            bgcolor="rgba(0,0,0,0)",
        )
        fig.update_layout(
            title=dict(text=f"🌍 3D Earth Globe View — {region_name}", font=dict(color=THEME["plotly_text"], size=13)),
            height=540,
            paper_bgcolor=THEME["plotly_paper"],
            plot_bgcolor=THEME["plotly_plot"],
            margin=dict(l=0, r=0, t=35, b=0),
            legend=dict(
                x=0.01,
                y=0.99,
                bgcolor=THEME["bg_card_solid"],
                bordercolor=THEME["border_card"],
                borderwidth=1,
                font=dict(color=THEME["plotly_text"]),
            ),
        )
    else:
        fig.update_layout(
            mapbox=dict(
                style="carto-positron",
                center=dict(lat=center_lat, lon=center_lon),
                zoom=5.6,
            ),
            title=dict(text=f"🗺️ 2D Interactive Map — {region_name}", font=dict(color=THEME["plotly_text"], size=13)),
            height=540,
            margin=dict(l=0, r=0, t=35, b=0),
            paper_bgcolor=THEME["plotly_paper"],
            legend=dict(
                x=0.01,
                y=0.99,
                bgcolor=THEME["bg_card_solid"],
                bordercolor=THEME["border_card"],
                borderwidth=1,
                font=dict(color=THEME["plotly_text"]),
            ),
        )

    st.plotly_chart(fig, use_container_width=True, config=get_plotly_config(f"spatial_footprint_{region_name}"))

    if sampled:
        st.caption(
            f"ℹ️ Showing **5,000 sampled hotspots** (out of **{total_pts:,}** total in selected region/dates) "
            "for clean, high-performance rendering. Points: Blue = MODIS, Red = VIIRS (≥ 6.5 MW)."
        )
    else:
        st.caption(
            f"ℹ️ Showing **all {total_pts:,} hotspots** in selected region and date range. "
            "Points: Blue = MODIS, Red = VIIRS (≥ 6.5 MW)."
        )

# ---------------------------------------------------------------------------
# Critical Periods & Seasonality Analysis
# ---------------------------------------------------------------------------

def calculate_season_window(daily_f):
    """Dynamically compute the core burning season window (10th to 90th percentile of DOY distribution)."""
    d = daily_f.copy()
    if d.empty or d["harmonised_hotspots"].sum() == 0:
        return None
    d["doy"] = d["date"].dt.dayofyear
    doy_totals = d.groupby("doy")["harmonised_hotspots"].sum()
    cumsum = doy_totals.cumsum()
    total = cumsum.iloc[-1]
    if total == 0:
        return None
    p10_doy = int(cumsum[cumsum >= 0.10 * total].index[0])
    p90_doy = int(cumsum[cumsum >= 0.90 * total].index[0])
    d10 = pd.Timestamp("2021-01-01") + pd.Timedelta(days=p10_doy - 1)
    d90 = pd.Timestamp("2021-01-01") + pd.Timedelta(days=p90_doy - 1)
    duration = p90_doy - p10_doy + 1
    return {
        "p10_doy": p10_doy,
        "p90_doy": p90_doy,
        "start_str": d10.strftime("%b %d"),
        "end_str": d90.strftime("%b %d"),
        "duration": duration,
    }

def calculate_critical_streaks(daily_f, multiplier=3.0, min_streak_len=3):
    """Dynamically identify sustained critical periods where daily burning exceeds multiplier * historical median."""
    d = daily_f.copy().sort_values("date").reset_index(drop=True)
    if d.empty or d["harmonised_hotspots"].sum() == 0:
        return pd.DataFrame()
    cond = (d["harmonised_hotspots"] > multiplier * d["median_hotspots"]) & (d["harmonised_hotspots"] >= 10)
    d["streak_id"] = (~cond).cumsum()
    streaks = d[cond].groupby("streak_id").agg(
        start_date=("date", "min"),
        end_date=("date", "max"),
        duration_days=("date", "count"),
        peak_daily_hotspots=("harmonised_hotspots", "max"),
        total_hotspots=("harmonised_hotspots", "sum"),
    ).reset_index(drop=True)
    if streaks.empty:
        return pd.DataFrame()
    streaks = streaks[streaks["duration_days"] >= min_streak_len].sort_values("duration_days", ascending=False)
    return streaks

def render_anomaly(daily_f, region_name):
    """Daily hotspots vs multi-year median, season window, critical streaks, and anomaly table."""
    d = daily_f.copy()

    render_daily_line(d, region_name)

    st.markdown("---")
    st.markdown("### 🚨 Critical Periods & Seasonality Analysis")
    st.caption("Empirical season boundaries and sustained outbreak streaks calculated dynamically from your active filter.")

    sw = calculate_season_window(d)
    if sw:
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("Core Fire Season Window", f"{sw['start_str']} – {sw['end_str']}", help="10th to 90th percentile of cumulative burning")
        sc2.metric("Core Season Duration", f"{sw['duration']} days", help="Length of the core 80% burning period")
        sc3.metric("Window Concentration", "80% of Hotspots", help="Percentage of burning contained within this seasonal window")

    streaks = calculate_critical_streaks(d, multiplier=3.0, min_streak_len=3)
    if not streaks.empty:
        st.markdown("**Sustained Critical Outbreak Streaks (≥ 3 consecutive days at > 3× historical median):**")
        disp_streaks = streaks.copy()
        disp_streaks["start_date"] = disp_streaks["start_date"].dt.strftime("%Y-%m-%d")
        disp_streaks["end_date"] = disp_streaks["end_date"].dt.strftime("%Y-%m-%d")
        disp_streaks["peak_daily_hotspots"] = disp_streaks["peak_daily_hotspots"].apply(lambda v: f"{int(v):,}")
        disp_streaks["total_hotspots"] = disp_streaks["total_hotspots"].apply(lambda v: f"{int(v):,}")
        disp_streaks.columns = ["Start Date", "End Date", "Duration (Days)", "Peak Daily Hotspots", "Total Hotspots in Streak"]
        st.dataframe(disp_streaks, use_container_width=True, hide_index=True)
    else:
        st.info("No sustained multi-day outbreak streaks (> 3× median for ≥ 3 consecutive days) detected in this selection.")

    st.markdown("---")
    top10 = d.nlargest(10, "anomaly_hotspots")[["date", "raw_modis_hotspots", "raw_viirs_hotspots", "harmonised_hotspots", "median_hotspots", "anomaly_hotspots"]].copy()
    top10["date"] = top10["date"].dt.strftime("%Y-%m-%d")
    top10.columns = ["Date", "MODIS (Raw)", "VIIRS (Raw)", "Harmonised", "Median", "Anomaly"]
    st.markdown("**Top 10 Peak Anomaly Days:**")
    st.dataframe(top10, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Situational Awareness Tab (Provisional NRT & Historical Comparison)
# ---------------------------------------------------------------------------

def render_situational_awareness(daily_f, cov_status, active_bounds, region_choice):
    """Provisional NRT & Historical Comparison tab."""
    st.warning(PROVENANCE_BANNER_TEXT)

    if cov_status == "OUT_OF_COVERAGE":
        st.warning("Selected area is outside the California data archive — no coverage.")
        st.caption("Historical median comparison is unavailable for coordinates outside California.")

    state_key = f"nrt_data_{region_choice}"
    fallback_key = f"nrt_fallback_{region_choice}"

    c_btn, c_info = st.columns([1.5, 3.5])
    with c_btn:
        fetch_clicked = st.button("🔄 Fetch Live FIRMS NRT", use_container_width=True)

    with c_info:
        st.caption(
            f"Active Region: **{region_choice}** | Lat [{active_bounds['min_lat']:.2f}, {active_bounds['max_lat']:.2f}], "
            f"Lon [{active_bounds['min_lon']:.2f}, {active_bounds['max_lon']:.2f}]"
        )

    if fetch_clicked:
        with st.spinner("Connecting to NASA FIRMS Area API (last 30 days) …"):
            success, status, raw_nrt_df = fetch_nrt_data(active_bounds, timeout=15)
            if not success:
                st.session_state[fallback_key] = True
                st.session_state[state_key] = None
            else:
                st.session_state[fallback_key] = False
                harm_nrt, stats = harmonize_nrt_data(raw_nrt_df)
                ts_pt = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
                st.session_state[state_key] = {
                    "harmonised_df": harm_nrt,
                    "raw_df": raw_nrt_df,
                    "stats": stats,
                    "timestamp": ts_pt,
                    "bounds": active_bounds,
                }

    if st.session_state.get(fallback_key, False):
        st.info(FALLBACK_BANNER_TEXT)

    nrt_session = st.session_state.get(state_key, None)
    harmonised_nrt_df = nrt_session["harmonised_df"] if nrt_session else None

    comp_df = build_comparison_series(
        harmonised_nrt_df=harmonised_nrt_df,
        daily_historical=daily_f if cov_status != "OUT_OF_COVERAGE" else None,
        cov_status=cov_status,
    )

    fig = go.Figure()

    if cov_status != "OUT_OF_COVERAGE" and "median_hotspots" in comp_df.columns and comp_df["median_hotspots"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=comp_df["date"],
                y=comp_df["median_hotspots"],
                name="Historical median — SP 2020–2024, same day-of-year",
                mode="lines",
                line=dict(color=THEME["modis_color"], width=2.0, dash="dash"),
            )
        )

    has_nrt = harmonised_nrt_df is not None and not harmonised_nrt_df.empty
    if has_nrt:
        fig.add_trace(
            go.Scatter(
                x=comp_df["date"],
                y=comp_df["nrt_hotspots"],
                name="Provisional NRT — daily count (this fetch)",
                mode="lines+markers",
                line=dict(color=THEME["accent_crimson"], width=2.0),
                marker=dict(size=5, color=THEME["accent_crimson"]),
            )
        )

    clean_region = region_choice.replace(" ", "_").replace("—", "").replace("/", "_").replace("(", "").replace(")", "").strip("_")
    fig.update_layout(
        title=dict(
            text=f"Provisional NRT Observations vs. Historical Median (Last 30 Days) — {region_choice}",
            font=dict(color=THEME["plotly_text"], size=13),
        ),
        xaxis=dict(title="Observation Date", gridcolor=THEME["plotly_grid"], tickfont=dict(color=THEME["plotly_text"], size=10)),
        yaxis=dict(title="Daily Hotspots Count", gridcolor=THEME["plotly_grid"], tickfont=dict(color=THEME["plotly_text"], size=10)),
        paper_bgcolor=THEME["plotly_paper"],
        plot_bgcolor=THEME["plotly_plot"],
        height=370,
        legend=dict(
            x=0.99,
            y=0.99,
            xanchor="right",
            yanchor="top",
            font=dict(color=THEME["plotly_text"]),
            bgcolor=THEME["bg_card_solid"],
            bordercolor=THEME["border_card"],
            borderwidth=1,
        ),
        margin=dict(l=50, r=40, t=50, b=50),
    )

    st.plotly_chart(fig, use_container_width=True, config=get_plotly_config(f"situational_awareness_{clean_region}"))
    st.caption(CAPTION_TEXT)

    if not has_nrt:
        st.info(EMPTY_STATE_TEXT)
    else:
        stats = nrt_session["stats"]
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Raw NRT Fetched", f"{stats['raw_total']:,}")
        sc2.metric("Harmonised NRT", f"{stats['harmonised_total']:,}")
        sc3.metric("Filtered Sub-Threshold", f"{stats['filtered_sub_threshold']:,}")
        sc4.metric("Day Range", "30 Days (Rolling)")

        st.caption(
            f"**Query Details:** Sources: `MODIS_NRT, VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT` | "
            f"Fetch Timestamp: **{nrt_session['timestamp']}** | "
            f"Bounding Box: Lat [{active_bounds['min_lat']:.2f}, {active_bounds['max_lat']:.2f}], "
            f"Lon [{active_bounds['min_lon']:.2f}, {active_bounds['max_lon']:.2f}]"
        )
        st.caption(f"🔬 *{THRESHOLD_LABEL_TEXT}*")

        nrt_export = harmonised_nrt_df.copy()
        nrt_export["provenance"] = "NRT provisional"
        today_str = date.today().isoformat()
        st.download_button(
            label="📥 Download Provisional NRT Detections (CSV)",
            data=get_csv_bytes(nrt_export),
            file_name=f"nrt_provisional_{today_str}.csv",
            mime="text/csv",
            help="Provisional NRT detections for this fetch. Stored separately from SP archive.",
        )

# ---------------------------------------------------------------------------
# Why Harmonisation & Downloads Tab
# ---------------------------------------------------------------------------

def render_why_harmonisation(daily_f):
    st.markdown(
        """
        ### Why Harmonisation Matters
        MODIS (1,000 m pixel resolution) and VIIRS (375 m pixel resolution) are fundamentally different instruments.
        Because VIIRS has higher spatial resolution, it detects lower-intensity and smaller fire hotspots that fall below
        MODIS detection limits.

        Without harmonisation, transitioning between sensors causes an apparent jump in hotspot activity that is a 
        sensor artefact, not a real physical fire increase.

        **Sekhmet Sync** applies an empirical **6.5 MW FRP threshold** to VIIRS observations:
        - Faint VIIRS hotspots with FRP < 6.5 MW are filtered out.
        - The remaining VIIRS hotspots match the observation scale of pre-drift MODIS ($r=0.9974$).
        - Result: A consistent daily time series where emergency managers can track fire regimes across sensor eras.
        """
    )

    if DISCONTINUITY_PNG.exists():
        st.image(str(DISCONTINUITY_PNG), use_column_width=True)
        st.caption("Historical Demonstration: The 2011–2013 S-NPP launch discontinuity.")

    d = daily_f.copy()
    d["year"] = d["date"].dt.year
    agg = d.groupby("year").agg({
        "raw_modis_hotspots": "sum",
        "raw_viirs_hotspots": "sum",
        "harmonised_hotspots": "sum",
    }).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=agg["year"].astype(str), y=agg["raw_modis_hotspots"], name="MODIS (Raw)", marker_color=THEME["modis_color"]))
    fig.add_trace(go.Bar(x=agg["year"].astype(str), y=agg["raw_viirs_hotspots"], name="VIIRS (Raw)", marker_color=THEME["viirs_color"]))
    fig.add_trace(go.Bar(x=agg["year"].astype(str), y=agg["harmonised_hotspots"], name="Harmonised (Thresholded)", marker_color=THEME["accent_flame"]))

    fig.update_layout(
        barmode="group",
        title=dict(text="Raw vs. Harmonised Annual Hotspot Counts (Selected Area)", font=dict(color=THEME["plotly_text"], size=13)),
        xaxis=dict(title="Year", tickfont=dict(color=THEME["plotly_text"]), gridcolor=THEME["plotly_grid"]),
        yaxis=dict(title="Total Hotspots", tickfont=dict(color=THEME["plotly_text"]), gridcolor=THEME["plotly_grid"]),
        height=340,
        paper_bgcolor=THEME["plotly_paper"],
        plot_bgcolor=THEME["plotly_plot"],
        legend=dict(
            x=0.99,
            y=0.99,
            xanchor="right",
            yanchor="top",
            font=dict(color=THEME["plotly_text"]),
            bgcolor=THEME["bg_card_solid"],
            bordercolor=THEME["border_card"],
            borderwidth=1,
        ),
        margin=dict(l=50, r=40, t=50, b=50),
    )
    st.plotly_chart(fig, use_container_width=True, config=get_plotly_config("annual_sensor_comparison"))

def render_downloads(daily_f, det_f, region_name, date_range):
    st.markdown("### 📥 Download Sliced Data")
    st.caption(f"Exports are dynamically sliced to your chosen region (**{region_name}**) and dates (**{date_range[0]} to {date_range[1]}**).")

    c1, c2 = st.columns(2)
    daily_export = daily_f.copy()
    daily_export["date"] = daily_export["date"].dt.strftime("%Y-%m-%d")
    clean_region = region_name.replace(" ", "_").replace("—", "").replace("/", "_").replace("(", "").replace(")", "").strip("_")
    daily_filename = f"sekhmet_sync_{clean_region}_{date_range[0]}_{date_range[1]}_daily.csv"

    with c1:
        st.download_button(
            label="📥 Download Daily Series (CSV)",
            data=get_csv_bytes(daily_export),
            file_name=daily_filename,
            mime="text/csv",
            help="Daily harmonised hotspot series for the selected search",
        )

    det_export = det_f.copy()
    if not det_export.empty and "date" in det_export.columns:
        det_export["date"] = det_export["date"].dt.strftime("%Y-%m-%d")
    det_filename = f"sekhmet_sync_{clean_region}_{date_range[0]}_{date_range[1]}_detections.csv"

    with c2:
        st.download_button(
            label="📥 Download Harmonised Detections (CSV)",
            data=get_csv_bytes(det_export),
            file_name=det_filename,
            mime="text/csv",
            help="Individual hotspot records for the selected search",
        )

# ---------------------------------------------------------------------------
# Method & Limitations
# ---------------------------------------------------------------------------

def render_method_box():
    with st.expander("📋 Method and Limitations", expanded=False):
        st.markdown(
            r"""
            **Plain-Language Summary:**  
            We count satellite-detected hotspots in California, 2020–2024, after filtering the more sensitive VIIRS sensor so it matches MODIS. MODIS is counted as-is; VIIRS is counted only if it is bright enough (at least 6.5 megawatts). This gives one combined daily count, with a historical median for comparison. The 6.5 threshold is experimental — it was fitted on California data from 2012–2013, and it does not correct for viewing angle or for how many satellites were flying in a given year.

            ---

            **Harmonization Method:**
            - **MODIS C6.1 (Terra/Aqua):** Hotspots counted as-is (confidence $\ge 30$).
            - **VIIRS NOAA-20/21:** Hotspots filtered with an **experimental 6.5 MW FRP threshold** (confidence $\ne$ 'l'). Faint hotspots below 6.5 MW are removed to calibrate VIIRS sensitivity to the pre-drift MODIS reference scale.
            - *Note:* The 6.5 MW threshold was fitted empirically on California 2012–2013 data; it is not yet globally validated.

            ---

            **Biome Stability Check (Sub-Region Transferability):**  
            Harmonised VIIRS/MODIS ratio is stable across Northern Forests and Sierra Nevada (1.98 vs 2.01), with a higher ratio in Southern Chaparral (2.48), consistent with smaller thermal cores in fast-moving chaparral fires favouring VIIRS 375 m pixels.

            | Sub-Region / Biome | MODIS (Harm.) | VIIRS (≥ 6.5 MW) | Total Harmonised | Harmonised VIIRS/MODIS Ratio |
            | :--- | :---: | :---: | :---: | :---: |
            | Northern Forests | 61,204 | 121,237 | 182,441 | 1.98 |
            | Sierra Nevada / Central | 24,522 | 49,235 | 73,757 | 2.01 |
            | Southern Chaparral | 7,350 | 18,199 | 25,549 | 2.48 |
            | **3-Biome Subtotal** | **93,076** | **188,671** | **281,747** | **2.03** |

            ---

            **Constellation Expansion & Annual Breakdown:**  
            | Observation Year | MODIS (Harm.) | VIIRS (≥ 6.5 MW) | Total Harmonised | Harmonised VIIRS/MODIS Ratio | Active Satellites in Scope |
            | :---: | :---: | :---: | :---: | :---: | :--- |
            | 2020 | 46,823 | 93,269 | 140,092 | 1.99 | Terra, Aqua, NOAA-20 |
            | 2021 | 42,522 | 77,411 | 119,933 | 1.82 | Terra, Aqua, NOAA-20 |
            | 2022 | 6,714 | 9,133 | 15,847 | 1.36 | Terra, Aqua, NOAA-20 |
            | 2023 | 7,222 | 19,774 | 26,996 | 2.74 | Terra, Aqua, NOAA-20, NOAA-21 |
            | 2024 | 10,514 | 33,792 | 44,306 | 3.21 | Terra, Aqua, NOAA-20, NOAA-21 |

            ---

            **Spatial & Temporal Scope:**
            - Data source: NASA Earthdata FIRMS active fire products.
            - Spatial scope: California state boundary (US Census TIGER/Line 2023).
            - Temporal scope: 2020-01-01 to 2024-12-31.
            """
        )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

def render_footer(is_extended: bool = False):
    sub_title = "California 2000–2024 (25-Yr Climatology) Archive" if is_extended else "California 2020–2024 Archive"
    st.markdown(
        f"""
        <div style="text-align: center; color: #6B7280; font-size: 0.82rem; margin-top: 28px; padding-top: 16px; border-top: 1px solid #E5E7EB;">
          <strong>Sekhmet Sync</strong> • <a href="https://sekhmet-sync.streamlit.app/" target="_blank" style="color: #4B5563; text-decoration: none; font-weight: 500;">sekhmet-sync.streamlit.app</a><br>
          <span style="font-size: 0.78rem; opacity: 0.85;">Data: NASA FIRMS (Public Domain) • {sub_title} • No NASA logos used</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Main Application Entry Point
# ---------------------------------------------------------------------------

def main():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    region_choice, custom_bounds, date_range, is_extended = render_sidebar()
    render_header(is_extended=is_extended)

    daily_statewide = load_statewide_daily(is_extended=is_extended)
    detections = load_detections(is_extended=is_extended)

    if daily_statewide is None or detections is None:
        st.error("Missing harmonised datasets in `data/`. Run `python build_daily_harmonized.py` first.")
        st.stop()

    daily_f, det_f, cov_status, active_bounds = filter_data(
        daily_statewide, detections, region_choice, custom_bounds, date_range
    )

    if cov_status == "OUT_OF_COVERAGE":
        st.warning("Selected area is outside the California data archive — no coverage.")
        st.info(
            f"The California archive covers latitude {CALIFORNIA_BBOX['min_lat']}° to {CALIFORNIA_BBOX['max_lat']}° "
            f"and longitude {CALIFORNIA_BBOX['min_lon']}° to {CALIFORNIA_BBOX['max_lon']}°. "
            "Historical baseline tabs are restricted to this bounding box. Global live queries are available in the 📡 Situational Awareness tab."
        )
    else:
        render_stat_cards(daily_f)

    if cov_status == "PARTIAL_OVERLAP":
        st.info(
            f"ℹ️ Selected custom bounding box partially overlaps California. "
            f"Filtered to the intersection: Lat [{active_bounds['min_lat']:.2f}, {active_bounds['max_lat']:.2f}], "
            f"Lon [{active_bounds['min_lon']:.2f}, {active_bounds['max_lon']:.2f}]."
        )

    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 Burning Calendar",
        "🗺️ Spatial Footprint",
        "📈 Anomaly Analysis",
        "📡 Situational Awareness",
        "❓ Why Harmonisation",
    ])

    with tab1:
        if cov_status == "OUT_OF_COVERAGE":
            st.warning("Selected area is outside the California data archive — no coverage.")
        else:
            render_calendar(daily_f, region_choice)

    with tab2:
        if cov_status == "OUT_OF_COVERAGE":
            st.warning("Selected area is outside the California data archive — no coverage.")
        else:
            render_spatial_footprint(det_f, region_choice, active_bounds)

    with tab3:
        if cov_status == "OUT_OF_COVERAGE":
            st.warning("Selected area is outside the California data archive — no coverage.")
        else:
            render_anomaly(daily_f, region_choice)

    with tab4:
        render_situational_awareness(daily_f, cov_status, active_bounds, region_choice)

    with tab5:
        render_why_harmonisation(daily_statewide)
        st.markdown("---")
        if cov_status != "OUT_OF_COVERAGE":
            render_downloads(daily_f, det_f, region_choice, date_range)
        else:
            st.info("Historical CSV download unavailable for out-of-coverage bounding box.")

    render_method_box()
    render_footer(is_extended=is_extended)

if __name__ == "__main__":
    main()
