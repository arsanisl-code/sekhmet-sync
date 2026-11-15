# Product Steering — Sekhmet Sync

## Purpose
Fuse MODIS C6.1 and VIIRS NOAA-20/21 active-fire detections from NASA FIRMS into one
California fire history (2020–2024). Present it as a burning-activity calendar with
historical-median comparison, sensor toggle, and CSV downloads. Primary users:
emergency managers, land managers, and researchers who need one true fire history.

## Target awards
Best Use of Data and Best Use of Technology.

## Mandatory user-facing features (non-negotiable)
1. Always-visible stat cards: raw detections, harmonised fires, % duplicates removed,
   total FRP (corrected), peak day.
2. Sensor toggle: MODIS alone | VIIRS alone | Harmonised. Changes map, calendar,
   stat cards, and download contents.
3. Burning-activity calendar: rows = years 2020–2024, columns = day of year,
   color = harmonised fires (default) or FRP.
4. Anomaly view: daily harmonised fires vs. historical median, anomaly shaded,
   worst days highlighted.
5. Map: fire centroids sized by total FRP, colored by sensors_present.
6. Top 10 fires table, sortable.
7. "Why harmonisation matters" section with the discontinuity chart.
8. Downloads: daily_series.csv and ca_2020_2024_harmonised.csv — must work in a
   real browser.
9. Method and Limitations box.

## What the app must NOT do
- Re-cluster or call the API on page load.
- Load in more than 5 seconds from cached files.
- Use GPU-dependent or heavy client-side libraries (Chromebook constraint).
- Embed NASA logos, flags, mission patches, or mission identifiers.
- Present simulated, randomized, or AI-generated data as real fire data.

## Header (exact text)
"Sekhmet Sync — Harmonizing MODIS and VIIRS Hot Spots"
Subtitle: "Make 20+ years of fire data from two different satellites tell one true story."
Note below subtitle: "Shipped scope: California 2020–2024."

## Honest claims
The defensible claim is distributional: counts and total FRP per day after
deduplication, with an approximate, documented correction. We do not claim exact
per-fire FRP harmonization. This disclaimer must appear in the app, the README, and
the final report.
