# Sekhmet Sync

**NASA International Space Apps Challenge 2026 — Harmonization of MODIS and VIIRS Hot Spots**

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

### The Problem: Sensor Discontinuity
MODIS (1 km pixel resolution) and VIIRS (375 m pixel resolution) observe fires at vastly different sensitivities. For the exact same fires in California, VIIRS detects over 5.3× more hotspots than MODIS. Treating them interchangeably creates an artificial surge in fire frequency whenever VIIRS data is added.

### The Solution: Direct Hotspot Counting with 6.5 MW Threshold
- **Dropped Spatial Clustering:** The prompt asks for *"number of hotspots detected"*, not synthetic clusters or "fires". Clustering algorithms introduce chaining artifacts (e.g., merging separate blazes into a 5,542-detection mega-fire) and spatial distortion. Sekhmet Sync counts harmonised hotspots directly.
- **Experimental 6.5 MW Cutoff:** VIIRS 375 m sensors detect faint sub-pixel burns that fall below MODIS detection capabilities. Testing S-NPP vs MODIS on pre-drift California fire records (2012–2013) demonstrated that filtering VIIRS at $\text{FRP} \ge 6.5\text{ MW}$ aligns monthly counts with MODIS at $r = 0.9974$ and $-4.8\%$ bias.
- **Honest Labeling:** This baseline is empirical and labeled **experimental**; it is not presented as an unchallengeable physical law. Uniform scalar multipliers (e.g., 0.85) were explicitly tested and rejected as physically ungrounded.

---

## Quickstart

### 1. Local Run

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/sekhmet-sync.git
cd sekhmet-sync

# Install lightweight dependencies
pip install -r requirements.txt

# Launch the Streamlit application
streamlit run app.py
```
Open [http://localhost:8502](http://localhost:8502) in your browser.

### 2. Streamlit Community Cloud Deployment
The application runs entirely from precomputed, verified CSV files in `data/`:
- `data/daily_series_harmonised.csv` (56 KB)
- `data/harmonised_detections.csv` (15.6 MB)

Both files are committed to the repository and are well below GitHub's 100 MB limit.
1. Connect your GitHub repository to [share.streamlit.io](https://share.streamlit.io).
2. Set Main file path to `app.py`.
3. Deploy! No database or external API credentials are required to serve the web application.

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

## Open-Source Citations & Acknowledgments

- **NASA FIRMS (Fire Information for Resource Management System):**
  - MODIS Collection 6.1 active fire product (Terra and Aqua).
  - VIIRS 375 m active fire products (NOAA-20 and NOAA-21 Standard Processing).
  - Web: [https://firms.modaps.eosdis.nasa.gov/](https://firms.modaps.eosdis.nasa.gov/)
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
