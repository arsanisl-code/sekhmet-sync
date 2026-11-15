# Tasks — Sekhmet Sync

Tasks are ordered by dependency. Do not start a task before its dependencies pass.

---

## TASK-01 Scaffolding and configuration files
**Depends on:** nothing
**Acceptance:** All required files and directories exist. Steering and spec files
committed. .env.example, .gitignore, requirements.txt present. DECISIONS.md present.

Subtasks:
- [x] Create .kiro/steering/ files (product, tech, structure, rules)
- [x] Create .kiro/specs/sekhmet-sync/ files (requirements, design, tasks)
- [ ] Write .env.example
- [ ] Write .gitignore
- [ ] Write requirements.txt (pinned)
- [ ] Write DECISIONS.md (initial)
- [ ] Write PITCH_OUTLINE.md (placeholder structure, to be filled with real numbers at end)
- [ ] Update README.md

**Gate:** None (scaffolding step)

---

## TASK-02 Data acquisition — fetch_firms.py
**Depends on:** TASK-01
**Acceptance (Gate G1):**
- fetch_firms.py runs without error when FIRMS_MAP_KEY is set.
- data/raw/ contains files for MODIS_SP (2020–2024), VIIRS_NOAA20_SP (2020–2024),
  VIIRS_NOAA21_SP (2023–2024).
- Log shows rows per sensor per year, date range, confidence drops.
- If key is absent, the script exits with a clear message and manual fallback instructions.

Subtasks:
- [ ] Implement fetch loop: for each product × year, call FIRMS area API in 5-day chunks
      (API limit is 10 days max; use 5 to stay safe), write to data/raw/.
- [ ] Implement confidence filter with logging.
- [ ] Implement bbox post-filter with logging.
- [ ] Implement fallback message and manual download checklist.
- [ ] Run and capture G1 log.

---

## TASK-03 Unit tests for clustering — tests/test_cluster.py
**Depends on:** TASK-01
**Acceptance (Gate G2 partial):**
- pytest tests/test_cluster.py passes with all test cases green.
- Cases: boundary, midnight UTC, consecutive days, empty input, mixed sensors, single detection.

Subtasks:
- [ ] Write tests/fixtures/ synthetic CSVs.
- [ ] Write test_cluster.py with all required cases.
- [ ] Run pytest and confirm pass.

---

## TASK-04 Clustering — cluster.py
**Depends on:** TASK-02 (data present), TASK-03 (tests pass)
**Acceptance (Gate G2):**
- Full clustering run completes.
- data/ca_2020_2024.parquet written with correct schema.
- G2 report: N, M, % removed, runtime.
- Scaling test: 50% run vs 100% run, ratio < 2.0.

Subtasks:
- [ ] Implement load + unified schema.
- [ ] Implement KDTree + union-find clustering, one day at a time.
- [ ] Implement output with fire_id CA-YYYY-MM-DD-NNN format.
- [ ] Run full pipeline and emit G2 report.
- [ ] Run scaling test.

---

## TASK-05 Unit tests for harmonization — tests/test_harmonize.py
**Depends on:** TASK-04 (schema known)
**Acceptance:** pytest tests/test_harmonize.py passes.

---

## TASK-06 Harmonization — harmonize.py
**Depends on:** TASK-04 (parquet present), TASK-05 (tests pass)
**Acceptance (Gate G3):**
- daily_series.csv has exactly 1,827 rows with correct column order.
- Sum of harmonised_fires equals row count in ca_2020_2024_harmonised.csv.
- Sum of n_detections equals N.
- FRP sums match within rtol=1e-5.

Subtasks:
- [ ] Implement daily aggregation.
- [ ] Implement FRP correction.
- [ ] Implement historical median and anomaly columns.
- [ ] Write reconciliation check (exits with error if G3 fails).
- [ ] Run and capture G3 results.

---

## TASK-07 App — app.py
**Depends on:** TASK-06 (data files present)
**Acceptance (Gate G4):**
- Streamlit app loads in < 5 s from cached files.
- Sensor toggle changes stat cards, map, calendar, download contents.
- Both CSV downloads return valid CSV.
- No clustering or API calls on page load.

Subtasks:
- [ ] Implement sidebar and sensor toggle.
- [ ] Implement stat cards.
- [ ] Implement map tab (scatter_mapbox).
- [ ] Implement calendar tab.
- [ ] Implement anomaly tab.
- [ ] Implement top-10 fires tab.
- [ ] Implement "Why harmonisation matters" tab.
- [ ] Implement downloads.
- [ ] Implement Method and Limitations box.
- [ ] Manual browser test or Playwright script for G4.

---

## TASK-08 Discontinuity demo — discontinuity.py
**Depends on:** TASK-02 (fetch infrastructure exists; SNPP data fetched here separately)
**Acceptance (Gate G5 partial):**
- exports/discontinuity.png saved.
- Chart title correct.
- Honest continuity assessment printed.

---

## TASK-09 Static exports — map.png and calendar.png
**Depends on:** TASK-06 (data present), TASK-07 (chart code exists)
**Acceptance (Gate G5):**
- exports/map.png and exports/calendar.png saved.
- Both generated from real data.

---

## TASK-10 Deployment docs and final checks
**Depends on:** all prior tasks
**Acceptance (Gate G6):**
- requirements.txt pinned and complete.
- Committed artifacts each < 100 MB.
- README has step-by-step Streamlit Community Cloud deploy section.
- DECISIONS.md complete.
- PITCH_OUTLINE.md filled with real numbers.
- Final report written.
