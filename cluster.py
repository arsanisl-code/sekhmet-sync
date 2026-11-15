"""
cluster.py — Sekhmet Sync spatial deduplication

Reads all FIRMS CSVs from data/raw/, merges them into a unified schema,
and clusters same-day detections within ~1 km of each other into single fire records.

Algorithm: KDTree + union-find, O(n log n). See DECISIONS D03.
Outputs: data/ca_2020_2024.parquet

Usage:
    python cluster.py              # full run
    python cluster.py --sample 0.5 # run on 50% sample (for scaling test)
    python cluster.py --input-files data/raw/MODIS_SP_2020.csv ...  # explicit files
"""

import sys
import time
import logging
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.spatial import KDTree
from shapely.geometry import shape, Point

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cluster")

DATA_RAW = Path("data/raw")
OUT_PARQUET = Path("data/ca_2020_2024.parquet")
CA_GEOJSON = Path("data/california.geojson")

# 1 km in degrees latitude (constant). Longitude degree varies by latitude;
# at 36°N (mid-CA): 1 km ≈ 0.01125° lon. Using 0.009° as the uniform threshold
# is slightly conservative at the equator side and slightly aggressive at the pole
# side, but the error is < 3% across the CA bounding box. See DECISIONS D03.
CLUSTER_RADIUS_DEG = 0.009  # ≈ 1 km


def load_ca_polygon():
    """Load California state boundary polygon for centroid filtering."""
    import json
    if not CA_GEOJSON.exists():
        log.warning("California GeoJSON not found at %s — skipping polygon filter", CA_GEOJSON)
        return None
    data = json.loads(CA_GEOJSON.read_text())
    return shape(data["features"][0]["geometry"])


def filter_to_california(fires_df: pd.DataFrame, ca_poly) -> pd.DataFrame:
    """
    Drop fire records whose centroid falls outside California state boundary.
    Applied after clustering so a fire is kept if its centroid is in CA,
    even if individual detections straddled the border.
    Logs how many records were dropped.
    """
    if ca_poly is None:
        return fires_df

    before = len(fires_df)
    mask = fires_df.apply(
        lambda r: ca_poly.contains(Point(r["centroid_lon"], r["centroid_lat"])),
        axis=1,
    )
    filtered = fires_df[mask].copy()
    dropped = before - len(filtered)
    log.info(
        "California polygon filter: kept %d fires, dropped %d (%.1f%%) "
        "with centroids outside CA state boundary",
        len(filtered), dropped, dropped / before * 100 if before else 0,
    )
    return filtered

# 1 km in degrees latitude (constant). Longitude degree varies by latitude;
# at 36°N (mid-CA): 1 km ≈ 0.01125° lon. Using 0.009° as the uniform threshold
# is slightly conservative at the equator side and slightly aggressive at the pole
# side, but the error is < 3% across the CA bounding box. See DECISIONS D03.
CLUSTER_RADIUS_DEG = 0.009  # ≈ 1 km

# ---------------------------------------------------------------------------
# Column mapping: unify MODIS and VIIRS schemas
# ---------------------------------------------------------------------------

# MODIS columns: latitude, longitude, brightness, scan, track, acq_date, acq_time,
#   satellite, instrument, confidence, version, bright_t31, frp, daynight, type
# VIIRS columns: latitude, longitude, bright_ti4, scan, track, acq_date, acq_time,
#   satellite, instrument, confidence, version, bright_ti5, frp, daynight, type
# See DECISIONS document and design.md for the full mapping rationale.

SHARED_COLS = ["latitude", "longitude", "scan", "track", "acq_date", "acq_time",
               "satellite", "instrument", "confidence", "frp", "daynight"]

MODIS_PRODUCTS = {"MODIS_SP"}
VIIRS_PRODUCTS = {"VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP"}


def infer_product(filepath: Path) -> str:
    """Infer the FIRMS product code from the filename."""
    name = filepath.stem  # e.g. MODIS_SP_2020
    if name.startswith("MODIS_SP"):
        return "MODIS_SP"
    elif name.startswith("VIIRS_NOAA21"):
        return "VIIRS_NOAA21_SP"
    elif name.startswith("VIIRS_NOAA20"):
        return "VIIRS_NOAA20_SP"
    raise ValueError(f"Cannot infer product from filename: {filepath}")


def load_and_unify(filepath: Path) -> pd.DataFrame:
    """
    Load one FIRMS CSV and map it to the unified schema.
    Returns an empty DataFrame if the file is empty or unreadable.
    """
    product = infer_product(filepath)
    try:
        df = pd.read_csv(filepath, low_memory=False)
    except Exception as e:
        log.error("Could not read %s: %s", filepath, e)
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # Brightness column unification
    if product in MODIS_PRODUCTS:
        df = df.rename(columns={
            "brightness": "brightness_mid",
            "bright_t31": "brightness_lwir",
        })
        df["sensor_type"] = "modis"
    else:  # VIIRS
        df = df.rename(columns={
            "bright_ti4": "brightness_mid",
            "bright_ti5": "brightness_lwir",
        })
        df["sensor_type"] = "viirs"

    df["source_product"] = product
    df["confidence_raw"] = df["confidence"].astype(str)

    # Keep only the columns we need
    keep = SHARED_COLS + ["brightness_mid", "brightness_lwir",
                           "sensor_type", "source_product", "confidence_raw"]
    # Drop columns not present (graceful)
    keep = [c for c in keep if c in df.columns]
    df = df[keep].copy()

    # Parse date
    df["acq_date"] = pd.to_datetime(df["acq_date"]).dt.date

    # Parse FRP as float; drop rows where FRP is null or zero (no thermal signal)
    df["frp"] = pd.to_numeric(df["frp"], errors="coerce")
    df = df[df["frp"].notna() & (df["frp"] > 0)].copy()

    # Ensure lat/lon are float
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])

    return df


