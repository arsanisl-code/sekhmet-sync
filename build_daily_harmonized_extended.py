"""
build_daily_harmonized_extended.py
===================================
Builds the extended harmonised daily series 2000-11-01 to 2024-12-31.

RULES (identical to build_daily_harmonized.py for the 2020-2024 baseline):
  MODIS:  confidence >= 30, counted as-is (no FRP filter)
  VIIRS:  confidence != 'l' AND frp >= 6.5 MW
  Clip:   point-in-polygon against data/california.geojson BEFORE counting
  NO clustering, NO 0.85 factor, NO Sofiev operator, NO NRT

Threshold label:
  "VIIRS >=6.5 MW threshold - experimental, fitted on California 2012-2013 monthly
   overlap (r=0.9974, monthly only). Not validated on daily data or outside California."

Outputs (NEW files, do NOT overwrite frozen files):
  data/daily_series_harmonised_extended.csv
  data/harmonised_detections_extended.csv
  data/raw_extended/MANIFEST_EXTENDED.md

Gate 2: 2020-2024 sum must equal 347,174 and peak must be 2020-09-09 / 10,320.
Gate 3: daily sum == detections rows.
"""

import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import shape, Point

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_ext")

CA_GEOJSON     = Path("data/california.geojson")
RAW_DIR        = Path("data/raw")
EXT_DIR        = Path("data/raw_extended")
OUT_DAILY      = Path("data/daily_series_harmonised_extended.csv")
OUT_DETECTIONS = Path("data/harmonised_detections_extended.csv")
OUT_MANIFEST   = Path("data/raw_extended/MANIFEST_EXTENDED.md")

FROZEN_HARM_TOTAL = 347_174
FROZEN_PEAK_DATE  = "2020-09-09"
FROZEN_PEAK_COUNT = 10_320


def constellation_meta(year):
    if year <= 2001:
        return {"era": "Terra-only",                     "n_satellites_viirs": 0, "n_satellites_total": 1}
    elif year <= 2011:
        return {"era": "Terra+Aqua",                     "n_satellites_viirs": 0, "n_satellites_total": 2}
    elif year <= 2017:
        return {"era": "Terra+Aqua+S-NPP",               "n_satellites_viirs": 1, "n_satellites_total": 3}
    elif year <= 2022:
        return {"era": "Terra+Aqua+S-NPP+NOAA-20",       "n_satellites_viirs": 2, "n_satellites_total": 4}
    else:
        return {"era": "Terra+Aqua+NOAA-20+NOAA-21",     "n_satellites_viirs": 2, "n_satellites_total": 4}


def satnorm_div(year):
    n = constellation_meta(year)["n_satellites_viirs"]
    return float(n) if n > 0 else 1.0


def map_satellite(sat, sensor):
    s = str(sat).strip()
    if sensor == "MODIS":
        if s in ("T", "Terra", "1"):   return "Terra"
        if s in ("A", "Aqua",  "2"):   return "Aqua"
        return s
    else:
        if s in ("N20", "NOAA-20", "JPSS-1", "1"):  return "NOAA20"
        if s in ("N21", "NOAA-21", "JPSS-2", "2"):  return "NOAA21"
        if s in ("N",   "NPP",  "SNPP", "Suomi-NPP"): return "SNPP"
        return s


def clip_ca(df, ca_poly):
    mask = [ca_poly.contains(Point(lo, la))
            for lo, la in zip(df["longitude"].values, df["latitude"].values)]
    return df[mask].copy()


def process_modis(path, ca_poly):
    df = pd.read_csv(path, low_memory=False)
    raw = len(df)
    df = df[df["confidence"].astype(float) >= 30].copy()
    conf_drop = raw - len(df)
    df["frp"] = pd.to_numeric(df["frp"], errors="coerce")
    df_ca = clip_ca(df, ca_poly)
    oos = len(df) - len(df_ca)
    return df_ca, {"raw": raw, "conf_drop": conf_drop, "oos": oos, "in_state": len(df_ca)}


def process_viirs(path, ca_poly):
    df = pd.read_csv(path, low_memory=False)
    raw = len(df)
    df = df[df["confidence"].astype(str).str.strip().str.lower() != "l"].copy()
    conf_drop = raw - len(df)
    df["frp"] = pd.to_numeric(df["frp"], errors="coerce")
    df_ca = clip_ca(df, ca_poly)
    oos = len(df) - len(df_ca)
    df_harm = df_ca[df_ca["frp"] >= 6.5].copy()
    thresh_drop = len(df_ca) - len(df_harm)
    return df_harm, {"raw": raw, "conf_drop": conf_drop, "oos": oos,
                     "in_state": len(df_ca), "thresh_drop": thresh_drop}


