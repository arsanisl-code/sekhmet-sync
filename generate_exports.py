"""
generate_exports.py — Generate static PNG exports for pitch and reports

Reads:
  data/daily_series_harmonised.csv
  data/harmonised_detections.csv

Writes:
  exports/calendar.png        (5×366 Daily Burning Activity Heatmap)
  exports/monthly_heatmap.png (5×12 Monthly Rollup Heatmap for overview)
  exports/anomaly_daily.png   (Daily Time Series Line Chart vs. 5-Year Median)
  exports/map.png             (Spatial distribution of harmonised detections)

Usage:
    python generate_exports.py
"""

import sys
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("generate_exports")

DAILY_CSV = Path("data/daily_series_harmonised.csv")
DETECTIONS_CSV = Path("data/harmonised_detections.csv")
EXPORTS = Path("exports")


def get_sekhmet_colormap():
    cmap_colors = ["#E8DCC4", "#D8C3A5", "#C68B25", "#A82E2E", "#8B1E1E"]
    cmap = mcolors.LinearSegmentedColormap.from_list("sekhmet", cmap_colors)
    cmap.set_bad(color="#B8B2A6")
    return cmap


def generate_calendar_png(daily: pd.DataFrame) -> None:
    """Generate exports/calendar.png — 5x366 daily burning-activity heatmap."""
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["year"] = d["date"].dt.year
    d["doy"] = d["date"].dt.dayofyear

    years = [2020, 2021, 2022, 2023, 2024]
    max_doy = 366

    matrix = np.full((len(years), max_doy), np.nan)
    has_data = np.zeros((len(years), max_doy), dtype=bool)

    for i, yr in enumerate(years):
        sub = d[d["year"] == yr]
        for _, row in sub.iterrows():
            doy = int(row["doy"]) - 1
            if 0 <= doy < max_doy:
                matrix[i, doy] = float(row["harmonised_hotspots"])
                has_data[i, doy] = True

    cmap = get_sekhmet_colormap()
    masked = np.ma.masked_where(~has_data, matrix)

    fig, ax = plt.subplots(figsize=(16, 4))
    fig.patch.set_facecolor("#E8DCC4")
    ax.set_facecolor("#E8DCC4")

    im = ax.imshow(
        masked,
        aspect="auto",
        cmap=cmap,
        interpolation="nearest",
        extent=[0.5, max_doy + 0.5, len(years) + 0.5, 0.5],
        vmin=0,
    )

    ax.set_yticks(range(1, len(years) + 1))
    ax.set_yticklabels([str(y) for y in years], color="#1C1B1A", fontweight="bold")
    ax.tick_params(colors="#1C1B1A")
    for spine in ax.spines.values():
        spine.set_edgecolor("#1C1B1A")

    ax.set_title(
        "Sekhmet Sync — Burning Activity Calendar, California 2020–2024 (Harmonised Hotspots)",
        fontsize=12,
        color="#1C1B1A",
        pad=12,
    )

    # Month boundaries
    month_starts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for ms in month_starts:
        ax.axvline(x=ms - 0.5, color="#1C1B1A", linewidth=0.5, alpha=0.3)
    ax.set_xticks([ms + 14 for ms in month_starts])
    ax.set_xticklabels(month_labels, fontsize=9, color="#1C1B1A")

    # Peak annotation (2020-09-09, 10,320 hotspots)
    pk_row = d.loc[d["harmonised_hotspots"].idxmax()]
    pk_doy = int(pk_row["doy"])
    pk_year_idx = years.index(int(pk_row["year"])) + 1
    pk_count = int(pk_row["harmonised_hotspots"])

    ax.annotate(
        f"★ Peak: {pk_count:,} hotspots (2020-09-09)",
        xy=(pk_doy, pk_year_idx),
        xytext=(pk_doy + 15, pk_year_idx - 0.5),
        fontsize=9,
        color="#5E4605",
        arrowprops=dict(arrowstyle="->", color="#D4AF37", lw=1.5),
        bbox=dict(facecolor="#E8DCC4", edgecolor="#D4AF37", boxstyle="round,pad=0.3"),
    )

    cbar = plt.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cbar.set_label("Harmonised Hotspots / Day", color="#1C1B1A")
    cbar.ax.yaxis.set_tick_params(color="#1C1B1A")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="#1C1B1A")

    out = EXPORTS / "calendar.png"
    plt.tight_layout()
    plt.savefig(str(out), dpi=180, bbox_inches="tight", facecolor="#E8DCC4")
    plt.close()
    log.info("Saved %s", out)