# ---------------------------------------------------------------------------
# Union-find (path compression + union by rank)
# ---------------------------------------------------------------------------

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # path compression
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


# ---------------------------------------------------------------------------
# Clustering core
# ---------------------------------------------------------------------------

def cluster_day(day_df: pd.DataFrame, date_str: str) -> pd.DataFrame:
    """
    Cluster detections for one UTC date.
    Returns a DataFrame of fire records with the required output schema.

    Time complexity: O(n log n) KDTree build + O(n k) queries.
    See DECISIONS D03 for full complexity analysis.
    """
    if day_df.empty:
        return pd.DataFrame()

    coords = day_df[["latitude", "longitude"]].values.astype(np.float64)
    n = len(coords)

    if n == 1:
        # Single detection — trivially one fire
        row = day_df.iloc[0]
        return pd.DataFrame([{
            "date": date_str,
            "centroid_lat": float(row["latitude"]),
            "centroid_lon": float(row["longitude"]),
            "n_detections": 1,
            "n_modis": 1 if row.get("sensor_type") == "modis" else 0,
            "n_viirs": 1 if row.get("sensor_type") == "viirs" else 0,
            "sensors_present": (
                "modis_only" if row.get("sensor_type") == "modis" else "viirs_only"
            ),
            "total_frp": float(row["frp"]),
            "max_frp": float(row["frp"]),
            "mean_brightness": float(row.get("brightness_mid", np.nan)),
            "first_acq_time": str(row.get("acq_time", "")),
            "last_acq_time": str(row.get("acq_time", "")),
        }])

    tree = KDTree(coords)
    # Query all pairs within CLUSTER_RADIUS_DEG
    # Returns list of lists: neighbors[i] = indices of points within radius of i
    neighbors = tree.query_ball_tree(tree, r=CLUSTER_RADIUS_DEG)

    uf = UnionFind(n)
    for i, nbrs in enumerate(neighbors):
        for j in nbrs:
            if j != i:
                uf.union(i, j)

    # Build component map: root → list of indices
    from collections import defaultdict
    components: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        components[uf.find(i)].append(i)

    records = []
    day_df_reset = day_df.reset_index(drop=True)

    for indices in components.values():
        sub = day_df_reset.iloc[indices]
        n_modis = int((sub["sensor_type"] == "modis").sum())
        n_viirs = int((sub["sensor_type"] == "viirs").sum())
        if n_modis > 0 and n_viirs > 0:
            sensors_present = "both"
        elif n_modis > 0:
            sensors_present = "modis_only"
        else:
            sensors_present = "viirs_only"

        brightness_vals = pd.to_numeric(sub["brightness_mid"], errors="coerce")
        acq_times = sub["acq_time"].astype(str).sort_values()

        records.append({
            "date": date_str,
            "centroid_lat": float(sub["latitude"].mean()),
            "centroid_lon": float(sub["longitude"].mean()),
            "n_detections": len(indices),
            "n_modis": n_modis,
            "n_viirs": n_viirs,
            "sensors_present": sensors_present,
            "total_frp": float(sub["frp"].sum()),
            "max_frp": float(sub["frp"].max()),
            "mean_brightness": float(brightness_vals.mean()) if brightness_vals.notna().any() else np.nan,
            "first_acq_time": acq_times.iloc[0] if len(acq_times) > 0 else "",
            "last_acq_time": acq_times.iloc[-1] if len(acq_times) > 0 else "",
        })

    return pd.DataFrame(records)


