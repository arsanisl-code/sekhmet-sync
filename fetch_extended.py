"""fetch_extended.py - FIRMS extended data pull. DATA PULL ONLY."""
import os, sys, time, logging, argparse
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from io import StringIO
import requests, pandas as pd
from dotenv import load_dotenv
load_dotenv()

BBOX = "-124.5,32.5,-114.0,42.0"
LAT_MIN, LAT_MAX = 32.5, 42.0
LON_MIN, LON_MAX = -124.5, -114.0
BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
OUT_DIR = Path("data/raw_extended")
CHUNK = 5
SLEEP = 0.35

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fetch_ext")

PRODUCT_START = {
    "MODIS_SP":        date(2000, 11, 1),
    "VIIRS_SNPP_SP":   date(2012, 1, 20),
    "VIIRS_NOAA20_SP": date(2018, 4, 1),
}

PRIORITIES = {
    1: [("MODIS_SP",2016,2019),("VIIRS_SNPP_SP",2016,2019),("VIIRS_NOAA20_SP",2018,2019)],
    2: [("MODIS_SP",2014,2015),("VIIRS_SNPP_SP",2014,2015)],
    3: [("MODIS_SP",2000,2010)],
}

tx_count = 0
window_start = time.monotonic()

def charge(n=2):
    global tx_count, window_start
    now = time.monotonic()
    if now - window_start >= 600:
        log.info("Rate window reset. tx in last window: %d", tx_count)
        tx_count = 0; window_start = now
    tx_count += n
    if tx_count > 4800:
        wait = 600 - (time.monotonic() - window_start) + 15
        log.warning("Approaching rate limit (%d tx). Waiting %.0f s", tx_count, wait)
        time.sleep(wait)
        tx_count = 0; window_start = time.monotonic()

def chunks(start, end):
    cur = start
    while cur <= end:
        days = min(CHUNK, (end - cur).days + 1)
        yield cur, days
        cur += timedelta(days=days)

def fetch_chunk(key, product, start, days):
    url = f"{BASE_URL}/{key}/{product}/{BBOX}/{days}/{start.isoformat()}"
    try:
        r = requests.get(url, timeout=90)
    except Exception as e:
        log.error("Network error %s %s: %s", product, start, e); return None
    if r.status_code == 429:
        raise RuntimeError(f"RATE LIMIT 429 on {product} {start}")
    if r.status_code != 200:
        log.error("HTTP %d on %s %s: %s", r.status_code, product, start, r.text[:100]); return None
    txt = r.text.strip()
    if not txt or txt.startswith("Not Found"): return None
    try:
        df = pd.read_csv(StringIO(txt))
        return df if not df.empty else None
    except Exception as e:
        log.error("Parse error %s %s: %s", product, start, e); return None

def conf_ok(row, product):
    if "MODIS" in product:
        try: return float(row["confidence"]) >= 30
        except: return False
    return str(row["confidence"]).strip().lower() != "l"

def empty_header(product):
    if "MODIS" in product:
        return "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_t31,frp,daynight,type"
    return "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight,type"

MANIFEST = OUT_DIR / "MANIFEST.md"

def manifest_append(r):
    if not MANIFEST.exists():
        MANIFEST.write_text("# Extended Data Manifest\nNo secrets in this file.\n\n"
            "| filename | sensor | year | date_start | date_end | rows | source | pulled_utc |\n"
            "|----------|--------|------|------------|----------|------|--------|------------|\n", encoding="utf-8")
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write(f"| {r['fn']} | {r['sensor']} | {r['year']} | {r['ds']} | {r['de']} | {r['rows']} | FIRMS_SP | {r['ts']} |\n")

def fetch_year(key, product, year):
    out = OUT_DIR / f"{product}_{year}.csv"
    if out.exists():
        df = pd.read_csv(out)
        log.info("EXISTS %s rows=%d", out.name, len(df)); return
    ps = PRODUCT_START.get(product, date(2000,1,1))
    ys = max(date(year,1,1), ps)
    ye = date(year,12,31)
    if ys > ye:
        log.info("SKIP %s %d (product starts %s)", product, year, ps); return
    log.info("Fetching %s %d (%s to %s)", product, year, ys, ye)
    parts = []
    for cs, days in chunks(ys, ye):
        charge(2)
        c = fetch_chunk(key, product, cs, days)
        if c is not None: parts.append(c)
        time.sleep(SLEEP)
    if not parts:
        log.info("0 rows for %s %d", product, year)
        out.write_text(empty_header(product)+"\n", encoding="utf-8")
        manifest_append({"fn":out.name,"sensor":product,"year":year,"ds":str(ys),"de":str(ye),"rows":0,"ts":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        return
    df = pd.concat(parts, ignore_index=True).drop_duplicates()
    # bbox
    df = df[(df.latitude>=LAT_MIN)&(df.latitude<=LAT_MAX)&(df.longitude>=LON_MIN)&(df.longitude<=LON_MAX)].copy()
    # conf
    mask = df.apply(lambda row: conf_ok(row, product), axis=1)
    conf_drop = (~mask).sum()
    df = df[mask].copy()
    # gate 1
    dates = pd.to_datetime(df["acq_date"])
    log.info("Gate1 %s %d rows=%d dates=%s/%s lat=[%.2f,%.2f] lon=[%.3f,%.3f] conf_drop=%d",
        product, year, len(df), dates.min().date() if len(df) else "N/A", dates.max().date() if len(df) else "N/A",
        df.latitude.min() if len(df) else 0, df.latitude.max() if len(df) else 0,
        df.longitude.min() if len(df) else 0, df.longitude.max() if len(df) else 0, conf_drop)
    df.to_csv(out, index=False)
    log.info("Saved %s (%d rows)", out.name, len(df))
    manifest_append({"fn":out.name,"sensor":product,"year":year,
        "ds":str(df.acq_date.min()) if len(df) else str(ys),
        "de":str(df.acq_date.max()) if len(df) else str(ye),
        "rows":len(df),"ts":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--priority", required=True)
    args = parser.parse_args()
    key = os.environ.get("FIRMS_MAP_KEY","").strip()
    if not key:
        print("FIRMS_MAP_KEY not set"); sys.exit(1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plist = [1,2,3] if args.priority=="all" else [int(args.priority)]
    for p in plist:
        log.info("=== PRIORITY %d ===", p)
        for product, ys, ye in PRIORITIES[p]:
            for yr in range(ys, ye+1):
                fetch_year(key, product, yr)
    log.info("Done. Manifest: %s", MANIFEST)

if __name__ == "__main__":
    main()


