# DECISIONS — Sekhmet Sync

Every design decision, assumption, and choice is recorded here with the reasoning
and alternatives rejected.

---

## D01 — Map library: Plotly scatter_mapbox with OpenStreetMap
**Choice:** Plotly scatter_mapbox, tiles = "open-street-map" (no API key).
**Reason:** Already in the core stack. Zero additional JS weight. OpenStreetMap tiles
require no key and render reliably on a Chromebook. Interactive (zoom, hover) in the browser.
**Rejected:** Folium (extra JS, Chromebook performance risk), Pydeck (WebGL, may fail
on integrated GPU), Kepler.gl (heavy, requires React).

## D02 — Caching and Data Storage: Committed CSV Files
**Choice:** Committed flat CSV files (`data/daily_series_harmonised.csv` and `data/harmonised_detections.csv`).
**Reason:** The app serves directly from clean, precomputed, committed CSV files (56 KB and 15.6 MB).
Zero database dependency, instant local query execution, under GitHub 100 MB file limit, and Streamlit Community Cloud deployable.
**Rejected:** SQLite/DuckDB/Parquet cube on the critical path (unnecessary complexity for 347k rows; calendar requires daily aggregation, not cube OLAP).

## D03 — Pivot from Clustering to Harmonised Hotspot Counts
**Choice:** Count harmonised active-fire hotspots directly per day. Drop spatial clustering (KD-tree + union-find).
**Reason:** The NASA Space Apps challenge explicitly asks for "number of hotspots detected" to build a burning activity calendar, not clustered "fires". Spatial clustering introduced arbitrary chaining heuristics, projection distortions (lat/lon degree distortion across California), and artificial mega-clusters (such as a 5,542-detection chained entity). Counting harmonised hotspots directly is robust, reproducible, and aligns strictly with the challenge prompt.
**Rejected:** Spatial clustering with KD-tree and union-find; DBSCAN.

## D04 — VIIRS confidence filter: drop 'l', keep 'n' and 'h'
**Choice:** Drop VIIRS rows where confidence == 'l'.
**Reason:** FIRMS user guide states that 'l' = low confidence, 'n' = nominal, 'h' = high.
The brief states "drop only low-confidence detections." 'l' is the only low class.
**Source:** https://firms.modaps.eosdis.nasa.gov/api/area/ and FIRMS FAQ.

## D05 — MODIS confidence filter: drop confidence < 30
**Choice:** Drop MODIS rows where confidence (integer 0–100) < 30.
**Reason:** FIRMS documentation states that MODIS confidence < 30 is "low". Values
30–79 are "nominal" and 80–100 are "high". Dropping < 30 is consistent with the VIIRS
'l' drop rule (keep nominal and high).
**Source:** FIRMS MODIS collection 6.1 product description.

## D06 — Baseline Harmonisation: Experimental 6.5 MW FRP Threshold
**Choice:** Filter VIIRS detections with FRP < 6.5 MW. Retain MODIS detections (confidence ≥ 30) and VIIRS detections (confidence ≠ 'l' and FRP ≥ 6.5 MW).
**Reason:** VIIRS 375 m pixels have much higher spatial sensitivity than MODIS 1 km pixels, detecting thousands of faint sub-pixel hotspots that MODIS cannot see. Testing S-NPP vs MODIS on pre-drift California fire records (2012–2013) demonstrated that applying a 6.5 MW cut-off on VIIRS yields an aggregate monthly correlation of r = 0.9974 with a -4.8% bias against MODIS counts.
**Limitation:** This threshold baseline is strictly empirical, regional (California), and labelled **experimental**. It is not a universal global physics model.
**Rejected:** Single scalar FRP multiplier (e.g. 0.85). Literature (Li et al. 2018, Sofiev & Kouznetsov) contradicts uniform scalar scaling between sensors with disparate point-spread functions and saturation characteristics.

## D07 — Leap year alignment for historical median
**Choice:** Compute day-of-year (DOY) using pandas dt.dayofyear. DOY 60 = Feb 29
in leap years. DOY 60 is absent in non-leap years; median for DOY 60 is taken over
only the two leap years (2020, 2024). DOY 366 similarly appears only in those two years.
**Reason:** Simplest approach that is mathematically correct. No artificial re-indexing needed.
**Rejected:** Forcing non-leap-year Feb 28 to cover DOY 59 and 60 (would double-count Feb 28).

## D08 — API chunk size: 5 days per request
**Choice:** Fetch 5 days per API request (well within the documented 10-day limit).
**Reason:** Keeps each request small, reduces risk of timeout on large-fire days with
high detection counts. 2020 is an extreme fire year; a single-year request could fail.

