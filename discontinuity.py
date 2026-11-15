"""
discontinuity.py — Sekhmet Sync historical demonstration (2011–2013)

IMPORTANT: This script uses VIIRS S-NPP data for the demonstration period ONLY.
S-NPP must NOT appear in the main pipeline. See rules.md R3.

Scope: California, 2011-01-01 to 2013-12-31. Monthly counts:
  - Raw MODIS (MODIS_SP)
  - Raw VIIRS S-NPP (VIIRS_SNPP_SP) — available from 2012-01-20
  - Harmonised (MODIS + SNPP combined)

Chart title (exact): "Historical demonstration, 2011–2013, includes S-NPP for this chart only."
Saves: exports/discontinuity.png

Usage:
    python discontinuity.py
"""

import os
import sys
import time
import logging
from datetime import date, timedelta
from pathlib import Path
from io import StringIO

import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("discontinuity")

DATA_RAW = Path("data/raw")
EXPORTS = Path("exports")
BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
BBOX = "-124.5,32.5,-114.0,42.0"
CHUNK_DAYS = 5

# 2011–2013 scope
DISC_START = date(2011, 1, 1)
DISC_END = date(2013, 12, 31)

# SNPP available from 2012-01-20
SNPP_START = date(2012, 1, 20)

# Confidence filters (same rules as main pipeline)
def modis_confidence_ok(df):
    return df["confidence"].astype(float) >= 30

def viirs_confidence_ok(df):
    return df["confidence"].astype(str).str.lower() != "l"

CLUSTER_RADIUS_DEG = 0.009


def date_chunks(start, end, chunk):
    cur = start
    while cur <= end:
        days = min(chunk, (end - cur).days + 1)
        yield cur, days
        cur += timedelta(days=days)


def download_product(key, product, start, end):
    out_path = DATA_RAW / f"{product}_disc_{start.year}_{end.year}.csv"
    if out_path.exists():
        log.info("Using cached: %s", out_path)
        return pd.read_csv(out_path)

    log.info("Downloading %s %s to %s ...", product, start, end)
    chunks = []
    for chunk_start, days in date_chunks(start, end, CHUNK_DAYS):
        url = f"{BASE_URL}/{key}/{product}/{BBOX}/{days}/{chunk_start.isoformat()}"
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            content = resp.text.strip()
            if content and not content.startswith("Not Found"):
                chunk_df = pd.read_csv(StringIO(content))
                if not chunk_df.empty:
                    chunks.append(chunk_df)
        except Exception as e:
            log.warning("Chunk failed %s %s: %s", product, chunk_start, e)
        time.sleep(0.3)

    if not chunks:
        log.warning("No data downloaded for %s", product)
        return pd.DataFrame()

    df = pd.concat(chunks, ignore_index=True).drop_duplicates()
    df.to_csv(out_path, index=False)
    log.info("Saved %d rows to %s", len(df), out_path)
    return df


def apply_filters(df, sensor):
    if df.empty:
        return df
    # Bbox filter
    df = df[
        (df["latitude"] >= 32.5) & (df["latitude"] <= 42.0) &
        (df["longitude"] >= -124.5) & (df["longitude"] <= -114.0)
    ].copy()
    # Confidence filter
    if sensor == "modis":
        df = df[modis_confidence_ok(df)].copy()
    else:
        df = df[viirs_confidence_ok(df)].copy()
    df["acq_date"] = pd.to_datetime(df["acq_date"])
    df["frp"] = pd.to_numeric(df["frp"], errors="coerce")
    df = df[df["frp"].notna() & (df["frp"] > 0)]
    return df


def simple_cluster_count(day_df):
    """
    Minimal O(n log n) clustering: returns number of fires for one day.
    Uses the same KDTree+union-find approach as cluster.py.
    """
    if day_df.empty:
        return 0

    from scipy.spatial import KDTree

    coords = day_df[["latitude", "longitude"]].values.astype(float)
    n = len(coords)
    if n == 0:
        return 0
    if n == 1:
        return 1

    tree = KDTree(coords)
    neighbors = tree.query_ball_tree(tree, r=CLUSTER_RADIUS_DEG)

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    for i, nbrs in enumerate(neighbors):
        for j in nbrs:
            if j != i:
                union(i, j)

    return len(set(find(i) for i in range(n)))


