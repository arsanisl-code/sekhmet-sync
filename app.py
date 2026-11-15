"""
app.py — Sekhmet Sync Streamlit Web Application

Harmonized burning activity calendar for California (2020–2024).
NASA International Space Apps Challenge 2026: Harmonization of MODIS and VIIRS Hot Spots.

Reads precomputed files only:
  - data/daily_series_harmonised.csv
  - data/harmonised_detections.csv
  - exports/discontinuity.png (optional historical demo)

No NASA logos. Sekhmet Egyptian Palette (WCAG AA compliant).
"""

import sys
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Sekhmet Sync",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

DAILY_CSV = Path("data/daily_series_harmonised.csv")
DETECTIONS_CSV = Path("data/harmonised_detections.csv")
DISCONTINUITY_PNG = Path("exports/discontinuity.png")

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
# Global CSS (Egyptian Palette & Layout Controls)
# ---------------------------------------------------------------------------

GLOBAL_CSS = """
<style>
/* Active tab underline in Basalt */
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    border-bottom: 3px solid #1C1B1A;
    color: #1C1B1A;
    font-weight: 600;
}
.stTabs [data-baseweb="tab"] {
    color: #4A4744;
}
/* Stat card metrics: 1.35rem to prevent 8-digit ellipsis truncation */
[data-testid="stMetricLabel"] {
    color: #1C1B1A !important;
    font-size: 0.80rem;
    font-weight: 500;
}
[data-testid="stMetricValue"] {
    color: #1C1B1A !important;
    font-size: 1.35rem !important;
    white-space: nowrap;
}
</style>
"""

