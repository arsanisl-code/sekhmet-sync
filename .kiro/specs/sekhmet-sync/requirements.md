# Requirements — Sekhmet Sync

## REQ-01 Data acquisition
- R01.1 fetch_firms.py downloads MODIS_SP and VIIRS_NOAA20_SP for 2020–2024 from the
  FIRMS area API using the key in FIRMS_MAP_KEY. It also downloads VIIRS_NOAA21_SP for
  2023–2024 (the only years it is available). No other product codes are used in the
  main pipeline.
- R01.2 All files are saved to data/raw/ as CSV, named
  {product}_{year}.csv (e.g., MODIS_SP_2020.csv).
- R01.3 If FIRMS_MAP_KEY is unset or the API call fails, the script prints the exact
  HTTP error or env-var absence, lists the expected manual file names with URLs, and
  exits with code 1 (Gate 1 fallback documented).
- R01.4 After download, the script logs: filename, rows, date range (min/max acq_date),
  confidence distribution, and rows dropped by confidence filter.
- R01.5 Bounding box is exactly: west=-124.5, south=32.5, east=-114.0, north=42.0.
  API requests use this box. Post-download, rows outside this box are dropped and counted.
- R01.6 VIIRS NOAA-21 is not available before 2023-03-01. The script notes this in its
  log and does not attempt to download it for 2020–2022.
- R01.7 Confidence filter (applied before writing to data/raw/ staging area but logged):
  MODIS: drop rows where confidence < 30 (numeric; FIRMS guidance says <30 is low).
  VIIRS: drop rows where confidence == 'l' (categorical; FIRMS guidance: l=low).
  Log "Dropped N rows from {product} {year} at confidence filter" for each file.
- R01.8 The `type` column is retained but not used to filter in the main pipeline.

## REQ-02 Column mapping
Shared columns that exist in both: latitude, longitude, scan, track, acq_date,
acq_time, satellite, instrument, confidence, version, frp, daynight.

MODIS-specific: brightness (Band 21/22 brightness temperature), bright_t31 (Band 31).
VIIRS-specific: bright_ti4 (I-4 band ≈ 3.75 µm), bright_ti5 (I-5 band ≈ 11.45 µm).

After loading, both are merged into a unified schema:
  latitude, longitude, scan, track, acq_date, acq_time, satellite, instrument,
  confidence_raw, frp, daynight, brightness_mid (MODIS brightness / VIIRS bright_ti4),
  brightness_lwir (MODIS bright_t31 / VIIRS bright_ti5), sensor_type (modis | viirs),
  source_product (MODIS_SP | VIIRS_NOAA20_SP | VIIRS_NOAA21_SP).

## REQ-03 Clustering
- R03.1 cluster.py clusters all filtered detections on the same UTC acq_date that fall
  within ~1 km of each other into one fire record.
- R03.2 Algorithm: 1 km spatial hash grid. Each detection maps to a grid cell at
  floor(lat / cell_deg) × floor(lon / cell_deg) where cell_deg ≈ 0.009° (≈1 km).
  For each cell, also check the 8 neighboring cells so boundary detections are not missed.
  Build adjacency within (cell + neighbors) using scipy.spatial.KDTree with
  radius = 0.009° (≈1 km at 36° N). Connected components via union-find.
  Time complexity: O(n log n) for KDTree build + O(n k) for radius queries where
  k is bounded by grid cell density (small constant for typical fire data).
- R03.3 Detections on different acq_dates are never merged.
- R03.4 Midnight UTC: acq_date is used as given. A fire crossing midnight UTC becomes
  two records. This is documented as a known limitation.
- R03.5 Output schema (one row per harmonised fire):
  fire_id, date, centroid_lat, centroid_lon, n_detections, n_modis, n_viirs,
  sensors_present, total_frp, max_frp, mean_brightness, first_acq_time, last_acq_time.
  sensors_present values: modis_only | viirs_only | both.
  fire_id format: CA-YYYY-MM-DD-NNN (zero-padded 3-digit sequential within each day).
