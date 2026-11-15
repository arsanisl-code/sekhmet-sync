# Structure Steering — Sekhmet Sync

## Repository layout (required minimum + additions)
```
sekhmet-sync/
  fetch_firms.py          # acquisition: FIRMS API or manual archive CSVs
  cluster.py              # deduplication via spatial hash + KDTree
  harmonize.py            # daily aggregation, FRP correction, historical median
  app.py                  # Streamlit UI only — reads precomputed outputs
  discontinuity.py        # 2011–2013 demo (S-NPP exception, labelled)
  requirements.txt
  .env.example
  .gitignore
  README.md
  DECISIONS.md
  PITCH_OUTLINE.md
  data/
    raw/                  # FIRMS CSVs as downloaded; gitignored if >10 MB each
    ca_2020_2024.parquet
    ca_2020_2024_harmonised.csv
    daily_series.csv
  exports/
    map.png
    calendar.png
    discontinuity.png
  tests/
    test_cluster.py
    test_harmonize.py
    fixtures/             # synthetic CSVs for unit tests ONLY; never reach data/
  .kiro/
    steering/
      product.md
      tech.md
      structure.md
      rules.md
    specs/sekhmet-sync/
      requirements.md
      design.md
      tasks.md
```

## Module responsibilities (strict)
- fetch_firms.py: network + file I/O only. Outputs raw CSVs to data/raw/.
- cluster.py: reads raw CSVs, outputs ca_2020_2024.parquet. No UI code.
- harmonize.py: reads parquet, outputs daily_series.csv and ca_2020_2024_harmonised.csv.
- app.py: reads data/ files only. Zero clustering, zero API calls.
- discontinuity.py: self-contained; reads its own raw CSVs from data/raw/,
  writes exports/discontinuity.png.

## Test fixtures rule
Synthetic fire data lives ONLY in tests/fixtures/. File names must end in
_fixture.csv. Test docstrings must include "SYNTHETIC TEST DATA — not real FIRMS data".
These files must never be imported or read by any non-test module.

## Git hygiene
.gitignore must cover: .env, data/raw/*.csv (raw downloads can be large),
__pycache__, *.pyc, .DS_Store, *.parquet (regenerable from raw), and any file >100 MB.
Committed artifacts: requirements.txt, all .py files, README, DECISIONS, PITCH_OUTLINE,
exports/*.png, data/daily_series.csv, data/ca_2020_2024_harmonised.csv.
(CSV exports are small enough to commit; they let the app run without re-running the pipeline.)
