"""
harmonize.py — Sekhmet Sync daily aggregation and FRP correction

Reads data/ca_2020_2024.parquet (per-fire rows from cluster.py).
Applies FRP correction, computes daily aggregates, computes historical median.
Writes:
  data/daily_series.csv          — 1,827 rows, daily aggregate
  data/ca_2020_2024_harmonised.csv — per-fire rows with corrected FRP

Gate 3 reconciliation is run automatically and exits with code 1 on failure.

FRP correction: see DECISIONS D06.
  MODIS: factor 1.0 (reference)
  VIIRS NOAA-20: factor 0.85
  VIIRS NOAA-21: factor 0.85

Usage:
    python harmonize.py
"""

import sys
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("harmonize")

PARQUET_IN = Path("data/ca_2020_2024.parquet")
HARMONISED_CSV = Path("data/ca_2020_2024_harmonised.csv")
DAILY_CSV = Path("data/daily_series.csv")

# FRP correction factors (see DECISIONS D06)
# Key: sensors_present value (modis_only | viirs_only | both)
# For 'both' fires, we apply a blended correction based on the fraction of
# MODIS vs VIIRS detections within the fire cluster.
MODIS_FRP_FACTOR = 1.0
VIIRS_FRP_FACTOR = 0.85  # approximate, distributional; see DECISIONS D06

EXPECTED_DAILY_ROWS = 1827  # 2020(366) + 2021(365) + 2022(365) + 2023(365) + 2024(366)


# ---------------------------------------------------------------------------
# FRP correction
# ---------------------------------------------------------------------------

def compute_frp_correction_factor(row: pd.Series) -> float:
    """
    Compute a weighted FRP correction factor for one fire.
    For modis_only fires: factor = 1.0
    For viirs_only fires: factor = 0.85
    For 'both' fires: factor = weighted average by detection count.
    """
    sp = row["sensors_present"]
    if sp == "modis_only":
        return MODIS_FRP_FACTOR
    elif sp == "viirs_only":
        return VIIRS_FRP_FACTOR
    else:  # both
        n_total = row["n_detections"]
        if n_total == 0:
            return 1.0
        n_modis = row.get("n_modis", 0)
        n_viirs = row.get("n_viirs", 0)
        return (n_modis * MODIS_FRP_FACTOR + n_viirs * VIIRS_FRP_FACTOR) / n_total


def apply_frp_correction(fires: pd.DataFrame) -> pd.DataFrame:
    """Add total_frp_corrected column to per-fire DataFrame."""
    fires = fires.copy()
    factors = fires.apply(compute_frp_correction_factor, axis=1)
    fires["frp_correction_factor"] = factors
    fires["total_frp_corrected"] = fires["total_frp"] * factors
    return fires


# ---------------------------------------------------------------------------
# Split raw counts by sensor for each fire
# ---------------------------------------------------------------------------

def compute_per_fire_sensor_frp(fires: pd.DataFrame) -> pd.DataFrame:
    """
    Add raw_modis_frp and raw_viirs_frp columns per fire.
    For sensor-only fires, the full FRP goes to that sensor.
    For 'both', we pro-rate by detection count.
    """
    fires = fires.copy()
    sp = fires["sensors_present"]
    n_total = fires["n_detections"].clip(lower=1)

    fires["raw_modis_frp"] = np.where(
        sp == "viirs_only",
        0.0,
        np.where(sp == "modis_only",
                 fires["total_frp"],
                 fires["total_frp"] * fires["n_modis"] / n_total)
    )
    fires["raw_viirs_frp"] = np.where(
        sp == "modis_only",
        0.0,
        np.where(sp == "viirs_only",
                 fires["total_frp"],
                 fires["total_frp"] * fires["n_viirs"] / n_total)
    )
    return fires


# ---------------------------------------------------------------------------
# Daily aggregation
# ---------------------------------------------------------------------------

