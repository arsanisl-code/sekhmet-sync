# Archived Legacy Prototype (Deprecated / Not Used by Operational App)

> [!WARNING]
> **DO NOT USE FOR EVALUATION:** The code and tests in this directory represent an exploratory pre-audit prototype. They are **NOT** imported or used by the operational web application (`app.py`), the daily harmonization pipeline (`build_daily_harmonized.py`), or the presentation exports (`generate_exports.py`).

### Why These Files Were Deprecated and Archived:

1. **Rejection of Spatial Clustering (`cluster.py`):**
   - The NASA Space Apps challenge asks for the *"number of hotspots detected"* to build a burning activity calendar, not synthetic clustered "fires".
   - Spatial clustering via KD-tree and union-find introduced arbitrary distance chaining artifacts (e.g. merging blazes into an artificial 5,542-detection entity) and projection distortions across California.
   - The operational application directly counts harmonized active-fire hotspots per day.

2. **Rejection of Uniform 0.85 FRP Multiplier (`harmonize.py`):**
   - Literature (e.g. Li et al. 2018, Sofiev & Kouznetsov) contradicts applying a uniform 0.85 scalar factor between sensors with disparate point-spread functions and saturation regimes.
   - The operational application uses an empirical **6.5 MW FRP threshold** on VIIRS observations (tested on pre-drift California holdouts: $r=0.9974$, bias $-4.8\%$), transparently labeled **experimental**.

For the active operational codebase, see:
- [`app.py`](../../app.py): The Streamlit web application.
- [`build_daily_harmonized.py`](../../build_daily_harmonized.py): The operational daily harmonization pipeline.
- [`DECISIONS.md`](../../DECISIONS.md): Architectural decisions and method rationale.
- [`tests/test_lean_pipeline.py`](../../tests/test_lean_pipeline.py): Active test suite.
