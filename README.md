# Sekhmet Sync

**NASA International Space Apps Challenge 2026 — Harmonization of MODIS and VIIRS Hot Spots**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://sekhmet-sync.streamlit.app/)
**Live Web Application:** [https://sekhmet-sync.streamlit.app/](https://sekhmet-sync.streamlit.app/)

Sekhmet Sync harmonizes active-fire hotspot records from MODIS (Terra/Aqua) and VIIRS (NOAA-20/NOAA-21) into a single, consistent **Burning Activity Calendar** for California (2020–2024).

The challenge requires a burning activity calendar based on active fire hotspots, enabling fire managers, emergency responders, and scientists to examine historical burning patterns, anomalies, and critical periods across user-selected regions. Sekhmet Sync delivers this with an honest, empirical harmonization method, accessible visual analytics, responsive layout for low-spec devices (Chromebooks), and dynamic sliced exports.

---

## Key Reconciled Figures (California 2020–2024)

Every headline statistic in Sekhmet Sync is verified and reconciled against raw NASA FIRMS records:

| Metric | Value | Description |
| :--- | :--- | :--- |
| **In-State Raw Hotspots** | **722,596** | Total active-fire detections within California state boundary (MODIS: 113,795; VIIRS: 608,801) |
| **Harmonised Hotspots** | **347,174** | MODIS + VIIRS (filtered at experimental $\text{FRP} \ge 6.5\text{ MW}$) |
| **Sub-Threshold Hotspots Filtered** | **375,422** | $61.7\%$ of raw VIIRS detections ($52.0\%$ of total raw) filtered out to match MODIS sensitivity |
| **Statewide Peak Day** | **2020-09-09** | **10,320** harmonised hotspots (August Complex / North Complex wildfire crisis) |
| **Operational Date Range** | **2020-01-01 to 2024-12-31** | Exactly 1,827 continuous days, 0 missing dates |

---

## Core Capabilities

1. **Multi-Scale Burning Activity Calendar**
   - **5×366 Daily Matrix Heatmap (Main Calendar):** High-resolution daily view across 366 day-of-year slots for all 5 continuous years (2020–2024), accurately handling leap days and pinpointing daily ignition bursts and peak events (e.g. 2020-09-09 with 10,320 hotspots).
   - **5×12 Monthly Rollup Heatmap (Overview):** Year × Month macro calendar revealing seasonal fire patterns (August–October accounting for >75% of annual burning) and multi-year climate trends (drought vs. atmospheric river seasons).
   - **Daily Time Series Line (Anomaly View):** Continuous daily burning plotted against the 5-year reference median line with Crimson (above-median) and Lapis (below-median) shading to isolate unusual fire crises.

2. **Daily Anomaly & Critical Period Analysis**
   - Evaluates daily harmonised hotspot counts against the pre-drift reference median.
   - Highlights top anomaly days with interactive markers and an above-median ranking table.

3. **Sub-Region Filtering & Coverage Boundary Guard**
   - Built-in presets for major California ecosections:
     - **California — Statewide** (Full state boundary polygon from US Census Bureau TIGER/Line)
     - **California — Northern Forests (Klamath / Cascades)**: Lat [39.5, 42.0], Lon [-124.5, -120.0]
     - **California — Sierra Nevada / Central**: Lat [36.5, 39.5], Lon [-121.5, -118.0]
     - **California — Southern Chaparral (LA / San Diego)**: Lat [32.5, 35.5], Lon [-120.5, -115.5]
     - **Custom Lat / Lon Bounding Box**: User-specified coordinates.
   - **Out-of-Coverage Guard**: If a user inputs coordinates outside California, the app halts processing and explicitly displays:
     > *"Selected area is outside the California data archive — no coverage."*
     This prevents rendering misleading empty calendars that falsely imply zero fires.

4. **Search-Matched Sliced Downloads**
   - Export buttons generate sliced CSVs matching the user's exact region and date filters.
   - Exports both the aggregated daily time series and per-detection coordinates.

5. **Chromebook-Ready & Accessible UI**
   - Custom CSS prevents metric values from truncating with ellipsis (`...`) on 1366×768 displays.
   - High-contrast Egyptian palette meeting WCAG AA/AAA standards (Basalt text 12.67:1 on Papyrus; Lapis MODIS badge 8.93:1).

---

## Harmonization Method

### Plain-Language Summary
We count satellite-detected hotspots in California, 2020–2024, after filtering the more sensitive VIIRS sensor so it matches MODIS. MODIS is counted as-is; VIIRS is counted only if it is bright enough (at least 6.5 megawatts). This gives one combined daily count, with a historical median for comparison. The 6.5 threshold is experimental — it was fitted on California data from 2012–2013, and it does not correct for viewing angle or for how many satellites were flying in a given year.

### The Problem: Sensor Discontinuity
MODIS (1 km pixel resolution) and VIIRS (375 m pixel resolution) observe fires at vastly different sensitivities. For the exact same fires in California, VIIRS detects over 5.3× more hotspots than MODIS. Treating them interchangeably creates an artificial surge in fire frequency whenever VIIRS data is added.

### The Solution: Direct Hotspot Counting with 6.5 MW Threshold
- **Dropped Spatial Clustering:** The prompt asks for *"number of hotspots detected"*, not synthetic clusters or "fires". Clustering algorithms introduce chaining artifacts (e.g., merging separate blazes into a 5,542-detection mega-fire) and spatial distortion. Sekhmet Sync counts harmonised hotspots directly.
- **Experimental 6.5 MW Cutoff:** VIIRS 375 m sensors detect faint sub-pixel burns that fall below MODIS detection capabilities. Testing S-NPP vs MODIS on pre-drift California fire records (2012–2013) demonstrated that filtering VIIRS at $\text{FRP} \ge 6.5\text{ MW}$ aligns monthly counts with MODIS at $r = 0.9974$ and $-4.8\%$ bias.
- **Honest Labeling:** This baseline is empirical and labeled **experimental**; it is not presented as an unchallengeable physical law. Uniform scalar multipliers (e.g., 0.85) were explicitly tested and rejected as physically ungrounded.

### Biome Stability Check (Sub-Region Transferability)
Harmonised VIIRS/MODIS ratio is stable across Northern Forests and Sierra Nevada (1.98 vs 2.01), with a higher ratio in Southern Chaparral (2.48), consistent with smaller thermal cores in fast-moving chaparral fires favouring VIIRS 375 m pixels. This is evidence the threshold behaves similarly across forest biomes in California — it is not proof of perfect transfer, and it has not been validated outside California.

| Sub-Region / Biome | MODIS (Harm.) | VIIRS (≥ 6.5 MW) | Total Harmonised | Harmonised VIIRS/MODIS Ratio |
| :--- | :---: | :---: | :---: | :---: |
| Northern Forests | 61,204 | 121,237 | 182,441 | 1.98 |
| Sierra Nevada / Central | 24,522 | 49,235 | 73,757 | 2.01 |
| Southern Chaparral | 7,350 | 18,199 | 25,549 | 2.48 |
| **3-Biome Subtotal** | **93,076** | **188,671** | **281,747** | **2.03** |

*Note on Remainder:* The three sub-region bboxes do not cover all of California. 65,427 harmonised detections (18.8% of statewide 347,174) fall outside Northern Forests, Sierra Nevada/Central, and Southern Chaparral — primarily Central Valley, coastal, and inter-bbox areas. (With half-open boundary upper limits, subtotal is 281,739 with 65,435 remainder). They are included in the statewide total, but not in any biome subtotal.

### Constellation Expansion & Annual Breakdown
Harmonised VIIRS/MODIS ratio was 1.99 in 2020, 1.82 in 2021, 1.36 in 2022, 2.74 in 2023, and 3.21 in 2024. The rise in 2023–2024 coincides with NOAA-21 becoming operational in 2023, giving two VIIRS satellites instead of one. Fire-year variability also affects the ratio (2022 was a low fire year), so this is consistent with, not proof of, satellite-hour scaling. A multi-decade series would need explicit satellite-hour normalisation.

| Observation Year | MODIS (Harm.) | VIIRS (≥ 6.5 MW) | Total Harmonised | Harmonised VIIRS/MODIS Ratio | Active Satellites in Scope |
| :---: | :---: | :---: | :---: | :---: | :--- |
| 2020 | 46,823 | 93,269 | 140,092 | 1.99 | Terra, Aqua, NOAA-20 |
| 2021 | 42,522 | 77,411 | 119,933 | 1.82 | Terra, Aqua, NOAA-20 |
| 2022 | 6,714 | 9,133 | 15,847 | 1.36 | Terra, Aqua, NOAA-20 |
| 2023 | 7,222 | 19,774 | 26,996 | 2.74 | Terra, Aqua, NOAA-20, NOAA-21 |
| 2024 | 10,514 | 33,792 | 44,306 | 3.21 | Terra, Aqua, NOAA-20, NOAA-21 |

### Viewing Zenith Angle (VZA) & Detection Truncation Finding
In our 2020 MODIS sample, median FRP rises with scan size, from 29.1 MW near nadir (1.0–1.5 km) to 159.8 MW at swath edge (3.0–5.0 km). This is consistent with detection truncation / selection bias: at swath edge, pixel area expands ~10×, background radiance is larger, and faint fires fall below detection — only large fires are seen. A scalar multiplier to 'boost' edge FRP would therefore inflate fires that are already large. This does not rule out FRP underestimation for a given fire at large viewing angle — that would require matched pairs of the same fire seen at nadir and at edge, which we have not done. VZA correction remains a documented frontier, not a solved problem.

| Scan Bin (Pixel Width) | Position in Swath | Detections Count | Mean FRP (MW) | Median FRP (MW) | 75th %ile FRP (MW) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| 1.0 – 1.5 km | Near Nadir | 29,488 | 84.5 MW | 29.1 MW | 68.0 MW |
| 1.5 – 2.0 km | Mid-Swath | 7,675 | 156.5 MW | 54.6 MW | 124.9 MW |
| 2.0 – 3.0 km | Off-Nadir | 6,157 | 254.3 MW | 84.2 MW | 200.3 MW |
| 3.0 – 5.0 km | Swath Edge | 4,633 | 409.1 MW | 159.8 MW | 376.0 MW |
| **Total Reconciled** | | **47,953** | | | |

*Reconciliation Note:* All 47,953 raw MODIS detections in 2020 reconcile exactly across the 4 bins. (Exactly 11,087 detections fall at nadir `scan == 1.0 km`, which require inclusive lower bin boundaries `[1.0, 1.5]`).

### External Consistency Check (CAL FIRE Incident Archives)
External check (CAL FIRE 2020 Incident Archive): our peak day, 2020-09-09 (10,320 hotspots), falls during the peak burning of the August Complex (started Aug 16, 2020, 1,032,648 acres) and Creek Fire (started Sep 4, 2020, 379,895 acres). Our 21-day streak, Aug 30 – Sep 19, 2020 (66,764 hotspots), matches the simultaneous explosive growth of the August Complex, Creek Fire, and North Complex (started Aug 17, 2020, 318,935 acres). Furthermore, our 23-day streak, Aug 1–23, 2021 (48,049 hotspots), coincides with the peak run of the Dixie Fire (started Jul 13, 2021, 963,309 acres). This is an external consistency check against official agency incident records, not a formal calibration against post-fire burned area perimeters.

---

## Quickstart

### 1. Live Interactive Web Application
Access the production application directly:
👉 **[https://sekhmet-sync.streamlit.app/](https://sekhmet-sync.streamlit.app/)**

No installation, setup, or API credentials required to explore the multi-scale burning activity calendar, spatial footprint maps, critical period analysis, and search-matched data exports.

### 2. Local Setup (Optional)

```bash
# Clone the repository
git clone https://github.com/arsanisl-code/sekhmet-sync.git
cd sekhmet-sync

# Install lightweight dependencies
pip install -r requirements.txt

# Launch the Streamlit application
streamlit run app.py
```

### 3. Production Deployment & Architecture
The application is deployed live on Streamlit Community Cloud:
- **Production URL:** [https://sekhmet-sync.streamlit.app/](https://sekhmet-sync.streamlit.app/)
- **Data Footprint:** Serves entirely from precomputed, verified CSV files in `data/`:
  - `data/daily_series_harmonised.csv` (56 KB)
  - `data/harmonised_detections.csv` (15.6 MB)

Both files are committed to the repository and are well below GitHub's 100 MB limit. No database or external API credentials are required to serve the web application.

---

## Synthetic Intelligence (SI) / AI Disclosure

In compliance with NASA Space Apps Challenge regulations, the use of AI tools during the development of Sekhmet Sync is fully disclosed:

| Tool | Purpose & Scope | Verification Method |
| :--- | :--- | :--- |
| **Antigravity & Gemini** | Pipeline architecture, data transformation scripting, Streamlit UI refactoring, and headless browser validation | Deterministic unit tests (`pytest`), Streamlit AppTest integration suite, and manual reconciliation scripts |
| **Claude & Codex** | Initial boilerplate drafting, exploratory spatial math, and documentation formatting | Rigorous code review; all clustering algorithms and unsupported scaling heuristics were subsequently audited and removed |
| **Kiro & Muse** | Requirements specification structuring and WCAG contrast ratio calculations | W3C IEC 61966-2-1 piecewise contrast verification scripts and live browser DOM inspection |

**Boundary Statement:** AI tools were utilized strictly for scaffolding, testing, contrast calculation, and code acceleration. All data counts, harmonization thresholds, and geographic boundaries are calculated deterministically against NASA FIRMS source data and US Census Bureau polygons.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Executes the operational verification suite in [`tests/test_lean_pipeline.py`](tests/test_lean_pipeline.py):
1. `test_daily_series_harmonised_integrity`: Verifies 1,827 continuous days (2020–2024), 0 missing dates, leap day alignment, and reconciled totals (347,174 harmonised hotspots, 10,320 peak day).
2. `test_detections_integrity`: Verifies all 347,174 detection coordinates fall inside California bounds, checks sensor counts (MODIS 113,795, VIIRS 233,379), and asserts the 6.5 MW VIIRS threshold.
3. `test_subregion_filtering`: Verifies spatial bounding box slicing for Northern Forests (182,441 hotspots) and Sierra Nevada (73,757 hotspots).
4. `test_out_of_coverage_rule`: Verifies that coordinates outside California halt with `OUT_OF_COVERAGE`.
5. `test_sliced_export_fidelity`: Asserts dynamically generated CSV bytes match the selected date and region filters.
6. `test_app_test_execution_and_views`: Exercises the Streamlit web app and tests all three calendar views (5×366 daily, 5×12 monthly, daily line) with zero exceptions.

---

## Repository Structure & Archived Prototypes

```
sekhmet-sync/
  app.py                         # Streamlit web application
  build_daily_harmonized.py      # Operational daily harmonization pipeline
  generate_exports.py            # Static PNG generator for briefing packs
  requirements.txt               # Lightweight runtime dependencies
  .env.example                   # Sanitized API key template
  data/
    daily_series_harmonised.csv  # 1,827-row operational daily series (56 KB)
    harmonised_detections.csv    # 347,174 harmonised active fire detections (15.6 MB)
    california.geojson           # US Census Bureau TIGER/Line state boundary
  exports/                       # Static presentation visualisations (PNG)
  tests/                         # Active test suite
    test_lean_pipeline.py
  archive/                       # Deprecated exploratory code (NOT used by app)
    legacy_prototype/            # Pre-audit clustering (cluster.py) & 0.85 scaling (harmonize.py)
```

> [!NOTE]
> The `archive/` directory contains exploratory prototype code (`cluster.py` and `harmonize.py`) preserved solely for historical transparency. The operational web application and pipeline do **NOT** import or use these files, relying entirely on direct hotspot threshold harmonization.

---

## Open-Source Citations & Acknowledgments

- **NASA FIRMS (Fire Information for Resource Management System):**
  - MODIS Collection 6.1 active fire product (Terra and Aqua).
  - VIIRS 375 m active fire products (NOAA-20 and NOAA-21 Standard Processing).
  - Web: [https://firms.modaps.eosdis.nasa.gov/](https://firms.modaps.eosdis.nasa.gov/)
- **CAL FIRE (California Department of Forestry and Fire Protection):**
  - 2020 Incident Archive (August Complex, Creek Fire, North Complex): [https://www.fire.ca.gov/incidents/2020](https://www.fire.ca.gov/incidents/2020)
  - 2021 Incident Archive (Dixie Fire): [https://www.fire.ca.gov/incidents/2021](https://www.fire.ca.gov/incidents/2021)
  - Accessed: November 2026.
- **US Census Bureau TIGER/Line:**
  - 2020 California State Boundary Polygon (via PublicaMundi GeoJSON).
- **OpenStreetMap:**
  - Base map cartography tiles for spatial context.
- **Python Open-Source Ecosystem:**
  - `pandas` & `numpy` for data ingestion and matrix operations.
  - `streamlit` for the reactive web application.
  - `plotly` for interactive heatmaps and anomaly charts.
  - `shapely` for vector point-in-polygon boundary validation.
  - `scipy` for statistical verification.

---

## License

Data: NASA FIRMS (Public Domain). Code: MIT License.
