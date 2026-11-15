# Tech Stack Steering — Sekhmet Sync

## Core stack (locked)
- Python 3.11+
- pandas (data wrangling)
- numpy (numerical ops)
- Plotly (all charts; already Chromebook-friendly, no WebGL requirement for 2D charts)
- pyarrow (Parquet I/O)
- Streamlit (web app, deployable to Streamlit Community Cloud)

## Additional libraries (chosen and pinned in requirements.txt)
- scipy — for KD-tree spatial indexing in cluster.py (scipy.spatial.KDTree);
  well-maintained, already a transitive dep of many scientific stacks.
- python-dotenv — read FIRMS_MAP_KEY from .env without shell gymnastics.
- requests — HTTP fetches in fetch_firms.py.
- pytest — test runner.
- kaleido — static PNG export from Plotly figures (required for G5).

## Map library decision
Plotly scatter_mapbox with OpenStreetMap tiles (no API key required, Chromebook-safe).
Rejected Folium (extra JS weight), Pydeck (WebGL), and Kepler.gl (too heavy).

## Caching
Precomputed files read by the app:
  data/ca_2020_2024.parquet        — per-fire harmonised rows
  data/ca_2020_2024_harmonised.csv — same content as CSV for download
  data/daily_series.csv            — 1,827-row daily aggregate

App reads these at startup; no network calls, no clustering logic in app.py.

## Parquet compression
snappy (default pyarrow). Fast decompression on read; files stay small.

## Environment
FIRMS_MAP_KEY read from environment variable. python-dotenv loads .env if present.
If key is absent, fetch_firms.py skips API calls and expects manual CSVs in data/raw/.

## Dependency pinning
All versions pinned with == in requirements.txt.
Pin strategy: use latest stable as of 2025-07-15, test, then lock.