- R03.6 Report: N raw detections (post-filter), M harmonised fires, % removed = (N−M)/N×100,
  runtime in seconds.
- R03.7 Scaling test: run on 50% sample and 100% of input; show runtime ratio < 2×
  (sub-quadratic growth).

## REQ-04 Harmonization
- R04.1 harmonize.py reads ca_2020_2024.parquet and writes:
  data/daily_series.csv (1,827 rows), data/ca_2020_2024_harmonised.csv (per-fire rows).
- R04.2 Daily series columns (in order):
  date, raw_modis, raw_viirs, harmonised_fires, total_frp_corrected, total_frp_raw,
  median_fires.
  Optional appended columns: median_frp, anomaly_fires, anomaly_frp.
- R04.3 FRP correction: each sensor's total_frp is multiplied by a documented correction
  factor. The corrected total is labeled approximate and distributional.
- R04.4 Historical median: for each day-of-year (1–366), compute median harmonised_fires
  and median total_frp across the five years 2020–2024. Feb 29 (DOY 60 in leap years)
  is handled by assigning it DOY 60 in both leap and non-leap years; non-leap years
  have no DOY 366 value, so median for DOY 366 is computed only from leap years.
- R04.5 1,827 rows = 365×4 + 366×1 (2020 and 2024 are leap years; 2021, 2022, 2023 are not).
  Wait — 2020 is leap (366 days), 2024 is leap (366 days), 2021/22/23 are not (365 each).
  Total = 366 + 365 + 365 + 365 + 366 = 1827. Correct.

## REQ-05 Gate 3 reconciliation
- R05.1 Row count of daily_series.csv == 1,827.
- R05.2 Sum of harmonised_fires across daily_series == number of rows in
  ca_2020_2024_harmonised.csv (and ca_2020_2024.parquet).
- R05.3 Sum of n_detections across ca_2020_2024_harmonised.csv == N (raw post-filter).
- R05.4 Sum of total_frp_raw in daily_series == sum of total_frp in harmonised, within
  floating-point tolerance (rtol=1e-5).

## REQ-06 App
See product.md and rules.md for the full UI requirements. Technical acceptance:
- Loads in < 5 seconds from data/ files on a standard laptop.
- Zero clustering, zero API calls on page load.
- Sensor toggle changes stat cards, map, calendar, and download contents.
- Both CSV downloads return valid CSV in a real browser (not just a link that 404s).

## REQ-07 Discontinuity demo
- R07.1 discontinuity.py downloads MODIS_SP and VIIRS_SNPP_SP for California 2011–2013.
- R07.2 Produces a 3-line chart: raw MODIS counts, raw S-NPP counts, harmonised counts.
- R07.3 Chart title exactly: "Historical demonstration, 2011–2013, includes S-NPP for
  this chart only."
- R07.4 Saves exports/discontinuity.png.
- R07.5 Reports honestly whether the harmonised line is continuous across the Jan 2012
  S-NPP launch boundary.

## REQ-08 Exports
- R08.1 exports/map.png — Plotly map of fire centroids for full 2020–2024, harmonised.
- R08.2 exports/calendar.png — Plotly calendar heatmap, harmonised fires.
- R08.3 exports/discontinuity.png — from discontinuity.py.
- R08.4 All exports generated from real data only.

## REQ-09 Deployment
- R09.1 requirements.txt pins all dependencies with ==.
- R09.2 Committed artifacts are each under 100 MB.
- R09.3 README contains step-by-step Streamlit Community Cloud deployment.
- R09.4 .gitignore excludes .env, data/raw/*.csv, __pycache__, *.pyc, *.parquet,
  any file > 100 MB.

## REQ-10 Tests
- R10.1 tests/test_cluster.py covers: grid-boundary detections, midnight UTC split,
  consecutive-day non-merge, single detection, empty input, mixed sensor merge.
- R10.2 tests/test_harmonize.py covers: row count, column order, FRP sum reconciliation,
  median computation, anomaly sign.
- R10.3 All fixtures in tests/fixtures/, named *_fixture.csv, with synthetic-data
  disclaimer in docstring.