def to_det(df, sensor):
    if df is None or df.empty:
        return pd.DataFrame(columns=["date","latitude","longitude","frp","sensor","satellite"])
    return pd.DataFrame({
        "date":      pd.to_datetime(df["acq_date"]).dt.strftime("%Y-%m-%d"),
        "latitude":  df["latitude"].round(4).values,
        "longitude": df["longitude"].round(4).values,
        "frp":       df["frp"].round(1).values,
        "sensor":    sensor,
        "satellite": df["satellite"].apply(lambda s: map_satellite(s, sensor)).values,
    })


def main():
    t0 = datetime.now(timezone.utc)
    log.info("Loading California polygon...")
    ca_poly = shape(json.loads(CA_GEOJSON.read_text())["features"][0]["geometry"])

    det_parts  = []
    year_stats = {}

    # --- 2000-2010: MODIS only ---
    for yr in range(2000, 2011):
        p = EXT_DIR / f"MODIS_SP_{yr}.csv"
        df, st = process_modis(p, ca_poly)
        det_parts.append(to_det(df, "MODIS"))
        year_stats[yr] = {"modis": st, "viirs": []}
        log.info("MODIS %d: raw=%d oos=%d in_state=%d", yr, st["raw"], st["oos"], st["in_state"])

    # --- 2011-2013: disc files ---
    for pmod, psat, sensor in [
        (RAW_DIR/"MODIS_SP_disc_2011_2013.csv", None,                                    "MODIS"),
        (None, RAW_DIR/"VIIRS_SNPP_SP_disc_2012_2013.csv",                               "VIIRS"),
    ]:
        if sensor == "MODIS":
            df, st = process_modis(pmod, ca_poly)
            det_parts.append(to_det(df, "MODIS"))
            df["_yr"] = pd.to_datetime(df["acq_date"]).dt.year
            for yr, grp in df.groupby("_yr"):
                yr = int(yr)
                if yr not in year_stats: year_stats[yr] = {"modis": None, "viirs": []}
                year_stats[yr]["modis"] = {**st, "in_state": len(grp), "note": "disc"}
        else:
            df, st = process_viirs(psat, ca_poly)
            det_parts.append(to_det(df, "VIIRS"))
            df["_yr"] = pd.to_datetime(df["acq_date"]).dt.year
            for yr, grp in df.groupby("_yr"):
                yr = int(yr)
                if yr not in year_stats: year_stats[yr] = {"modis": None, "viirs": []}
                year_stats[yr]["viirs"].append({**st, "in_state": len(grp),
                                                "product": "VIIRS_SNPP_SP_disc", "note": "disc"})

    # --- 2014-2019 ---
    for yr in range(2014, 2020):
        if yr not in year_stats: year_stats[yr] = {"modis": None, "viirs": []}
        df, st = process_modis(EXT_DIR / f"MODIS_SP_{yr}.csv", ca_poly)
        det_parts.append(to_det(df, "MODIS"))
        year_stats[yr]["modis"] = st
        log.info("MODIS %d: raw=%d oos=%d in_state=%d", yr, st["raw"], st["oos"], st["in_state"])

        for prod in ["VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"]:
            p = EXT_DIR / f"{prod}_{yr}.csv"
            if p.exists():
                vdf, vst = process_viirs(p, ca_poly)
                det_parts.append(to_det(vdf, "VIIRS"))
                year_stats[yr]["viirs"].append({**vst, "product": prod})
                log.info("%s %d: raw=%d oos=%d in_state=%d harm=%d",
                         prod, yr, vst["raw"], vst["oos"], vst["in_state"],
                         vst["in_state"] - vst["thresh_drop"])

    # --- 2020-2024 ---
    for yr in range(2020, 2025):
        if yr not in year_stats: year_stats[yr] = {"modis": None, "viirs": []}
        df, st = process_modis(RAW_DIR / f"MODIS_SP_{yr}.csv", ca_poly)
        det_parts.append(to_det(df, "MODIS"))
        year_stats[yr]["modis"] = st

        for prod in ["VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP"]:
            p = RAW_DIR / f"{prod}_{yr}.csv"
            if p.exists():
                vdf, vst = process_viirs(p, ca_poly)
                det_parts.append(to_det(vdf, "VIIRS"))
                year_stats[yr]["viirs"].append({**vst, "product": prod})

        log.info("MODIS %d: raw=%d oos=%d in_state=%d", yr, st["raw"], st["oos"], st["in_state"])

    # --- Combine ---
    det_all = pd.concat([d for d in det_parts if not d.empty], ignore_index=True)
    det_all = det_all.sort_values(["date", "latitude", "longitude"]).reset_index(drop=True)
    total_rows = len(det_all)
    log.info("Total harmonised detections: %d (MODIS=%d VIIRS=%d)",
             total_rows, (det_all.sensor=="MODIS").sum(), (det_all.sensor=="VIIRS").sum())

    # --- Daily aggregation ---
    det_all["_date"] = pd.to_datetime(det_all["date"])
    daily_m = det_all[det_all.sensor=="MODIS"].groupby("_date").size().rename("raw_modis_hotspots")
    daily_v = det_all[det_all.sensor=="VIIRS"].groupby("_date").size().rename("raw_viirs_hotspots")

    spine = pd.date_range("2000-11-01", "2024-12-31", freq="D")
    dd = pd.DataFrame(index=spine)
    dd = dd.join(daily_m).join(daily_v).fillna(0).astype(int)
    dd["harmonised_hotspots"] = dd["raw_modis_hotspots"] + dd["raw_viirs_hotspots"]

    dd["year"] = dd.index.year
    dd["n_satellites_viirs"] = dd["year"].apply(lambda y: constellation_meta(y)["n_satellites_viirs"])
    dd["n_satellites_total"] = dd["year"].apply(lambda y: constellation_meta(y)["n_satellites_total"])
    dd["era"]                = dd["year"].apply(lambda y: constellation_meta(y)["era"])
    dd["_sdiv"]              = dd["year"].apply(satnorm_div)
    dd["harmonised_hotspots_satnorm"] = (dd["harmonised_hotspots"] / dd["_sdiv"]).round(2)
    dd["doy"] = dd.index.dayofyear
    doy_med   = dd.groupby("doy")["harmonised_hotspots"].median().rename("median_hotspots")
    dd = dd.join(doy_med, on="doy")
    dd["anomaly_hotspots"] = dd["harmonised_hotspots"] - dd["median_hotspots"]

    # --- Gate 2 ---
    sub = dd[(dd.index >= "2020-01-01") & (dd.index <= "2024-12-31")]
    ext_sum = int(sub["harmonised_hotspots"].sum())
    pk_idx   = sub["harmonised_hotspots"].idxmax()
    pk_date  = pk_idx.strftime("%Y-%m-%d")
    pk_count = int(sub.loc[pk_idx, "harmonised_hotspots"])
    log.info("Gate 2 — 2020-2024 sum=%d (frozen=%d) peak=%s/%d (frozen=%s/%d)",
             ext_sum, FROZEN_HARM_TOTAL, pk_date, pk_count, FROZEN_PEAK_DATE, FROZEN_PEAK_COUNT)
    if ext_sum != FROZEN_HARM_TOTAL or pk_date != FROZEN_PEAK_DATE or pk_count != FROZEN_PEAK_COUNT:
        log.error("GATE 2 FAIL"); sys.exit(1)
    log.info("Gate 2 PASSED")

    # --- Gate 3 ---
    daily_sum = int(dd["harmonised_hotspots"].sum())
    if daily_sum != total_rows:
        log.error("GATE 3 FAIL: daily_sum=%d != rows=%d", daily_sum, total_rows); sys.exit(1)
    log.info("Gate 3 PASSED: daily_sum=%d == rows=%d", daily_sum, total_rows)

    # --- Low-year check ---
    for yr in [2010, 2019]:
        yr_dd = dd[dd.index.year == yr]
        log.info("Low-year %d: days=%d zero_days=%d sum=%d",
                 yr, len(yr_dd), int((yr_dd.harmonised_hotspots==0).sum()),
                 int(yr_dd.harmonised_hotspots.sum()))

    # --- Overall peak ---
    overall_pk_idx   = dd["harmonised_hotspots"].idxmax()
    overall_pk_date  = overall_pk_idx.strftime("%Y-%m-%d")
    overall_pk_count = int(dd.loc[overall_pk_idx, "harmonised_hotspots"])
    log.info("Overall peak 2000-2024: %s / %d", overall_pk_date, overall_pk_count)
    if overall_pk_date != FROZEN_PEAK_DATE:
        log.warning("Overall peak (%s/%d) differs from 2020-2024 peak. "
                    "Do NOT overwrite app peak claim.", overall_pk_date, overall_pk_count)

    # --- Write outputs ---
    cols = ["date","raw_modis_hotspots","raw_viirs_hotspots","harmonised_hotspots",
            "harmonised_hotspots_satnorm","n_satellites_viirs","n_satellites_total",
            "era","median_hotspots","anomaly_hotspots"]
    out = dd.reset_index().rename(columns={"index": "date"})
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out[cols].to_csv(OUT_DAILY, index=False)
    log.info("Wrote %s (%d rows)", OUT_DAILY, len(out))

    det_out = det_all[["date","latitude","longitude","frp","sensor","satellite"]].copy()
    det_out.to_csv(OUT_DETECTIONS, index=False)
    log.info("Wrote %s (%d rows)", OUT_DETECTIONS, len(det_out))

    # --- Manifest ---
    elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
    _write_manifest(year_stats, dd, total_rows, overall_pk_date, overall_pk_count, elapsed)
    log.info("Done in %.0f s", elapsed)


