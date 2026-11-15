# Fixed Rules Steering — Sekhmet Sync

These rules come from the challenge brief. They override any design preference.

## R1 — Real data only
Use NASA FIRMS data only. Never generate, simulate, randomize, or fill in fire data.
Never present an AI-generated image as data.
If a fetch fails: stop that step, report the exact error and what was tried,
then use the documented fallback (manual archive CSVs in data/raw/).
If no real data is available at all: halt and say so. Do not continue with
placeholder data.

## R2 — Scope
California only. Bounding box: lat 32.5–42.0, lon −124.5–−114.0.
Dates: 2020-01-01 to 2024-12-31. No other regions. Do not download the global archive.

## R3 — Sensors in the main pipeline
MODIS C6.1 (Terra and Aqua), VIIRS NOAA-20, VIIRS NOAA-21.
VIIRS S-NPP must NOT appear in the main pipeline.
S-NPP may appear ONLY in discontinuity.py (2011–2013 demo), clearly labelled.

## R4 — Claims
The defensible claim is distributional: counts and total FRP per day after
deduplication, with an approximate, documented correction.
Do not claim exact per-fire FRP harmonization.
This disclaimer appears in the app, the README, and the final report.

## R5 — Secrets
Read the key from environment variable FIRMS_MAP_KEY.
Never hard-code or commit the key.
Provide .env.example with FIRMS_MAP_KEY=PASTE_YOUR_KEY_HERE.
The app must work from cached files when no key is set.

## R6 — Branding
No NASA logos, flags, mission patches, or mission identifiers in the app or exports.
Use the project name "Sekhmet Sync" only.

## R7 — Viewing constraint
The demo machine is a Chromebook. The app must be deployable to a hosted URL
(e.g., Streamlit Community Cloud). The repo must contain everything needed to deploy.
Static PNG exports must exist so the pitch survives a live-demo failure.

## R8 — Clustering complexity
Clustering must not be O(n²). Use a spatial hash or KD-tree.
Document the complexity and show measured scaling (1× and ~2× input size, ratio sub-quadratic).

## Gates (must pass before moving to next phase)
G1 Data       — rows per sensor/year, date range, confidence drops, errors/fallback status
G2 Clustering — unit tests pass; full run reports N, M, % removed, runtime; scaling shown
G3 Reconcile  — 1,827 daily rows; sums match; FRP matches within float tolerance
G4 App        — loads <5 s from cache; sensor toggle changes numbers; downloads work
G5 Exports    — map.png, calendar.png, discontinuity.png generated from real data
G6 Deployment — requirements.txt pinned; committed artifacts <100 MB; README deploy steps