def generate_monthly_heatmap_png(daily: pd.DataFrame) -> None:
    """Generate exports/monthly_heatmap.png — 5x12 monthly aggregate heatmap for overview."""
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month

    years = [2020, 2021, 2022, 2023, 2024]
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    m_agg = d.groupby(["year", "month"])["harmonised_hotspots"].sum().unstack(fill_value=0)
    matrix = np.zeros((len(years), 12))
    for i, yr in enumerate(years):
        for j, mo in enumerate(range(1, 13)):
            if yr in m_agg.index and mo in m_agg.columns:
                matrix[i, j] = m_agg.loc[yr, mo]

    cmap = get_sekhmet_colormap()

    fig, ax = plt.subplots(figsize=(12, 4))
    fig.patch.set_facecolor("#E8DCC4")
    ax.set_facecolor("#E8DCC4")

    im = ax.imshow(matrix, aspect="auto", cmap=cmap, interpolation="nearest", vmin=0)

    ax.set_xticks(range(12))
    ax.set_xticklabels(month_labels, color="#1C1B1A", fontsize=9)
    ax.set_yticks(range(len(years)))
    ax.set_yticklabels([str(y) for y in years], color="#1C1B1A", fontweight="bold")
    ax.tick_params(colors="#1C1B1A")
    for spine in ax.spines.values():
        spine.set_edgecolor("#1C1B1A")

    # Add text labels inside cells
    for i in range(len(years)):
        for j in range(12):
            val = matrix[i, j]
            label = f"{val/1000:.1f}k" if val >= 1000 else (f"{int(val)}" if val > 0 else "0")
            text_color = "#FFFFFF" if val > 20000 else "#1C1B1A"
            ax.text(j, i, label, ha="center", va="center", color=text_color, fontsize=8, fontweight="bold")

    ax.set_title(
        "Sekhmet Sync — Monthly Burning Activity Rollup (California 2020–2024)",
        fontsize=12,
        color="#1C1B1A",
        pad=12,
    )

    cbar = plt.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cbar.set_label("Harmonised Hotspots / Month", color="#1C1B1A")
    cbar.ax.yaxis.set_tick_params(color="#1C1B1A")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="#1C1B1A")

    out = EXPORTS / "monthly_heatmap.png"
    plt.tight_layout()
    plt.savefig(str(out), dpi=180, bbox_inches="tight", facecolor="#E8DCC4")
    plt.close()
    log.info("Saved %s", out)


def generate_anomaly_daily_png(daily: pd.DataFrame) -> None:
    """Generate exports/anomaly_daily.png — daily time series vs 5-year median line chart."""
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])

    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor("#E8DCC4")
    ax.set_facecolor("#E8DCC4")

    # Above median fill (Crimson)
    above_mask = d["anomaly_hotspots"] > 0
    ax.fill_between(
        d["date"], d["median_hotspots"], d["harmonised_hotspots"],
        where=above_mask, color="#A82E2E", alpha=0.3, label="Above Median", interpolate=True
    )

    # Below median fill (Lapis)
    below_mask = d["anomaly_hotspots"] < 0
    ax.fill_between(
        d["date"], d["harmonised_hotspots"], d["median_hotspots"],
        where=below_mask, color="#1B365D", alpha=0.15, label="Below Median", interpolate=True
    )

    # Historical Median line (Malachite dashed)
    ax.plot(d["date"], d["median_hotspots"], color="#2E6F40", linestyle="--", linewidth=2.0, label="5-Year Median Baseline")

    # Daily harmonised line (Basalt solid)
    ax.plot(d["date"], d["harmonised_hotspots"], color="#1C1B1A", linewidth=1.2, label="Harmonised Daily Hotspots")

    # Top anomaly marker (2020-09-09)
    top_row = d.loc[d["anomaly_hotspots"].idxmax()]
    ax.scatter([top_row["date"]], [top_row["harmonised_hotspots"]], color="#8B1E1E", s=80, marker="*", zorder=5, label="Peak Anomaly Day")
    ax.annotate(
        f"2020-09-09\n({int(top_row['harmonised_hotspots']):,} hotspots)",
        xy=(top_row["date"], top_row["harmonised_hotspots"]),
        xytext=(top_row["date"] + pd.Timedelta(days=25), top_row["harmonised_hotspots"] - 1000),
        fontsize=8.5,
        color="#5E4605",
        arrowprops=dict(arrowstyle="->", color="#D4AF37", lw=1.2),
        bbox=dict(facecolor="#E8DCC4", edgecolor="#D4AF37", boxstyle="round,pad=0.25"),
    )

    ax.set_title(
        "Sekhmet Sync — Daily Harmonised Hotspots vs. 5-Year Historical Median (2020–2024)",
        fontsize=12,
        color="#1C1B1A",
        pad=12,
    )
    ax.set_ylabel("Daily Hotspots", color="#1C1B1A")
    ax.tick_params(colors="#1C1B1A")
    for spine in ax.spines.values():
        spine.set_edgecolor("#1C1B1A")
    ax.grid(True, alpha=0.25, color="#1C1B1A")

    leg = ax.legend(loc="upper right", facecolor="#D8C3A5", edgecolor="#1C1B1A")
    for text in leg.get_texts():
        text.set_color("#1C1B1A")

    out = EXPORTS / "anomaly_daily.png"
    plt.tight_layout()
    plt.savefig(str(out), dpi=180, bbox_inches="tight", facecolor="#E8DCC4")
    plt.close()
    log.info("Saved %s", out)