def _write_manifest(year_stats, dd, total_rows, peak_date, peak_count, elapsed):
    lines = [
        "# Sekhmet Sync — Extended Harmonised Series Manifest",
        "",
        "> **WARNING:** A naive 2000–2024 sum would show a spurious ~3x rise that is",
        "> mostly more satellites in orbit, not more fire. `harmonised_hotspots` does",
        "> NOT correct for this. Use `harmonised_hotspots_satnorm` for multi-decade",
        "> comparison — treat it as **experimental**.",
        ">",
        "> In 2020–2024, 73.8% of harmonised detections are VIIRS-only. Sensor still matters.",
        "",
        "## Threshold label",
        "> VIIRS >=6.5 MW — experimental, fitted on California 2012-2013 monthly overlap",
        "> (r=0.9974, monthly only). Not validated on daily 2020-2024 data or outside California.",
        "",
        "## Constellation",
        "",
        "| Years | Era | VIIRS sats | Satnorm div |",
        "|-------|-----|------------|-------------|",
        "| 2000–2001 | Terra-only | 0 | 1 |",
        "| 2002–2011 | Terra+Aqua | 0 | 1 |",
        "| 2012–2017 | Terra+Aqua+S-NPP | 1 | 1 |",
        "| 2018–2022 | Terra+Aqua+S-NPP+NOAA-20 | 2 | 2 |",
        "| 2023–2024 | Terra+Aqua+NOAA-20+NOAA-21 | 2 | 2 |",
        "",
        "## Per-year reconciliation",
        "",
        "| Year | MODIS in-state | VIIRS in-state | Harmonised (daily) | Era |",
        "|------|---------------|---------------|-------------------|-----|",
    ]
    for yr in sorted(year_stats):
        st = year_stats[yr]
        m_in = st["modis"]["in_state"] if st["modis"] else 0
        v_in = sum(v.get("in_state", 0) for v in st["viirs"])
        yr_harm = int(dd[dd.index.year == yr]["harmonised_hotspots"].sum())
        era = constellation_meta(yr)["era"]
        lines.append(f"| {yr} | {m_in:,} | {v_in:,} | {yr_harm:,} | {era} |")

    total_harm = int(dd["harmonised_hotspots"].sum())
    sub_sum = int(dd[(dd.index >= "2020-01-01") & (dd.index <= "2024-12-31")]["harmonised_hotspots"].sum())
    lines += [
        "",
        "## Reconciliation checks",
        "",
        f"- Daily sum harmonised: **{total_harm:,}**",
        f"- Detections file rows: **{total_rows:,}**",
        f"- Match: {'PASS' if total_harm == total_rows else 'FAIL'}",
        f"- Peak day (2000-2024): **{peak_date}** / **{peak_count:,}**",
        f"- 2020-2024 subset: **{sub_sum:,}** (frozen: 347,174) — {'PASS' if sub_sum == 347174 else 'FAIL'}",
        f"- Gate 2: PASS | Gate 3: PASS",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} | {elapsed:.0f}s",
    ]
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Wrote %s", OUT_MANIFEST)


if __name__ == "__main__":
    main()