# ---------------------------------------------------------------------------
# Cached Data Loaders
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading statewide daily series …")
def load_statewide_daily():
    if not DAILY_CSV.exists():
        return None
    df = pd.read_csv(DAILY_CSV, parse_dates=["date"])
    for col in ["raw_modis_hotspots", "raw_viirs_hotspots", "harmonised_hotspots",
                "median_hotspots", "anomaly_hotspots"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

@st.cache_data(show_spinner="Loading harmonised detections dataset …")
def load_detections():
    if not DETECTIONS_CSV.exists():
        return None
    df = pd.read_csv(DETECTIONS_CSV, parse_dates=["date"])
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

def render_header():
    st.markdown(
        """
        <div style="background-color:#1C1B1A;border-bottom:2px solid #D4AF37;
                    padding:16px 24px;margin-bottom:0">
          <span style="color:#D4AF37;font-size:1.6rem;font-weight:700">
            🔥 Sekhmet Sync
          </span>
          <span style="color:#D4AF37;font-size:1.0rem;margin-left:12px">
            — Harmonized Satellite Hotspot Activity Calendar (California 2020–2024)
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#5E4605;font-size:0.85em;margin-top:6px;margin-bottom:12px">'
        "⚠️ Harmonization applies an experimental 6.5 MW FRP sensitivity threshold to VIIRS "
        "to align detection counts with the pre-drift MODIS baseline. See Method & Limitations."
        "</p>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Sidebar Controls
# ---------------------------------------------------------------------------

def render_sidebar():
    st.sidebar.markdown("## Region & Timeframe")

    region_choice = st.sidebar.selectbox(
        "Choose Region",
        options=list(REGIONS.keys()),
        index=0,
        help="Select a defined California fire regime or specify a custom bounding box.",
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

    start_date = st.sidebar.date_input(
        "Start Date",
        value=date(2020, 1, 1),
        min_value=date(2020, 1, 1),
        max_value=date(2024, 12, 31),
    )
    end_date = st.sidebar.date_input(
        "End Date",
        value=date(2024, 12, 31),
        min_value=date(2020, 1, 1),
        max_value=date(2024, 12, 31),
    )

    if start_date > end_date:
        st.sidebar.error("Start Date must be on or before End Date.")
        end_date = start_date

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Sensors in Archive:**\n"
        "- MODIS C6.1 (Terra + Aqua)\n"
        "- VIIRS NOAA-20 (375 m)\n"
        "- VIIRS NOAA-21 (from 2023-03-01)\n\n"
        "**Harmonization Threshold:**\n"
        "`VIIRS FRP >= 6.5 MW` (experimental)"
    )

    return region_choice, custom_bounds, (start_date, end_date)

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

def render_daily_matrix(daily_f, region_name):
    """Render 5x366 Daily Burning Activity Calendar Matrix."""
    years = [2020, 2021, 2022, 2023, 2024]
    d = daily_f.copy()
    d["year"] = d["date"].dt.year
    d["doy"] = d["date"].dt.dayofyear

    # Build 5x366 matrix
    matrix = np.full((5, 366), np.nan)
    for i, yr in enumerate(years):
        sub = d[d["year"] == yr]
        for _, row in sub.iterrows():
            doy_idx = int(row["doy"]) - 1
            if 0 <= doy_idx < 366:
                matrix[i, doy_idx] = float(row["harmonised_hotspots"])

    # Sequential Sekhmet palette (Sand -> Gold -> Crimson -> Deep Crimson)
    sekhmet_colorscale = [
        [0.00, "#E8DCC4"],
        [0.05, "#D8C3A5"],
        [0.30, "#C68B25"],
        [0.70, "#A82E2E"],
        [1.00, "#8B1E1E"],
    ]

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=list(range(1, 367)),
        y=[str(yr) for yr in years],
        colorscale=sekhmet_colorscale,
        colorbar=dict(title="Harmonised Hotspots", tickfont=dict(color="#1C1B1A")),
        xgap=0.5,
        ygap=1,
        zmin=0,
        hovertemplate="Year: %{y}<br>DOY: %{x}<br>Harmonised Hotspots: %{z:.0f}<extra></extra>",
    ))

    # Month demarcation lines
    month_starts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for ms in month_starts:
        fig.add_vline(x=ms - 0.5, line_width=0.5, line_color="#D8C3A5", opacity=0.8)

    # Dynamic peak callout
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
            arrowcolor="#D4AF37",
            font=dict(color="#5E4605", size=10),
            bgcolor="#E8DCC4",
            bordercolor="#D4AF37",
            borderwidth=1,
        )

    fig.update_layout(
        title=dict(text=f"Burning Activity Calendar (Daily 5×366) — {region_name}", font=dict(color="#1C1B1A", size=13)),
        xaxis=dict(
            tickmode="array",
            tickvals=[ms + 10 for ms in month_starts],
            ticktext=month_labels,
            tickfont=dict(color="#1C1B1A", size=9),
            showgrid=False,
        ),
        yaxis=dict(tickfont=dict(color="#1C1B1A"), autorange="reversed"),
        paper_bgcolor="#E8DCC4",
        plot_bgcolor="#E8DCC4",
        height=290,
        margin=dict(l=50, r=60, t=45, b=30),
    )

    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Rows = years 2020–2024. Columns = day-of-year 1–366. "
        "Papyrus cells = zero hotspots detected. Grey cells (DOY 366 in non-leap years) = no data."
    )


def render_monthly_heatmap(daily_f, region_name):
    """Render 5x12 Monthly Burning Activity Heatmap showing macro trends and seasonal patterns."""
    years = [2020, 2021, 2022, 2023, 2024]
    months = list(range(1, 13))
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    d = daily_f.copy()
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month

    monthly_agg = d.groupby(["year", "month"])["harmonised_hotspots"].sum().reset_index()
    matrix = np.zeros((len(years), 12))
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

    sekhmet_colorscale = [
        [0.00, "#E8DCC4"],
        [0.05, "#D8C3A5"],
        [0.30, "#C68B25"],
        [0.70, "#A82E2E"],
        [1.00, "#8B1E1E"],
    ]

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=month_labels,
        y=[str(yr) for yr in years],
        text=text_matrix,
        texttemplate="%{text}",
        textfont=dict(size=11, color="#1C1B1A"),
        colorscale=sekhmet_colorscale,
        colorbar=dict(title="Hotspots / Mo", tickfont=dict(color="#1C1B1A")),
        xgap=2,
        ygap=2,
        zmin=0,
        hovertemplate="Year: %{y}<br>Month: %{x}<br>Harmonised Hotspots: %{z:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=f"Monthly Burning Activity Calendar (5×12) — {region_name}", font=dict(color="#1C1B1A", size=13)),
        xaxis=dict(title="Month", tickfont=dict(color="#1C1B1A")),
        yaxis=dict(title="Year", tickfont=dict(color="#1C1B1A"), autorange="reversed"),
        paper_bgcolor="#E8DCC4",
        plot_bgcolor="#E8DCC4",
        height=310,
        margin=dict(l=50, r=60, t=45, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Rows = years 2020–2024. Columns = months Jan–Dec. "
        "Cell values display total monthly harmonised hotspots (k = thousands). "
        "Provides an overview of seasonal wildfire concentration (Aug–Oct) and multi-year climate trends."
    )


def render_daily_line(daily_f, region_name):
    """Daily hotspots vs multi-year median line chart."""
    d = daily_f.copy()

    fig = go.Figure()

    # Above median fill (Crimson)
    fig.add_trace(go.Scatter(
        x=pd.concat([d["date"], d["date"].iloc[::-1]]),
        y=pd.concat([
            d["harmonised_hotspots"].where(d["anomaly_hotspots"] > 0, d["median_hotspots"]),
            d["median_hotspots"].iloc[::-1],
        ]),
        fill="toself",
        fillcolor="rgba(168,46,46,0.25)",
        line=dict(color="rgba(255,255,255,0)"),
        name="Above median",
    ))

    # Below median fill (Lapis)
    fig.add_trace(go.Scatter(
        x=pd.concat([d["date"], d["date"].iloc[::-1]]),
        y=pd.concat([
            d["harmonised_hotspots"].where(d["anomaly_hotspots"] < 0, d["median_hotspots"]),
            d["median_hotspots"].iloc[::-1],
        ]),
        fill="toself",
        fillcolor="rgba(27,54,93,0.15)",
        line=dict(color="rgba(255,255,255,0)"),
        name="Below median",
    ))

    # 5-Year Median line (Malachite dashed)
    fig.add_trace(go.Scatter(
        x=d["date"],
        y=d["median_hotspots"],
        name="Reference Median (2020–2024)",
        line=dict(color="#2E6F40", width=2.2, dash="dash"),
    ))

    # Observed daily hotspots (Basalt solid)
    fig.add_trace(go.Scatter(
        x=d["date"],
        y=d["harmonised_hotspots"],
        name="Harmonised Hotspots",
        line=dict(color="#1C1B1A", width=1.6),
    ))

    # Top 5 anomaly days (Deep Crimson stars)
    top5 = d.nlargest(5, "anomaly_hotspots")
    fig.add_trace(go.Scatter(
        x=top5["date"],
        y=top5["harmonised_hotspots"],
        mode="markers",
        marker=dict(color="#8B1E1E", size=9, symbol="star"),
        name="Top 5 Anomaly Days",
        hovertemplate="%{x}<br>Hotspots: %{y:,}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=f"Daily Burning Activity vs. Reference Median — {region_name}", font=dict(color="#1C1B1A", size=13)),
        xaxis=dict(title="Date", tickfont=dict(color="#1C1B1A")),
        yaxis=dict(title="Daily Hotspots", tickfont=dict(color="#1C1B1A")),
        height=360,
        paper_bgcolor="#E8DCC4",
        plot_bgcolor="#E8DCC4",
        legend=dict(x=0.01, y=0.99, font=dict(color="#1C1B1A")),
        margin=dict(l=50, r=40, t=45, b=45),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_calendar(daily_f, region_name):
    """Burning Activity Calendar container with multi-scale views."""
    cal_mode = st.radio(
        "Calendar View",
        [
            "📅 Daily Matrix (5×366)",
            "🗓️ Monthly Heatmap (5×12)",
            "📈 Daily Line (Hotspots vs. Median)",
        ],
        horizontal=True,
        help="Select view: 5×366 daily matrix for intra-season ignition spikes, 5×12 monthly rollup for macro seasonal trends, or daily line chart for unusual fire days.",
    )

    if cal_mode == "📅 Daily Matrix (5×366)":
        render_daily_matrix(daily_f, region_name)
    elif cal_mode == "🗓️ Monthly Heatmap (5×12)":
        render_monthly_heatmap(daily_f, region_name)
    else:
        render_daily_line(daily_f, region_name)


# ---------------------------------------------------------------------------
# Spatial Footprint Tab (Where Burning Occurred)
# ---------------------------------------------------------------------------

def render_spatial_footprint(det_f, region_name, active_bounds):
    """Render Plotly OpenStreetMap of harmonised hotspot locations."""
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

    # Center coordinates from active bounding box
    center_lat = (active_bounds["min_lat"] + active_bounds["max_lat"]) / 2.0
    center_lon = (active_bounds["min_lon"] + active_bounds["max_lon"]) / 2.0

    # Dynamic zoom level based on bounding box span
    lat_span = active_bounds["max_lat"] - active_bounds["min_lat"]
    lon_span = active_bounds["max_lon"] - active_bounds["min_lon"]
    max_span = max(lat_span, lon_span)
    if max_span > 6.0:
        zoom = 5.0
    elif max_span > 3.0:
        zoom = 6.0
    elif max_span > 1.5:
        zoom = 7.0
    else:
        zoom = 8.0

    fig = go.Figure()

    # Separate traces for MODIS (Lapis) and VIIRS (Amber)
    for sensor, color, name in [
        ("MODIS", "#1B365D", "MODIS (Reference)"),
        ("VIIRS", "#C68B25", "VIIRS (FRP ≥ 6.5 MW)"),
    ]:
        sub = d_map[d_map["sensor"] == sensor]
        if sub.empty:
            continue

        # Scale marker size logarithmically by FRP (2.5 to 8.5 px)
        sizes = np.clip(np.log1p(sub["frp"].fillna(1)) * 1.5, 2.5, 8.5)

        hover_text = [
            f"<b>{row.date.strftime('%Y-%m-%d') if hasattr(row.date, 'strftime') else row.date}</b><br>"
            f"Sensor: {row.sensor} ({row.satellite})<br>"
            f"FRP: {row.frp:.1f} MW<br>"
            f"Lat: {row.latitude:.3f}, Lon: {row.longitude:.3f}"
            for row in sub.itertuples()
        ]

        fig.add_trace(go.Scattermapbox(
            lat=sub["latitude"],
            lon=sub["longitude"],
            mode="markers",
            marker=dict(
                size=sizes,
                color=color,
                opacity=0.6,
            ),
            name=f"{name} ({len(sub):,} pts)",
            text=hover_text,
            hoverinfo="text",
        ))

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom,
        ),
        title=dict(
            text=f"Spatial Hotspot Footprint — {region_name}",
            font=dict(color="#1C1B1A", size=13),
        ),
        height=480,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="#E8DCC4",
        legend=dict(
            x=0.01,
            y=0.99,
            bgcolor="#D8C3A5",
            bordercolor="#1C1B1A",
            borderwidth=1,
            font=dict(color="#1C1B1A"),
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

    if sampled:
        st.caption(
            f"ℹ️ Showing **5,000 sampled hotspots** (out of **{total_pts:,}** total in selected region/dates) "
            "for smooth, fast rendering. Points are colored by sensor: Lapis = MODIS, Amber = VIIRS (≥ 6.5 MW). "
            "Marker size scales logarithmically with Fire Radiative Power (MW)."
        )
    else:
        st.caption(
            f"ℹ️ Showing **all {total_pts:,} hotspots** in selected region and date range. "
            "Points are colored by sensor: Lapis = MODIS, Amber = VIIRS (≥ 6.5 MW). "
            "Marker size scales logarithmically with Fire Radiative Power (MW)."
        )


# ---------------------------------------------------------------------------
# Anomaly Tab
# ---------------------------------------------------------------------------

def render_anomaly(daily_f, region_name):
    """Daily hotspots vs multi-year median and top anomaly table."""
    d = daily_f.copy()

    # Render the daily line chart
    render_daily_line(d, region_name)

    # Top 10 anomaly table
    top10 = d.nlargest(10, "anomaly_hotspots")[["date", "raw_modis_hotspots", "raw_viirs_hotspots", "harmonised_hotspots", "median_hotspots", "anomaly_hotspots"]].copy()
    top10["date"] = top10["date"].dt.strftime("%Y-%m-%d")
    top10.columns = ["Date", "MODIS (Raw)", "VIIRS (Raw)", "Harmonised", "Median", "Anomaly"]
    st.markdown("**Top 10 Above-Median Anomaly Days (Critical Fire Periods):**")
    st.dataframe(top10, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Why Harmonisation Tab
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

    # Annual breakdown bar chart
    d = daily_f.copy()
    d["year"] = d["date"].dt.year
    agg = d.groupby("year").agg({
        "raw_modis_hotspots": "sum",
        "raw_viirs_hotspots": "sum",
        "harmonised_hotspots": "sum",
    }).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=agg["year"].astype(str), y=agg["raw_modis_hotspots"], name="MODIS (Raw)", marker_color="#1B365D"))
    fig.add_trace(go.Bar(x=agg["year"].astype(str), y=agg["raw_viirs_hotspots"], name="VIIRS (Raw)", marker_color="#C68B25"))
    fig.add_trace(go.Bar(x=agg["year"].astype(str), y=agg["harmonised_hotspots"], name="Harmonised (Thresholded)", marker_color="#A82E2E"))

    fig.update_layout(
        barmode="group",
        title=dict(text="Raw vs. Harmonised Annual Hotspot Counts (Selected Area)", font=dict(color="#1C1B1A")),
        xaxis=dict(title="Year", tickfont=dict(color="#1C1B1A")),
        yaxis=dict(title="Total Hotspots", tickfont=dict(color="#1C1B1A")),
        height=340,
        paper_bgcolor="#E8DCC4",
        plot_bgcolor="#E8DCC4",
        legend=dict(x=0.01, y=0.99, font=dict(color="#1C1B1A")),
        margin=dict(l=50, r=40, t=50, b=50),
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Search CSV Downloads (Slices to User's Selected Region & Date Range)
# ---------------------------------------------------------------------------

def render_downloads(daily_f, det_f, region_name, date_range):
    st.markdown("### Download Search Analytics")
    st.caption(f"Exports are dynamically sliced to your chosen region (**{region_name}**) and dates (**{date_range[0]} to {date_range[1]}**).")

    c1, c2 = st.columns(2)

    # 1. Daily aggregated series download
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

    # 2. Per-detection download
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
            **Harmonization Method:**
            - **MODIS C6.1 (Terra/Aqua):** Hotspots counted as-is (confidence $\ge 30$).
            - **VIIRS NOAA-20/21:** Hotspots filtered with an **experimental 6.5 MW FRP threshold** (confidence $\ne$ 'l'). Faint hotspots below 6.5 MW are removed to calibrate VIIRS sensitivity to the pre-drift MODIS reference scale.
            - *Note:* The 6.5 MW threshold was fitted empirically on California 2012–2013 data; it is not yet globally validated.

            **Spatial & Temporal Scope:**
            - Data source: NASA Earthdata FIRMS active fire products.
            - Spatial scope: California state boundary (US Census TIGER/Line 2023).
            - Temporal scope: 2020-01-01 to 2024-12-31 (plus 2011–2013 historical demonstration). Expanding to the full early-2000s to present archive is planned future work.

            **Known Limitations:**
            - **Industrial Heat / Gas Flares:** Static heat sources (Type 2, ~7% of detections) are retained in the dataset and not filtered out.
            - **Orbital Drift:** Terra and Aqua experienced local overpass time drift post-2021 (Terra drifted earlier by ~44 min, Aqua drifted later by ~40 min by 2024), which affects diurnal sampling.
            - **Baseline:** The historical median is computed across 2020–2024 only, which is heavily influenced by the extreme 2020 California fire season.
            """
        )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

def render_footer():
    st.markdown(
        "<p style='text-align:center;color:#4A4744;font-size:0.8em;margin-top:16px'>"
        "Sekhmet Sync | Data: NASA FIRMS (public domain) | "
        "California 2020–2024 | No NASA logos used"
        "</p>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Main Application Entry Point
# ---------------------------------------------------------------------------

def main():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    render_header()

    region_choice, custom_bounds, date_range = render_sidebar()

    daily_statewide = load_statewide_daily()
    detections = load_detections()

    if daily_statewide is None or detections is None:
        st.error("Missing harmonised datasets in `data/`. Run `python build_daily_harmonized.py` first.")
        st.stop()

    # Filter data to selected region and dates
    daily_f, det_f, cov_status, active_bounds = filter_data(
        daily_statewide, detections, region_choice, custom_bounds, date_range
    )

    # Handle out-of-coverage rule
    if cov_status == "OUT_OF_COVERAGE":
        st.warning("Selected area is outside the California data archive — no coverage.")
        st.info(
            f"The California archive covers latitude {CALIFORNIA_BBOX['min_lat']}° to {CALIFORNIA_BBOX['max_lat']}° "
            f"and longitude {CALIFORNIA_BBOX['min_lon']}° to {CALIFORNIA_BBOX['max_lon']}°. "
            "Please select coordinates within this bounding box."
        )
        st.stop()

    if cov_status == "PARTIAL_OVERLAP":
        st.info(
            f"ℹ️ Selected custom bounding box partially overlaps California. "
            f"Filtered to the intersection: Lat [{active_bounds['min_lat']:.2f}, {active_bounds['max_lat']:.2f}], "
            f"Lon [{active_bounds['min_lon']:.2f}, {active_bounds['max_lon']:.2f}]."
        )

    # Render always-visible Stat Cards
    render_stat_cards(daily_f)
    st.divider()

    # Interactive Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Burning Calendar",
        "🗺️ Spatial Footprint",
        "📈 Anomaly Analysis",
        "❓ Why Harmonisation",
    ])

    with tab1:
        render_calendar(daily_f, region_choice)

    with tab2:
        render_spatial_footprint(det_f, region_choice, active_bounds)

    with tab3:
        render_anomaly(daily_f, region_choice)

    with tab4:
        render_why_harmonisation(daily_f)

    st.divider()
    render_downloads(daily_f, det_f, region_choice, date_range)
    render_method_box()
    render_footer()

if __name__ == "__main__":
    main()