def generate_map_png(detections: pd.DataFrame) -> None:
    """Generate exports/map.png — spatial distribution of harmonised detections."""
    import matplotlib.patches as mpatches

    d = detections.dropna(subset=["latitude", "longitude"]).copy()
    color_map = {
        "MODIS": "#1B365D",
        "VIIRS": "#C68B25",
    }
    colors = d["sensor"].map(color_map).fillna("#A82E2E")

    fig, ax = plt.subplots(figsize=(10, 10))
    fig.patch.set_facecolor("#E8DCC4")
    ax.set_facecolor("#E8DCC4")

    ax.scatter(
        d["longitude"], d["latitude"],
        s=1.2, c=colors, alpha=0.35, linewidths=0,
    )
    ax.set_xlim(-124.5, -114.0)
    ax.set_ylim(32.5, 42.0)
    ax.set_xlabel("Longitude", color="#1C1B1A")
    ax.set_ylabel("Latitude", color="#1C1B1A")
    ax.set_title(
        f"Sekhmet Sync — California Harmonised Hotspots, 2020–2024 ({len(d):,} detections)\n"
        "(MODIS = Lapis #1B365D, VIIRS >= 6.5 MW = Dark Ocher #C68B25)",
        fontsize=11,
        color="#1C1B1A",
    )
    ax.tick_params(colors="#1C1B1A")
    for spine in ax.spines.values():
        spine.set_edgecolor("#1C1B1A")
    ax.grid(True, alpha=0.25)

    legend_patches = [
        mpatches.Patch(color="#1B365D", label="MODIS (113,795)"),
        mpatches.Patch(color="#C68B25", label="VIIRS >= 6.5 MW (233,379)"),
    ]
    leg = ax.legend(handles=legend_patches, loc="upper right", facecolor="#D8C3A5", edgecolor="#1C1B1A")
    for text in leg.get_texts():
        text.set_color("#1C1B1A")

    out = EXPORTS / "map.png"
    plt.tight_layout()
    plt.savefig(str(out), dpi=180, bbox_inches="tight", facecolor="#E8DCC4")
    plt.close()
    log.info("Saved %s", out)


def main():
    EXPORTS.mkdir(parents=True, exist_ok=True)

    if not DAILY_CSV.exists():
        log.error("Missing %s. Run build_daily_harmonized.py first.", DAILY_CSV)
        sys.exit(1)

    daily = pd.read_csv(DAILY_CSV)

    log.info("Generating calendar.png (5x366 Daily Heatmap) ...")
    generate_calendar_png(daily)

    log.info("Generating monthly_heatmap.png (5x12 Monthly Rollup for Overview) ...")
    generate_monthly_heatmap_png(daily)

    log.info("Generating anomaly_daily.png (Daily Time Series vs. 5-Year Median) ...")
    generate_anomaly_daily_png(daily)

    if DETECTIONS_CSV.exists():
        log.info("Generating map.png (Spatial Distribution) ...")
        detections = pd.read_csv(DETECTIONS_CSV)
        generate_map_png(detections)

    log.info("All exports successfully generated in %s/", EXPORTS)


if __name__ == "__main__":
    main()