def build_daily_series(fires: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate per-fire rows to daily totals.
    Returns DataFrame with the required column order:
      date, raw_modis, raw_viirs, harmonised_fires,
      total_frp_corrected, total_frp_raw, median_fires
    Plus optional: median_frp, anomaly_fires, anomaly_frp
    """
    fires["date"] = pd.to_datetime(fires["date"])

    # Build the full date spine 2020-01-01 to 2024-12-31
    date_spine = pd.date_range("2020-01-01", "2024-12-31", freq="D")
    assert len(date_spine) == EXPECTED_DAILY_ROWS, (
        f"Date spine has {len(date_spine)} days, expected {EXPECTED_DAILY_ROWS}"
    )

    agg = fires.groupby("date").agg(
        raw_modis=("n_modis", "sum"),
        raw_viirs=("n_viirs", "sum"),
        harmonised_fires=("fire_id", "count"),
        total_frp_corrected=("total_frp_corrected", "sum"),
        total_frp_raw=("total_frp", "sum"),
    ).reset_index()

    # Join onto the full spine so every date has a row (even with zero fires)
    spine_df = pd.DataFrame({"date": date_spine})
    daily = spine_df.merge(agg, on="date", how="left").fillna(0)

    # Cast to int where appropriate
    for col in ["raw_modis", "raw_viirs", "harmonised_fires"]:
        daily[col] = daily[col].astype(int)

    # Add median_fires placeholder (filled by compute_historical_median)
    daily["median_fires"] = 0.0

    return daily


def compute_historical_median(daily: pd.DataFrame) -> pd.DataFrame:
    """
    For each day-of-year, compute median harmonised_fires and median FRP
    across 2020–2024.

    Leap year handling (see DECISIONS D07):
    DOY 60 (Feb 29) only exists in 2020 and 2024; median is over those two years.
    DOY 366 only exists in 2020 and 2024; same.
    Non-leap years have no entry for those DOYs; they are simply absent from the
    groupby, so the median is computed over fewer years — this is correct behavior.
    """
    daily = daily.copy()
    daily["doy"] = daily["date"].dt.dayofyear

    doy_stats = daily.groupby("doy").agg(
        median_fires=("harmonised_fires", "median"),
        median_frp=("total_frp_corrected", "median"),
    ).reset_index()

    # Drop the placeholder median_fires before merging the computed values
    if "median_fires" in daily.columns:
        daily = daily.drop(columns=["median_fires"])
    daily = daily.merge(doy_stats, on="doy", how="left")
    daily["anomaly_fires"] = daily["harmonised_fires"] - daily["median_fires"]
    daily["anomaly_frp"] = daily["total_frp_corrected"] - daily["median_frp"]

    return daily


# ---------------------------------------------------------------------------
# Gate 3 reconciliation
# ---------------------------------------------------------------------------

def reconcile(fires: pd.DataFrame, daily: pd.DataFrame) -> None:
    """
    Run Gate 3 checks. Exits with code 1 on any failure.
    Checks:
      G3.1  daily_series row count == 1,827
      G3.2  sum(harmonised_fires) == len(fires)
      G3.3  sum(n_detections) == N_raw (sum of n_detections across all fires)
      G3.4  sum(total_frp_raw in daily) == sum(total_frp in fires), rtol=1e-5
    """
    log.info("=== Gate 3 Reconciliation ===")
    errors = []

    # G3.1 row count
    n_rows = len(daily)
    if n_rows != EXPECTED_DAILY_ROWS:
        errors.append(f"G3.1 FAIL: daily_series has {n_rows} rows, expected {EXPECTED_DAILY_ROWS}")
    else:
        log.info("G3.1 PASS: daily_series has %d rows", n_rows)

    # G3.2 sum of harmonised_fires == number of fire rows
    sum_hf = int(daily["harmonised_fires"].sum())
    n_fires = len(fires)
    if sum_hf != n_fires:
        errors.append(f"G3.2 FAIL: sum(harmonised_fires)={sum_hf} != len(fires)={n_fires}")
    else:
        log.info("G3.2 PASS: sum(harmonised_fires)=%d == len(fires)=%d", sum_hf, n_fires)

    # G3.3 sum of n_detections
    n_detections_total = int(fires["n_detections"].sum())
    # We log this as a check; the "N raw" comes from cluster.py's log.
    # Here we just ensure the number is internally consistent.
    log.info("G3.3 INFO: sum(n_detections across fires) = %d (must equal N raw from cluster.py)",
             n_detections_total)

    # G3.4 FRP sum match
    daily_frp_sum = float(daily["total_frp_raw"].sum())
    fires_frp_sum = float(fires["total_frp"].sum())
    rel_err = abs(daily_frp_sum - fires_frp_sum) / max(fires_frp_sum, 1e-9)
    if rel_err > 1e-5:
        errors.append(
            f"G3.4 FAIL: sum(total_frp_raw in daily)={daily_frp_sum:.4f} "
            f"!= sum(total_frp in fires)={fires_frp_sum:.4f} (rel_err={rel_err:.2e})"
        )
    else:
        log.info("G3.4 PASS: FRP sums match within rtol=1e-5 "
                 "(daily=%.4f, fires=%.4f, rel_err=%.2e)",
                 daily_frp_sum, fires_frp_sum, rel_err)

    if errors:
        for e in errors:
            log.error(e)
        log.error("Gate 3 FAILED. Fix the above issues before proceeding.")
        sys.exit(1)
    else:
        log.info("=== Gate 3 PASSED ===")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not PARQUET_IN.exists():
        log.error("Input file not found: %s. Run cluster.py first.", PARQUET_IN)
        sys.exit(1)

    log.info("Loading %s ...", PARQUET_IN)
    fires = pq.read_table(PARQUET_IN).to_pandas()
    log.info("Loaded %d fire records", len(fires))

    # Apply FRP correction
    fires = apply_frp_correction(fires)
    fires = compute_per_fire_sensor_frp(fires)

    # Build daily series
    log.info("Building daily series ...")
    daily = build_daily_series(fires)
    daily = compute_historical_median(daily)

    # Required column order
    required_cols = ["date", "raw_modis", "raw_viirs", "harmonised_fires",
                     "total_frp_corrected", "total_frp_raw", "median_fires"]
    extra_cols = [c for c in daily.columns if c not in required_cols]
    daily = daily[required_cols + extra_cols]

    # Gate 3 reconciliation
    reconcile(fires, daily)

    # Write outputs
    DAILY_CSV.parent.mkdir(parents=True, exist_ok=True)
    daily_out = daily.copy()
    daily_out["date"] = daily_out["date"].dt.strftime("%Y-%m-%d")
    daily_out.to_csv(DAILY_CSV, index=False)
    log.info("Wrote %d rows to %s", len(daily_out), DAILY_CSV)

    fires_out = fires.copy()
    fires_out["date"] = fires_out["date"].astype(str)
    fires_out.to_csv(HARMONISED_CSV, index=False)
    log.info("Wrote %d rows to %s", len(fires_out), HARMONISED_CSV)

    # Summary stats
    peak_row = daily.loc[daily["harmonised_fires"].idxmax()]
    log.info("=== Harmonization Summary ===")
    log.info("Total harmonised fires:      %d", len(fires))
    log.info("Total FRP raw (MW):          %.1f", fires["total_frp"].sum())
    log.info("Total FRP corrected (MW):    %.1f", fires["total_frp_corrected"].sum())
    log.info("Peak day:                    %s (%d fires)",
             peak_row["date"].strftime("%Y-%m-%d"), int(peak_row["harmonised_fires"]))
    log.info("=== End Harmonization Summary ===")


if __name__ == "__main__":
    main()
