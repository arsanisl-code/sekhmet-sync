# Design — Sekhmet Sync

## Data flow
```
FIRMS API (or manual CSVs)
    ↓ fetch_firms.py
data/raw/{product}_{year}.csv    ← confidence-filtered, bbox-confirmed
    ↓ cluster.py
data/ca_2020_2024.parquet        ← per-fire rows
    ↓ harmonize.py
data/daily_series.csv            ← 1,827-row daily aggregate
data/ca_2020_2024_harmonised.csv ← per-fire rows with FRP correction applied
    ↓ app.py (read-only)
Streamlit web app
```

## Sensor availability in main pipeline
| Product          | Available from  | Years in pipeline   |
|------------------|-----------------|---------------------|
| MODIS_SP         | 2000-11-01      | 2020–2024           |
| VIIRS_NOAA20_SP  | 2018-04-01      | 2020–2024           |
| VIIRS_NOAA21_SP  | 2023-03-01      | 2023–2024 only      |

Years 2020–2022 have no NOAA-21 detections. This is a data reality, not a gap.
The app and README document it.

## Column mapping (unified schema after load)
| Unified column    | MODIS source    | VIIRS source   |
|-------------------|-----------------|----------------|
| brightness_mid    | brightness      | bright_ti4     |
| brightness_lwir   | bright_t31      | bright_ti5     |
| sensor_type       | "modis"         | "viirs"        |
| confidence_raw    | confidence (int)| confidence (str)|

All other shared columns retain their names.

## Confidence filter
MODIS: drop if confidence < 30. Rationale: FIRMS user guide states confidence ≥ 30
is the "nominal or high" threshold for MODIS. Values below 30 are "low confidence".
VIIRS: drop if confidence == 'l'. Rationale: FIRMS assigns 'l' (low), 'n' (nominal),
'h' (high) for VIIRS. The brief directs us to drop only low-confidence detections.

## Clustering algorithm
Input: a DataFrame for one day, with latitude and longitude.
Step 1: Assign each detection to a 0.009°×0.009° grid cell.
Step 2: For each detection, query a KDTree (built on that day's detections) for all
  neighbors within radius 0.009° (≈1 km at 36° N; actual arc length varies ±3% across
  CA latitudes). Include points from the current cell and all 8 neighbors.
  Practically, the KDTree handles the neighbor lookup implicitly when queried on the
  full day's points.
Step 3: Union-find over pairs returned by KDTree radius queries to find connected
  components. Each component is one fire.
Step 4: Aggregate: centroid = mean lat/lon of component, total_frp = sum, etc.

Time complexity: O(n log n) KDTree build; O(n k) queries where k = average neighbors
(empirically ≪ 10 for typical fire data). Overall O(n log n).
Space: O(n).

## FRP correction
Decision: apply a multiplicative scale factor per sensor type to bring each sensor's
FRP distribution closer to a common reference.

MODIS FRP is known to underestimate small fires (pixel size 1 km²) relative to
VIIRS 375 m. We apply:
  - MODIS: multiply raw FRP by 1.0 (no correction). MODIS is the reference.
  - VIIRS NOAA-20: multiply raw FRP by 0.85.
    Rationale: VIIRS 375 m pixels resolve sub-pixel fires more finely; the same fire
    can generate higher total FRP than MODIS due to better spatial sampling. A factor
    of 0.85 is a distributional alignment; it is approximate and labeled as such.
    NOAA-21 uses the same factor as NOAA-20 (same instrument design).

We label this as approximate and distributional throughout. We do not cite a specific
Li et al. figure because we have not been able to verify the exact number against the
primary source; instead we state: "FRP correction is approximate. See DECISIONS.md."

## Historical median / anomaly
For each calendar day-of-year d (1..366):
  median_fires[d] = median of harmonised_fires across all five years for that DOY.
  anomaly[date] = harmonised_fires[date] − median_fires[DOY(date)].

Leap year alignment: DOY is computed using dayofyear from pandas. DOY 366 only exists
in 2020 and 2024. The median for DOY 366 is taken over those two years only.
DOY 60 (Feb 29) is computed only for 2020 and 2024; non-leap years skip it.
This is documented as a known limitation of a 5-year baseline.

## App layout
Sidebar:
  - Date range picker (default: 2020-01-01 to 2024-12-31)
  - Sensor toggle: MODIS | VIIRS | Harmonised
  - Info: region fixed to California, bounding box shown

Main area (tab layout):
  Tab 1 "Overview":
    - Stat cards row
    - Map (Plotly scatter_mapbox, OpenStreetMap, no key required)
  Tab 2 "Calendar":
    - Burning-activity calendar heatmap (years × DOY)
    - Toggle: color by fires or FRP
  Tab 3 "Anomaly":
    - Line chart: daily harmonised vs. median, anomaly shaded
    - Worst days table
  Tab 4 "Top Fires":
    - Sortable table of top 10 fires
  Tab 5 "Why Harmonisation Matters":
    - Discontinuity chart image (exports/discontinuity.png)
    - Sensor comparison bar chart for the selected range

Footer:
  - Method and Limitations box (always visible)
  - Download buttons for daily_series.csv and ca_2020_2024_harmonised.csv

## Sensor toggle logic
When toggle = MODIS:
  - Map shows detections from modis-only and both clusters, sized by n_modis detections
  - Calendar uses raw_modis column
  - Stat cards use raw_modis, raw total_frp (no correction)
When toggle = VIIRS:
  - Map shows viirs-only and both clusters, sized by n_viirs
  - Calendar uses raw_viirs column
When toggle = Harmonised (default):
  - Map shows all fires sized by total_frp
  - Calendar uses harmonised_fires column
  - Stat cards use harmonised numbers

## Download implementation
Two st.download_button calls, one per file.
Files are read at startup and stored in session_state.
The sensor toggle filters daily_series before serving the download so it reflects
what the user sees. The harmonised CSV is served in full regardless of filter
(it is the full dataset; the user can filter themselves).

## Scaling test (G2)
Run cluster.py on a 50% random sample of the full raw data, record runtime.
Run on 100%. Report ratio. Expected < 2.0× (O(n log n) predicts ~1.07× for n→2n, 
empirically expect 1.3–1.8× due to fixed overhead).
