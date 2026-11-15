# Sekhmet Sync — Extended Harmonised Series Manifest

> **WARNING:** A naive 2000–2024 sum would show a spurious ~3x rise that is
> mostly more satellites in orbit, not more fire. `harmonised_hotspots` does
> NOT correct for this. Use `harmonised_hotspots_satnorm` for multi-decade
> comparison — treat it as **experimental**.
>
> In 2020–2024, 73.8% of harmonised detections are VIIRS-only. Sensor still matters.

## Threshold label
> VIIRS >=6.5 MW — experimental, fitted on California 2012-2013 monthly overlap
> (r=0.9974, monthly only). Not validated on daily 2020-2024 data or outside California.

## Constellation

| Years | Era | VIIRS sats | Satnorm div |
|-------|-----|------------|-------------|
| 2000–2001 | Terra-only | 0 | 1 |
| 2002–2011 | Terra+Aqua | 0 | 1 |
| 2012–2017 | Terra+Aqua+S-NPP | 1 | 1 |
| 2018–2022 | Terra+Aqua+S-NPP+NOAA-20 | 2 | 2 |
| 2023–2024 | Terra+Aqua+NOAA-20+NOAA-21 | 2 | 2 |

## Per-year reconciliation

| Year | MODIS in-state | VIIRS in-state | Harmonised (daily) | Era |
|------|---------------|---------------|-------------------|-----|
| 2000 | 434 | 0 | 434 | Terra-only |
| 2001 | 3,071 | 0 | 3,071 | Terra-only |
| 2002 | 7,091 | 0 | 7,091 | Terra+Aqua |
| 2003 | 10,848 | 0 | 10,848 | Terra+Aqua |
| 2004 | 6,121 | 0 | 6,121 | Terra+Aqua |
| 2005 | 4,846 | 0 | 4,846 | Terra+Aqua |
| 2006 | 10,892 | 0 | 10,892 | Terra+Aqua |
| 2007 | 12,345 | 0 | 12,345 | Terra+Aqua |
| 2008 | 20,913 | 0 | 20,913 | Terra+Aqua |
| 2009 | 7,901 | 0 | 7,901 | Terra+Aqua |
| 2010 | 2,811 | 0 | 2,811 | Terra+Aqua |
| 2011 | 3,430 | 0 | 3,430 | Terra+Aqua |
| 2012 | 8,744 | 13,449 | 22,193 | Terra+Aqua+S-NPP |
| 2013 | 9,826 | 15,664 | 25,490 | Terra+Aqua+S-NPP |
| 2014 | 7,896 | 39,676 | 20,173 | Terra+Aqua+S-NPP |
| 2015 | 10,888 | 54,417 | 28,120 | Terra+Aqua+S-NPP |
| 2016 | 8,591 | 35,862 | 22,164 | Terra+Aqua+S-NPP |
| 2017 | 16,886 | 75,075 | 45,624 | Terra+Aqua+S-NPP |
| 2018 | 20,281 | 161,825 | 82,256 | Terra+Aqua+S-NPP+NOAA-20 |
| 2019 | 5,602 | 48,701 | 21,014 | Terra+Aqua+S-NPP+NOAA-20 |
| 2020 | 46,823 | 228,701 | 140,092 | Terra+Aqua+S-NPP+NOAA-20 |
| 2021 | 42,522 | 194,162 | 119,933 | Terra+Aqua+S-NPP+NOAA-20 |
| 2022 | 6,714 | 31,486 | 15,847 | Terra+Aqua+S-NPP+NOAA-20 |
| 2023 | 7,222 | 65,181 | 26,996 | Terra+Aqua+NOAA-20+NOAA-21 |
| 2024 | 10,514 | 89,271 | 44,306 | Terra+Aqua+NOAA-20+NOAA-21 |

## Reconciliation checks

- Daily sum harmonised: **704,911**
- Detections file rows: **704,911**
- Match: PASS
- Peak day (2000-2024): **2020-09-09** / **10,320**
- 2020-2024 subset: **347,174** (frozen: 347,174) — PASS
- Gate 2: PASS | Gate 3: PASS
- Generated: 2026-11-15T05:05:18Z | 36s