def build_monthly_counts(modis_df, snpp_df):
    """
    Build a monthly DataFrame with raw_modis, raw_snpp, harmonised_fires columns.

    For the harmonised count, we use a fast spatial hash approach:
    round lat/lon to 0.009° grid cells and count unique (date, cell) pairs.
    This approximates the KDTree clustering without the per-day Python loop cost.
    The result is used for a demonstration chart, not a precise scientific output.
    """
    months = pd.date_range("2011-01", "2013-12", freq="MS")

    # Pre-compute grid cell keys for combined dataset
    combined_parts = []
    if not modis_df.empty:
        m = modis_df[["latitude", "longitude", "acq_date"]].copy()
        combined_parts.append(m)
    if not snpp_df.empty:
        s = snpp_df[["latitude", "longitude", "acq_date"]].copy()
        combined_parts.append(s)

    if combined_parts:
        combined = pd.concat(combined_parts, ignore_index=True)
        # Grid cell: round to nearest 0.009° cell
        combined["cell_lat"] = (combined["latitude"] / CLUSTER_RADIUS_DEG).astype(int)
        combined["cell_lon"] = (combined["longitude"] / CLUSTER_RADIUS_DEG).astype(int)
        combined["year_month"] = pd.to_datetime(combined["acq_date"]).dt.to_period("M")
        # Harmonised fires = unique (date, cell_lat, cell_lon) combinations per month
        harm_monthly = combined.groupby("year_month").apply(
            lambda g: g.drop_duplicates(subset=["acq_date", "cell_lat", "cell_lon"]).shape[0]
        ).reset_index()
        harm_monthly.columns = ["year_month", "harmonised_fires"]
    else:
        harm_monthly = pd.DataFrame(columns=["year_month", "harmonised_fires"])

    records = []
    for month_start in months:
        month_end = month_start + pd.offsets.MonthEnd(0)
        label = month_start.strftime("%Y-%m")
        period = month_start.to_period("M")

        # Raw counts
        if not modis_df.empty:
            raw_modis = int(len(modis_df[
                (modis_df["acq_date"] >= month_start) & (modis_df["acq_date"] <= month_end)
            ]))
        else:
            raw_modis = 0

        if not snpp_df.empty:
            raw_snpp = int(len(snpp_df[
                (snpp_df["acq_date"] >= month_start) & (snpp_df["acq_date"] <= month_end)
            ]))
        else:
            raw_snpp = 0

        # Harmonised
        hrow = harm_monthly[harm_monthly["year_month"] == period]
        harmonised = int(hrow["harmonised_fires"].iloc[0]) if not hrow.empty else 0

        records.append({
            "month": label,
            "raw_modis": raw_modis,
            "raw_snpp": raw_snpp,
            "harmonised_fires": harmonised,
        })

    return pd.DataFrame(records)


def plot_discontinuity(monthly: pd.DataFrame) -> go.Figure:
    """
    Create the 3-line discontinuity chart.
    Title (exact): "Historical demonstration, 2011–2013, includes S-NPP for this chart only."
    """
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=monthly["month"],
        y=monthly["raw_modis"],
        name="MODIS (raw detections)",
        mode="lines+markers",
        line=dict(color="#E76F51", width=2),
        marker=dict(size=4),
    ))

    fig.add_trace(go.Scatter(
        x=monthly["month"],
        y=monthly["raw_snpp"],
        name="VIIRS S-NPP (raw detections) — this chart only",
        mode="lines+markers",
        line=dict(color="#2A9D8F", width=2, dash="dot"),
        marker=dict(size=4),
    ))

    fig.add_trace(go.Scatter(
        x=monthly["month"],
        y=monthly["harmonised_fires"],
        name="Harmonised fires (MODIS + S-NPP)",
        mode="lines+markers",
        line=dict(color="#264653", width=3),
        marker=dict(size=5),
    ))

    # Mark SNPP launch
    fig.add_vline(
        x="2012-01",
        line_dash="dash",
        line_color="gray",
        annotation_text="S-NPP\nlaunched",
        annotation_position="top right",
        annotation_font_size=10,
    )

    fig.update_layout(
        title=dict(
            text="Historical demonstration, 2011\u20132013, includes S-NPP for this chart only.",
            font=dict(size=14),
            x=0.5,
        ),
        xaxis_title="Month",
        yaxis_title="Count",
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)"),
        template="plotly_white",
        width=900,
        height=450,
        margin=dict(l=60, r=40, t=70, b=60),
        font=dict(family="Arial, sans-serif"),
    )

    return fig


