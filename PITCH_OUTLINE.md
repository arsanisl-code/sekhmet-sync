# PITCH_OUTLINE — Sekhmet Sync

**NASA International Space Apps Challenge 2026 — Harmonization of MODIS and VIIRS Hot Spots**

7 slides. Every statistic is reconciled against raw NASA FIRMS inputs.
The burning activity calendar is presented across three complementary temporal scales — covering **seasonal patterns, multi-year trends, and unusual critical days** without inventing redundant visualizations.

---

## Slide 1 — Problem + Hook
**Title:** Two Satellites. Two Fire Records. Zero Continuity.

- In California (2020–2024), MODIS counted **113,795** active-fire hotspots.
- Over the exact same period, VIIRS counted **608,801** hotspots — **5.35× more**.
- Neither sensor is "wrong": VIIRS has 375 m pixels that resolve tiny, faint burns, while MODIS has 1 km pixels.
- If an emergency manager or scientist looks at the raw combined record, it looks like fire activity exploded overnight.
- Without harmonization, you cannot tell whether the fire regime changed or the satellite did.

**Visual:** Side-by-side comparison card: MODIS (113,795) vs. VIIRS (608,801) raw California hotspots.

---

## Slide 2 — The Overview: Seasonal Patterns & Trends
**Title:** Five Years of California Fire: The Monthly Heatmap (5×12)

- Aggregates **347,174 harmonised hotspots** into a clean 5-year × 12-month calendar rollup.
- **Seasonal Pattern:** California burning strictly concentrates in late summer and early autumn (August–October accounting for >75% of annual burning). Winter and spring remain quiet (<1.5k hotspots/month).
- **Multi-Year Macro Trends:**
  - **2020 (Extreme Wildfire Crisis):** September alone peaked at **79,417** harmonised hotspots.
  - **2021 (Dixie / Caldor Fires):** Massive August surge (**66,729** hotspots).
  - **2022–2023 (Atmospheric Rivers):** Subdued fire seasons (September peaks dropped to 4k–5k).
  - **2024 (Park Fire):** Early July surge (**19,700** hotspots).

**Visual:** `exports/monthly_heatmap.png` — High-contrast 5×12 monthly rollup heatmap with cell labels.

---

## Slide 3 — The Harmonization Method
**Title:** Direct Hotspot Harmonization via 6.5 MW Threshold

- **Dropped Spatial Clustering:** The challenge specifically asks for "number of hotspots detected" to create a burning activity calendar, not synthetic "fires". Clustering introduces arbitrary chaining rules and creates artificial 5,000+ detection mega-fires.
- **The 6.5 MW Threshold:** We count hotspots directly. VIIRS detections below 6.5 MW represent sub-pixel heat that MODIS cannot detect.
- Filtering VIIRS at $\text{FRP} \ge 6.5\text{ MW}$ aligns VIIRS detection frequency with MODIS sensitivity (tested on pre-drift California holdout: $r = 0.9974$, bias $-4.8\%$).
- **The Numbers:**
  - 375,422 faint detections filtered ($61.7\%$ of raw VIIRS; $52.0\%$ of total raw).
  - **347,174 harmonised California hotspots** (113,795 MODIS + 233,379 VIIRS $\ge 6.5\text{ MW}$).

**Visual:** Flow diagram: 722,596 raw detections $\to$ 6.5 MW threshold filter $\to$ 347,174 harmonised hotspots.

---

## Slide 4 — The Main Calendar: Daily Intra-Season Ignition Bursts
**Title:** The Burning Activity Calendar (5×366 Daily Matrix)

- **The Main Calendar:** Displays every day from 2020 through 2024 across 366 day-of-year slots in a single unified matrix, correctly handling leap days (2020 and 2024).
- **Daily Ignition Precision:** Reveals intra-seasonal ignition bursts and exact peak burning periods across all 1,827 continuous days.
- **Statewide Peak Day:** **2020-09-09 with 10,320 harmonised hotspots** during the catastrophic August Complex / North Complex fire storm.
- **Sub-Region Slicing:** Responsive to regional ecosections (Northern Forests, Sierra Nevada, Southern Chaparral, or custom bounding box).

**Visual:** `exports/calendar.png` — The 5×366 burning activity calendar heatmap with peak day marker.

---

## Slide 5 — Unusual Days & Critical Periods: The Anomaly View
**Title:** Tracking Deviations: Daily Line Chart vs. 5-Year Median

- **Detecting Anomalies:** Compares daily harmonised hotspot counts against the 5-year reference median line (dashed green).
- **Above vs. Below Median:** Shaded red areas instantly highlight critical fire outbreaks; shaded blue shows damp, suppressed periods.
- **Top Anomaly Days:** Flags extreme breakout events (e.g. 2020-09-09 with +10,183 hotspots above seasonal median; 2021-08-18 with +3,900 hotspots).
- **Early Warning & Response:** Land managers can evaluate whether an active fire event represents typical seasonal burning or an unprecedented emergency crisis.

**Visual:** `exports/anomaly_daily.png` — Daily time series line chart with historical median baseline and peak markers.

---

## Slide 6 — Why Harmonization Matters & Honest Science
**Title:** Without Harmonization, History Lies

- **The Discontinuity Problem:** In 2011–2013, launching VIIRS S-NPP created an artificial 3.6× jump in reported hotspots overnight. Harmonization flattens this step-function to preserve true historical continuity.
- **Honest Scope:** Focused on California 2020–2024. We do not claim global coverage or early 2000s solved — we deliver a verified regional prototype.
- **Empirical Baseline:** The 6.5 MW threshold is empirical and labeled **experimental**. We tested and rejected arbitrary scalar multipliers (like 0.85) because sensor physics does not support a single multiplier.
- **Out-of-Coverage Guard:** Coordinates outside California trigger: *"Selected area is outside the California data archive — no coverage"* rather than falsely reporting 0 fires.

**Visual:** Sensor step-function chart & Method and Limitations disclosure.

---

## Slide 7 — Live Demo & Future Vision
**Title:** Sekhmet Sync — Accessible and Deployable Today

- **Zero-Friction Access:** Runs locally or deploys instantly to Streamlit Community Cloud with precomputed, committed flat files (no heavy database or external API dependencies).
- **Chromebook-Ready:** Responsive UI with custom CSS preventing ellipsis truncation on standard 1366×768 screens; WCAG AA/AAA accessible Egyptian palette.
- **Interactive Multi-Scale Calendar:** Users can toggle between the 5×366 Daily Matrix, 5×12 Monthly Heatmap, and Daily Anomaly Line in one click, plus download search-matched sliced CSVs.
- **Next Steps:**
  - Extend pre-drift reference baseline back to 2000 using historical MODIS archives.
  - Expand threshold calibration across additional global fire biomes.

**Visual:** Live app dashboard with interactive calendar view selector and metric cards.