def assign_fire_ids(fires_df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign fire_id in format CA-YYYY-MM-DD-NNN, sequential within each date.
    Sorted by date then centroid_lat descending (north-to-south ordering).
    """
    if fires_df.empty:
        return fires_df

    fires_df = fires_df.sort_values(
        ["date", "centroid_lat"], ascending=[True, False]
    ).copy()

    ids = []
    # Group by date and assign sequential NNN
    for date_val, grp in fires_df.groupby("date", sort=False):
        for seq, idx in enumerate(grp.index, start=1):
            ids.append((idx, f"CA-{date_val}-{seq:03d}"))

    id_series = pd.Series({idx: fid for idx, fid in ids}, name="fire_id")
    fires_df.insert(0, "fire_id", id_series)
    return fires_df


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(input_files: list[Path], sample_frac: float = 1.0) -> pd.DataFrame:
    """
    Load all input files, cluster, and return the fires DataFrame.
    """
    log.info("Loading %d input files ...", len(input_files))
    dfs = []
    for f in input_files:
        df = load_and_unify(f)
        if not df.empty:
            dfs.append(df)
            log.info("  Loaded %-35s  %d rows", f.name, len(df))

    if not dfs:
        log.error("No data loaded from input files. Cannot cluster.")
        sys.exit(1)

    all_detections = pd.concat(dfs, ignore_index=True)
    n_raw = len(all_detections)
    log.info("Total raw detections (post-filter): %d", n_raw)

    if sample_frac < 1.0:
        all_detections = all_detections.sample(frac=sample_frac, random_state=42)
        log.info("Sample (%.0f%%): %d detections", sample_frac * 100, len(all_detections))
        n_raw = len(all_detections)

    # Sort by date for groupby efficiency
    all_detections = all_detections.sort_values("acq_date")
    dates = sorted(all_detections["acq_date"].unique())
    log.info("Clustering %d unique dates ...", len(dates))

    fire_chunks: list[pd.DataFrame] = []
    t0 = time.perf_counter()

    for d in dates:
        day_df = all_detections[all_detections["acq_date"] == d]
        date_str = str(d)
        fires = cluster_day(day_df, date_str)
        if not fires.empty:
            fire_chunks.append(fires)

    t1 = time.perf_counter()
    runtime = t1 - t0

    if not fire_chunks:
        log.error("No fires produced. Check input data.")
        sys.exit(1)

    fires_df = pd.concat(fire_chunks, ignore_index=True)

    # Filter centroids to California state boundary (before assigning IDs
    # so numbering is clean and sequential within each day)
    ca_poly = load_ca_polygon()
    fires_df = filter_to_california(fires_df, ca_poly)

    fires_df = assign_fire_ids(fires_df)

    m_fires = len(fires_df)
    pct_removed = (n_raw - m_fires) / n_raw * 100 if n_raw > 0 else 0.0

    log.info("=== Gate 2 Report ===")
    log.info("N raw detections (post-filter):  %d", n_raw)
    log.info("M harmonised fires:              %d", m_fires)
    log.info("%% removed (N-M)/N*100:           %.1f%%", pct_removed)
    log.info("Runtime:                         %.2f seconds", runtime)
    log.info("=== End Gate 2 Report ===")

    return fires_df


def save_parquet(fires_df: pd.DataFrame, out_path: Path) -> None:
    """Save fires DataFrame to Parquet."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fires_df["date"] = fires_df["date"].astype(str)
    table = pa.Table.from_pandas(fires_df, preserve_index=False)
    pq.write_table(table, out_path, compression="snappy")
    log.info("Wrote %d fire records to %s", len(fires_df), out_path)


def run_scaling_test(input_files: list[Path]) -> None:
    """
    Run clustering on 50% and 100% of input, report runtime ratio.
    Demonstrates sub-quadratic growth (Gate 2 requirement).
    """
    log.info("=== Scaling test: 50%% sample ===")
    t0 = time.perf_counter()
    run_pipeline(input_files, sample_frac=0.5)
    t50 = time.perf_counter() - t0

    log.info("=== Scaling test: 100%% sample ===")
    t0 = time.perf_counter()
    run_pipeline(input_files, sample_frac=1.0)
    t100 = time.perf_counter() - t0

    ratio = t100 / t50 if t50 > 0 else float("inf")
    log.info("Scaling result: t50=%.2fs  t100=%.2fs  ratio=%.2f (expected < 2.0 for sub-quadratic)",
             t50, t100, ratio)
    if ratio < 2.0:
        log.info("PASS: ratio %.2f < 2.0 — sub-quadratic growth confirmed.", ratio)
    else:
        log.warning("CAUTION: ratio %.2f >= 2.0. Check for O(n²) paths in hot dates.", ratio)


def main():
    parser = argparse.ArgumentParser(description="Sekhmet Sync clustering pipeline")
    parser.add_argument("--sample", type=float, default=1.0,
                        help="Fraction of data to use (0.0–1.0). Default: 1.0")
    parser.add_argument("--scaling-test", action="store_true",
                        help="Run 50%% and 100%% samples to demonstrate scaling")
    parser.add_argument("--input-files", nargs="+",
                        help="Explicit list of CSV files to cluster")
    parser.add_argument("--output", default=str(OUT_PARQUET),
                        help=f"Output Parquet path (default: {OUT_PARQUET})")
    args = parser.parse_args()

    if args.input_files:
        input_files = [Path(f) for f in args.input_files]
    else:
        input_files = sorted(f for f in DATA_RAW.glob("*.csv") if "_disc_" not in f.name)

    if not input_files:
        log.error("No CSV files found in %s. Run fetch_firms.py first.", DATA_RAW)
        sys.exit(1)

    if args.scaling_test:
        run_scaling_test(input_files)
        return

    fires_df = run_pipeline(input_files, sample_frac=args.sample)

    out_path = Path(args.output)
    save_parquet(fires_df, out_path)

    log.info("Clustering complete. Output: %s", out_path)


if __name__ == "__main__":
    main()