## D09 — VIIRS NOAA-21 availability
**Fact:** VIIRS_NOAA21_SP data starts 2023-03-01 (confirmed via FIRMS
data_availability API). No NOAA-21 data exists for 2020–2022 or Jan–Feb 2023 in this
product. The pipeline proceeds without it for those dates; this is a physical satellite launch constraint, not a pipeline gap. Documented in app and README.

## D10 — VIIRS S-NPP exclusion from main 2020–2024 pipeline
**Choice:** S-NPP is excluded from the 2020–2024 California operational dataset.
**Reason:** S-NPP began drifting significantly in orbit later in life, and operational VIIRS standard products transitioned to NOAA-20 and NOAA-21. S-NPP is used solely for the 2011–2013 historical demonstration of sensor discontinuity.

## D11 — Gas flares and industrial heat sources
**Choice:** No persistent-source spatial filter implemented in this version.
**Reason:** Filtering industrial/refinery heat sources requires a verified external persistent-source catalogue. Retaining all verified active fire detections keeps the pipeline lean and reproducible. Documented in the app and README as a known scope limit.

## D12 — Five-year baseline acknowledgment
**Choice:** Use 2020–2024 as the baseline for the historical median.
**Known limitation:** Five years is a short baseline, dominated by the extreme 2020
fire season. The median represents recent burning patterns, not a 30-year climatology. This is prominently displayed in the UI.

## D13 — Midnight UTC split
**Choice:** Use acq_date as recorded in NASA FIRMS.
**Reason:** FIRMS reports observations stamped in UTC. Splitting across calendar days preserves exact observation dates without making temporal clustering assumptions.

## D14 — Pre-filtering California state boundary
**Choice:** US Census Bureau TIGER/Line California state boundary polygon (`data/california.geojson`).
**Implementation:** In `build_daily_harmonized.py`, shapely point-in-polygon filtering is applied directly to detection coordinates:
- Raw input rows: 752,610 (MODIS: 117,770; NOAA-20: 553,074; NOAA-21: 81,766).
- Zero/negative FRP: 1,317 rows dropped.
- In-state raw hotspots: 722,596 (MODIS: 113,795; VIIRS: 608,801). 28,697 out-of-state detections dropped.
- Harmonised in-state hotspots: 347,174 (MODIS: 113,795; VIIRS ≥ 6.5 MW: 233,379).
- Sub-threshold VIIRS filtered: 375,422 (61.7% of raw VIIRS, 52.0% of total raw).

## D15 — Sub-Region Definitions and Out-of-Coverage Guard
**Choice:** Define 4 preset regions plus an interactive custom bounding box:
1. `California — Statewide`: full California state boundary polygon.
2. `California — Northern Forests (Klamath)`: Lat [39.5, 42.0], Lon [-124.5, -120.0].
3. `California — Sierra Nevada / Central`: Lat [36.5, 39.5], Lon [-121.5, -118.0].
4. `California — Southern Chaparral (LA / San Diego)`: Lat [32.5, 35.5], Lon [-120.5, -115.5].
5. `Custom Lat / Lon Bounding Box`: User-entered min/max latitude and longitude.

**Out-of-Coverage Rule:**
If a custom bounding box does not intersect California extent (Lat [32.5, 42.0], Lon [-124.5, -114.1]), the application stops execution and displays the exact warning:
`"Selected area is outside the California data archive — no coverage."`
It does NOT display an empty calendar or false 0-fire statistics.

## D16 — Sliced Data Export (Search-to-Download Fidelity)
**Choice:** Download buttons export CSV data sliced dynamically to both the selected region/bounding box AND the selected date range.
**Reason:** Resolves user friction where downloads previously exported full state or un-sliced data. If a user selects Sierra Nevada for August 2021, the export contains exactly the 31 daily rows and 11,657 detection records for that search.

## D17 — Palette and WCAG AA/AAA Compliance
**Palette:**
- Papyrus `#E8DCC4` (canvas background)
- Warm Sand `#D8C3A5` (sidebar / card containers)
- Basalt `#1C1B1A` (primary text — 12.67:1 contrast on Papyrus, AAA)
- Solar Gold `#D4AF37` (brand accents on dark Basalt only — 8.18:1, AAA)
- Text Gold `#5E4605` (gold text on light backgrounds — 6.57:1 on Papyrus, AA)
- Deshret Crimson `#A82E2E` (accent / fire peak — 5.00:1 on Papyrus, AA)
- Deep Crimson `#8B1E1E` (peak severity)
- Lapis `#1B365D` (MODIS sensor — 8.93:1 on Papyrus, AAA)
- Wadj Malachite `#2E6F40` (historical median reference — 4.46:1, AA graphical)

