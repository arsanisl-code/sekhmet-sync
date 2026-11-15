"""
build_daily_harmonized.py — Build daily harmonised series and harmonised detections

Inputs:
  - 12 raw California CSV files in data/raw/ (2020–2024)
  - data/california.geojson (California state boundary polygon)

Outputs:
  - data/daily_series_harmonised.csv (1,827 rows)
  - data/harmonised_detections.csv (surviving harmonised detections)

Method:
  - MODIS C6.1: confidence >= 30, counted as-is
  - VIIRS NOAA-20/21: confidence != 'l', FRP >= 6.5 MW (experimental threshold)
  - Boundary: Point-in-polygon with California state boundary
"""

import sys
import json
import logging
from pathlib import Path
from datetime import date

import pandas as pd
import numpy as np
from shapely.geometry import shape, Point

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_daily_harmonized")

DATA_RAW = Path("data/raw")
CA_GEOJSON = Path("data/california.geojson")
OUT_DAILY = Path("data/daily_series_harmonised.csv")
OUT_DETECTIONS = Path("data/harmonised_detections.csv")

EXPECTED_SPINE_DAYS = 1827  # 366 (2020) + 365 (2021) + 365 (2022) + 365 (2023) + 366 (2024)

def load_ca_polygon():
    if not CA_GEOJSON.exists():
        raise FileNotFoundError(f"Missing {CA_GEOJSON}")
    data = json.loads(CA_GEOJSON.read_text())
    return shape(data["features"][0]["geometry"])

def map_satellite(sat_str, sensor_type):
    s = str(sat_str).strip()
    if sensor_type == "MODIS":
        if s in ["T", "Terra", "1"]:
            return "Terra"
        elif s in ["A", "Aqua", "2"]:
            return "Aqua"
        return s
    else:  # VIIRS
        if s in ["N20", "NOAA-20", "JPSS-1", "1"]:
            return "NOAA20"
        elif s in ["N21", "NOAA-21", "JPSS-2", "2"]:
            return "NOAA21"
        elif s in ["NPP", "SNPP", "Suomi-NPP"]:
            return "SNPP"
        return s