def assess_continuity(monthly: pd.DataFrame) -> str:
    """
    Report honestly whether the harmonised line is roughly continuous across
    the Jan 2012 S-NPP launch boundary.
    """
    pre_launch = monthly[monthly["month"] < "2012-01"]["harmonised_fires"]
    post_launch_early = monthly[
        (monthly["month"] >= "2012-01") & (monthly["month"] <= "2012-06")
    ]["harmonised_fires"]

    if pre_launch.empty or post_launch_early.empty:
        return "Insufficient data to assess continuity."

    pre_mean = pre_launch.mean()
    post_mean = post_launch_early.mean()

    if pre_mean == 0:
        return "Pre-launch period has no harmonised fires; cannot assess continuity."

    ratio = post_mean / pre_mean if pre_mean > 0 else float("inf")

    if ratio < 1.3:
        continuity = "roughly continuous"
    elif ratio < 2.0:
        continuity = "moderately elevated (some discontinuity)"
    else:
        continuity = "substantially elevated (significant discontinuity)"

    msg = (
        f"Harmonised series continuity assessment:\n"
        f"  Pre-S-NPP mean (2011):       {pre_mean:.1f} fires/month\n"
        f"  Early post-S-NPP mean (H1 2012): {post_mean:.1f} fires/month\n"
        f"  Ratio (post/pre):            {ratio:.2f}\n"
        f"  Assessment: harmonised line is {continuity} across the Jan 2012 boundary.\n"
        f"\n"
        f"NOTE: Before Jan 2012, the harmonised series contains MODIS only.\n"
        f"Any level shift reflects the addition of VIIRS S-NPP detections\n"
        f"that could not be observed by MODIS alone (smaller fires, better\n"
        f"spatial resolution). A perfectly flat harmonised line would be\n"
        f"surprising given the sensor capability difference. The raw MODIS\n"
        f"line should remain approximately flat across the boundary.\n"
    )
    return msg


def main():
    EXPORTS.mkdir(parents=True, exist_ok=True)
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not key:
        log.error("FIRMS_MAP_KEY not set. Cannot download discontinuity data.")
        log.error("Set the key in .env and re-run, or provide data/raw/ files manually.")
        sys.exit(1)

    # Download MODIS 2011–2013
    modis_raw = download_product(key, "MODIS_SP", DISC_START, DISC_END)
    # Download VIIRS SNPP 2012–2013 (S-NPP started 2012-01-20)
    snpp_raw = download_product(key, "VIIRS_SNPP_SP", SNPP_START, DISC_END)

    # Apply filters
    modis_df = apply_filters(modis_raw, "modis")
    snpp_df = apply_filters(snpp_raw, "viirs")

    log.info("Post-filter: MODIS=%d rows, SNPP=%d rows", len(modis_df), len(snpp_df))

    # Build monthly counts
    log.info("Computing monthly counts (this may take a minute) ...")
    monthly = build_monthly_counts(modis_df, snpp_df)
    log.info("Monthly counts:\n%s", monthly.to_string(index=False))

    # Assess continuity
    assessment = assess_continuity(monthly)
    print("\n" + assessment)

    # Plot
    fig = plot_discontinuity(monthly)

    # Save PNG using matplotlib (kaleido not required)
    out_path = EXPORTS / "discontinuity.png"
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker

        fig_mpl, ax = plt.subplots(figsize=(11, 5))
        ax.plot(monthly["month"], monthly["raw_modis"],
                label="MODIS (raw detections)", color="#E76F51",
                marker="o", markersize=3, linewidth=2)
        ax.plot(monthly["month"], monthly["raw_snpp"],
                label="VIIRS S-NPP (raw) — this chart only", color="#2A9D8F",
                marker="o", markersize=3, linewidth=2, linestyle="--")
        ax.plot(monthly["month"], monthly["harmonised_fires"],
                label="Harmonised fires (MODIS + S-NPP)", color="#264653",
                marker="o", markersize=4, linewidth=3)

        # Mark SNPP launch
        snpp_idx = list(monthly["month"]).index("2012-01") if "2012-01" in list(monthly["month"]) else None
        if snpp_idx is not None:
            ax.axvline(x=snpp_idx, color="gray", linestyle="--", linewidth=1)
            ax.text(snpp_idx + 0.3, ax.get_ylim()[1] * 0.9, "S-NPP\nlaunched",
                    fontsize=8, color="gray")

        ax.set_title(
            "Historical demonstration, 2011\u20132013, includes S-NPP for this chart only.",
            fontsize=11,
        )
        ax.set_xlabel("Month")
        ax.set_ylabel("Count")

        # Thin out x-tick labels
        n_months = len(monthly["month"])
        step = max(1, n_months // 12)
        ax.set_xticks(range(0, n_months, step))
        ax.set_xticklabels(monthly["month"].iloc[::step], rotation=45, ha="right", fontsize=7)

        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(str(out_path), dpi=150, bbox_inches="tight")
        plt.close()
        log.info("Saved %s", out_path)
    except Exception as e:
        log.error("Could not save PNG: %s", e)
        # Fallback: save as HTML
        fig.write_html(str(EXPORTS / "discontinuity.html"))
        log.info("Saved exports/discontinuity.html as fallback")


if __name__ == "__main__":
    main()