## D18 — Metric Card Responsive Sizing (No Ellipsis)
**Choice:** Inject custom CSS targeting `[data-testid="stMetricValue"]` with `font-size: 1.35rem !important;` and `white-space: normal;`.
**Reason:** On standard Chromebook screens (1366×768), Streamlit's default 2.25rem font size causes numbers with 6 digits and commas (e.g. `722,596`) to truncate with ellipsis (`...`). Setting 1.35rem ensures all values render cleanly and legibly.

## D19 — Calendar Single Matrix Heatmap
**Choice:** Single 5×366 NumPy matrix rendered via `go.Heatmap`.
**Reason:** Plotly cannot cleanly align 5 separate 1D traces with categorical y-axes. A single 2D matrix ensures crisp pixel-perfect rendering across all 5 years (2020–2024) and 366 day-of-year slots, with leap day handled naturally.

## D20 — Empirical Biome Stability and Inter-Bbox Remainder
**Finding:** Auditing the 347,174 harmonised detections across California biomes shows that the 6.5 MW threshold produces consistent harmonised VIIRS/MODIS ratios across forested ecosystems:
- Northern Forests (Klamath): 1.98 (61,204 MODIS, 121,237 VIIRS)
- Sierra Nevada / Central: 2.01 (24,522 MODIS, 49,235 VIIRS)
- Southern Chaparral: 2.48 (7,350 MODIS, 18,199 VIIRS)
**Subtotal & Remainder:** The 3 subregions contain 281,747 harmonised detections (81.15%). Exactly 65,427 detections (18.85%) fall outside these 3 bounding boxes (primarily Central Valley, coastal, and inter-bbox corridors). With half-open upper boundaries (`<`), subtotal is 281,739 with 65,435 remainder.
**Interpretation:** The ratio is stable across forested biomes; higher in chaparral due to smaller thermal cores in fine fuels. This demonstrates empirical transferability within California forest biomes without claiming global transferability.

## D21 — Constellation Expansion vs. Satellite-Hour Scaling
**Finding:** Harmonised VIIRS/MODIS ratios by year are:
- 2020: 1.99
- 2021: 1.82
- 2022: 1.36
- 2023: 2.74
- 2024: 3.21
**Interpretation:** The jump in 2023–2024 directly reflects the operational arrival of NOAA-21 in March 2023 (doubling VIIRS satellite sensors from 1 to 2). This empirically verifies that multi-decade harmonization cannot rely on un-normalized counts, and must incorporate satellite-hour normalization.

## D22 — VZA Scan-Angle Truncation vs. Detection Selection Bias
**Finding:** Binned audit of all 47,953 raw MODIS 2020 detections shows median FRP rises monotonically with scan angle:
- 1.0–1.5 km (Near Nadir): 29,488 detections, Median FRP = 29.1 MW
- 1.5–2.0 km (Mid-Swath): 7,675 detections, Median FRP = 54.6 MW
- 2.0–3.0 km (Off-Nadir): 6,157 detections, Median FRP = 84.2 MW
- 3.0–5.0 km (Swath Edge): 4,633 detections, Median FRP = 159.8 MW
**Reconciliation:** All 47,953 rows reconcile. Exactly 11,087 detections fall at nadir `scan == 1.0 km`.
**Interpretation:** Scan edge pixel expansion (~10× area) creates an observational truncation filter where faint fires fall below detection limits, causing detected median FRP to rise 5×. Scalar inflation of edge FRP would falsely inflate large fires; VZA correction remains a documented frontier.

## D23 — External Ground Truth Consistency Check (CAL FIRE 2020/2021)
**Verification:**
- Peak Day: 2020-09-09 (10,320 hotspots) matches the extreme Diablo wind siege that exploded the August Complex (started Aug 16, 2020, 1,032,648 acres), Creek Fire (started Sep 4, 2020, 379,895 acres), and North Complex (started Aug 17, 2020, 318,935 acres).
- 21-Day Streak: Aug 30 – Sep 19, 2020 (66,764 hotspots) spans the synchronized peak burning window of these 3 mega-fires.
- 23-Day Streak: Aug 1–23, 2021 (48,049 hotspots) matches the peak run of the Dixie Fire (started Jul 13, 2021, 963,309 acres).
**Conclusion:** Validates that Sekhmet Sync's statistical anomalies and critical periods correlate with major physical wildfire disasters recorded by CAL FIRE.