def main():
    log.info("Loading California polygon boundary...")
    ca_poly = load_ca_polygon()

    # 1. Load raw files
    modis_files = sorted(DATA_RAW.glob("MODIS_SP_202*.csv"))
    viirs_n20_files = sorted(DATA_RAW.glob("VIIRS_NOAA20_SP_202*.csv"))
    viirs_n21_files = sorted(DATA_RAW.glob("VIIRS_NOAA21_SP_202*.csv"))

    log.info("Found %d MODIS files, %d NOAA-20 files, %d NOAA-21 files",
             len(modis_files), len(viirs_n20_files), len(viirs_n21_files))

    raw_counts = {}
    
    # Process MODIS
    m_dfs = []
    for f in modis_files:
        df = pd.read_csv(f)
        raw_counts[f.name] = len(df)
        m_dfs.append(df)
    raw_modis = pd.concat(m_dfs, ignore_index=True)

    # Process VIIRS NOAA-20
    v20_dfs = []
    for f in viirs_n20_files:
        df = pd.read_csv(f)
        raw_counts[f.name] = len(df)
        v20_dfs.append(df)
    raw_v20 = pd.concat(v20_dfs, ignore_index=True)

    # Process VIIRS NOAA-21
    v21_dfs = []
    for f in viirs_n21_files:
        df = pd.read_csv(f)
        raw_counts[f.name] = len(df)
        v21_dfs.append(df)
    raw_v21 = pd.concat(v21_dfs, ignore_index=True)

    total_raw_rows = len(raw_modis) + len(raw_v20) + len(raw_v21)
    log.info("=== RAW INGESTION AUDIT ===")
    log.info("Raw MODIS rows:    %7d (Expected 117,770)", len(raw_modis))
    log.info("Raw NOAA-20 rows:  %7d (Expected 553,074)", len(raw_v20))
    log.info("Raw NOAA-21 rows:  %7d (Expected  81,766)", len(raw_v21))
    log.info("Total Raw rows:    %7d (Expected 752,610)", total_raw_rows)

    # 2. Confidence Filtering Audit
    modis_conf_mask = raw_modis["confidence"].astype(float) >= 30
    v20_conf_mask = raw_v20["confidence"].astype(str).str.lower() != "l"
    v21_conf_mask = raw_v21["confidence"].astype(str).str.lower() != "l"

    m_conf = raw_modis[modis_conf_mask].copy()
    v20_conf = raw_v20[v20_conf_mask].copy()
    v21_conf = raw_v21[v21_conf_mask].copy()

    total_conf_passed = len(m_conf) + len(v20_conf) + len(v21_conf)
    dropped_conf = total_raw_rows - total_conf_passed
    log.info("=== CONFIDENCE FILTER AUDIT ===")
    log.info("MODIS confidence >= 30:        %7d (dropped %d)", len(m_conf), len(raw_modis) - len(m_conf))
    log.info("NOAA-20 confidence != 'l':     %7d (dropped %d)", len(v20_conf), len(raw_v20) - len(v20_conf))
    log.info("NOAA-21 confidence != 'l':     %7d (dropped %d)", len(v21_conf), len(raw_v21) - len(v21_conf))
    log.info("Total Post-Confidence filter:  %7d (dropped %d, expected 751,293 post-conf/FRP)",
             total_conf_passed, dropped_conf)

    # Check zero/negative FRP in post-confidence data
    m_zero_frp = (m_conf["frp"] <= 0).sum()
    v20_zero_frp = (v20_conf["frp"] <= 0).sum()
    v21_zero_frp = (v21_conf["frp"] <= 0).sum()
    total_zero_frp = m_zero_frp + v20_zero_frp + v21_zero_frp
    log.info("Zero or negative FRP rows in post-confidence: %d (MODIS: %d, N20: %d, N21: %d)",
             total_zero_frp, m_zero_frp, v20_zero_frp, v21_zero_frp)

    # Combine VIIRS
    raw_viirs_conf = pd.concat([v20_conf, v21_conf], ignore_index=True)

    # 3. Polygon Filtering Audit
    log.info("Applying California polygon boundary filter...")
    m_in_ca = m_conf.apply(lambda r: ca_poly.contains(Point(r["longitude"], r["latitude"])), axis=1)
    v_in_ca = raw_viirs_conf.apply(lambda r: ca_poly.contains(Point(r["longitude"], r["latitude"])), axis=1)

    m_ca = m_conf[m_in_ca].copy()
    v_ca = raw_viirs_conf[v_in_ca].copy()

    in_state_modis = len(m_ca)
    in_state_viirs_raw = len(v_ca)
    in_state_total_raw = in_state_modis + in_state_viirs_raw

    log.info("=== IN-STATE POLYGON FILTER AUDIT ===")
    log.info("In-state MODIS detections:     %7d", in_state_modis)
    log.info("In-state VIIRS raw detections: %7d", in_state_viirs_raw)
    log.info("Total In-State Raw detections: %7d", in_state_total_raw)
    log.info("Reconciliation comparison:")
    log.info("  vs 721,169 (earlier cluster-centroid filter): delta = %+d (%+.3f%%)",
             in_state_total_raw - 721169, (in_state_total_raw - 721169) / 721169 * 100)
    log.info("  vs 722,589 (P3 cell-center filter):          delta = %+d (%+.3f%%)",
             in_state_total_raw - 722589, (in_state_total_raw - 722589) / 722589 * 100)

    # 4. VIIRS FRP Threshold Harmonization (FRP >= 6.5 MW)
    v_ca_harmonised = v_ca[v_ca["frp"] >= 6.5].copy()
    in_state_viirs_harm = len(v_ca_harmonised)
    v_filtered_out = in_state_viirs_raw - in_state_viirs_harm
    pct_viirs_filtered = v_filtered_out / in_state_viirs_raw * 100
    pct_total_raw_filtered = (in_state_total_raw - (in_state_modis + in_state_viirs_harm)) / in_state_total_raw * 100

    log.info("=== HARMONIZATION THRESHOLD AUDIT (FRP >= 6.5 MW) ===")
    log.info("VIIRS kept (FRP >= 6.5 MW):        %7d (%.1f%% of raw VIIRS)",
             in_state_viirs_harm, in_state_viirs_harm / in_state_viirs_raw * 100)
    log.info("VIIRS filtered out (< 6.5 MW):     %7d (%.1f%% of raw VIIRS)",
             v_filtered_out, pct_viirs_filtered)
    log.info("Harmonised Total (MODIS + VIIRS):  %7d", in_state_modis + in_state_viirs_harm)
    log.info("Total raw filtered:                %7d (%.1f%% of total in-state raw)",
             v_filtered_out, pct_total_raw_filtered)

    # 5. Build Daily Aggregates on 1,827-day Spine
    log.info("Building 1,827-day spine and daily aggregation...")
    m_ca["date"] = pd.to_datetime(m_ca["acq_date"])
    v_ca["date"] = pd.to_datetime(v_ca["acq_date"])
    v_ca_harmonised["date"] = pd.to_datetime(v_ca_harmonised["acq_date"])

    daily_m = m_ca.groupby("date").size().rename("raw_modis_hotspots")
    daily_v = v_ca.groupby("date").size().rename("raw_viirs_hotspots")
    daily_v_harm = v_ca_harmonised.groupby("date").size().rename("harm_viirs")

    spine = pd.date_range("2020-01-01", "2024-12-31", freq="D")
    daily_df = pd.DataFrame({"date": spine}).set_index("date")
    daily_df = daily_df.join(daily_m).join(daily_v).join(daily_v_harm).fillna(0).astype(int)

    daily_df["harmonised_hotspots"] = daily_df["raw_modis_hotspots"] + daily_df["harm_viirs"]

    # Compute 5-year day-of-year median
    daily_df["doy"] = daily_df.index.dayofyear
    doy_median = daily_df.groupby("doy")["harmonised_hotspots"].median().rename("median_hotspots")
    daily_df = daily_df.join(doy_median, on="doy")
    daily_df["anomaly_hotspots"] = daily_df["harmonised_hotspots"] - daily_df["median_hotspots"]

    # Format output daily CSV
    daily_out = daily_df.reset_index()
    daily_out["date"] = daily_out["date"].dt.strftime("%Y-%m-%d")
    daily_out = daily_out[[
        "date",
        "raw_modis_hotspots",
        "raw_viirs_hotspots",
        "harmonised_hotspots",
        "median_hotspots",
        "anomaly_hotspots"
    ]]

    assert len(daily_out) == EXPECTED_SPINE_DAYS, f"Expected {EXPECTED_SPINE_DAYS} rows, got {len(daily_out)}"
    daily_out.to_csv(OUT_DAILY, index=False)
    log.info("Saved %s with %d rows", OUT_DAILY, len(daily_out))

    # Peak Day Audit
    peak_idx = daily_df["harmonised_hotspots"].idxmax()
    peak_date = peak_idx.strftime("%Y-%m-%d")
    peak_count = int(daily_df.loc[peak_idx, "harmonised_hotspots"])
    peak_raw_m = int(daily_df.loc[peak_idx, "raw_modis_hotspots"])
    peak_raw_v = int(daily_df.loc[peak_idx, "raw_viirs_hotspots"])
    log.info("=== PEAK DAY AUDIT ===")
    log.info("Peak Day: %s with %d harmonised hotspots (MODIS raw: %d, VIIRS raw: %d)",
             peak_date, peak_count, peak_raw_m, peak_raw_v)

    # 6. Build Compact Harmonised Detections CSV
    log.info("Writing compact harmonised detections CSV (%s)...", OUT_DETECTIONS)
    m_ca["sensor"] = "MODIS"
    m_ca["satellite"] = m_ca["satellite"].apply(lambda s: map_satellite(s, "MODIS"))
    
    v_ca_harmonised["sensor"] = "VIIRS"
    v_ca_harmonised["satellite"] = v_ca_harmonised["satellite"].apply(lambda s: map_satellite(s, "VIIRS"))

    keep_cols = ["acq_date", "latitude", "longitude", "frp", "sensor", "satellite"]
    m_slim = m_ca[keep_cols].copy()
    v_slim = v_ca_harmonised[keep_cols].copy()

    det_combined = pd.concat([m_slim, v_slim], ignore_index=True)
    det_combined.rename(columns={"acq_date": "date"}, inplace=True)
    det_combined["date"] = pd.to_datetime(det_combined["date"]).dt.strftime("%Y-%m-%d")
    det_combined["latitude"] = det_combined["latitude"].round(4)
    det_combined["longitude"] = det_combined["longitude"].round(4)
    det_combined["frp"] = det_combined["frp"].round(1)

    det_combined = det_combined.sort_values(by=["date", "latitude", "longitude"]).reset_index(drop=True)
    det_combined.to_csv(OUT_DETECTIONS, index=False)
    log.info("Saved %s with %d rows", OUT_DETECTIONS, len(det_combined))

    daily_size_kb = OUT_DAILY.stat().st_size / 1024
    det_size_mb = OUT_DETECTIONS.stat().st_size / (1024 * 1024)
    log.info("File sizes: %s = %.1f KB | %s = %.2f MB",
             OUT_DAILY.name, daily_size_kb, OUT_DETECTIONS.name, det_size_mb)

    # Final summary check
    print("\n" + "="*80)
    print("PHASE 1 EXECUTION COMPLETE — RECONCILIATION SUMMARY")
    print("="*80)
    print(f"Spine length:                  {len(daily_out)} days (2020-01-01 to 2024-12-31)")
    print(f"Missing dates:                 0")
    print(f"Raw Input Rows:                {total_raw_rows:,}")
    print(f"Post-Confidence Rows:          {total_conf_passed:,}")
    print(f"In-State Raw Hotspots:         {in_state_total_raw:,} (MODIS: {in_state_modis:,}, VIIRS: {in_state_viirs_raw:,})")
    print(f"Delta vs 721,169 (Clustered):  {in_state_total_raw - 721169:+,d} ({((in_state_total_raw - 721169)/721169)*100:+.3f}%)")
    print(f"Delta vs 722,589 (Cell Cent):  {in_state_total_raw - 722589:+,d} ({((in_state_total_raw - 722589)/722589)*100:+.3f}%)")
    print(f"Harmonised In-State Hotspots:  {len(det_combined):,} (MODIS: {in_state_modis:,}, VIIRS >=6.5MW: {in_state_viirs_harm:,})")
    print(f"VIIRS Sensitivity Filtered:    {v_filtered_out:,} ({pct_viirs_filtered:.1f}% of VIIRS, {pct_total_raw_filtered:.1f}% of all raw)")
    print(f"Peak Harmonised Day:           {peak_date} with {peak_count:,} hotspots (MODIS: {peak_raw_m:,}, VIIRS raw: {peak_raw_v:,})")
    print(f"Output Sizes:                  {OUT_DAILY.name} ({daily_size_kb:.1f} KB), {OUT_DETECTIONS.name} ({det_size_mb:.2f} MB)")
    print("="*80)

if __name__ == "__main__":
    main()
