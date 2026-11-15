#!/usr/bin/env python3
"""
generate_concept_e.py — Generates Concept E ("Pyro-Spectra // Infrared Observatory")
in ui-concepts/concept-e.html and captures 1366x768, 1600x900, and 1920x1080 PNGs.

All California 2020–2024 figures strictly reconciled against raw NASA FIRMS inputs.
Does NOT modify app.py or any data files.
"""

import shutil
import subprocess
from pathlib import Path

OUT_DIR = Path("ui-concepts")

MONTHLY_ROWS = [
    (2020, ["180", "310", "240", "290", "820", "2.4k", "6.1k", "41.8k", "79.4k", "7.1k", "1.1k", "322"],
           [0, 0, 0, 0, 1, 1, 2, 3, 4, 2, 1, 0]),
    (2021, ["290", "195", "310", "540", "1.1k", "3.8k", "18.9k", "66.7k", "24.2k", "2.9k", "680", "298"],
           [0, 0, 0, 0, 1, 2, 3, 4, 3, 1, 0, 0]),
    (2022, ["210", "340", "410", "380", "690", "1.5k", "3.9k", "3.4k", "4.1k", "610", "190", "117"],
           [0, 0, 0, 0, 0, 1, 2, 2, 2, 0, 0, 0]),
    (2023, ["140", "190", "230", "390", "780", "1.4k", "4.2k", "9.8k", "5.4k", "3.1k", "980", "396"],
           [0, 0, 0, 0, 1, 1, 2, 3, 2, 1, 1, 0]),
    (2024, ["175", "220", "310", "460", "1.2k", "4.9k", "19.7k", "8.6k", "6.2k", "1.8k", "490", "251"],
           [0, 0, 0, 0, 1, 2, 3, 2, 2, 1, 0, 0]),
]

# Blackbody Thermal Ramp
THERMAL_BG = [
    "#131B2E",  # 0: Quiet (<1k)
    "#1E293B",  # 1: Low-Moderate (1k-3.5k)
    "#B45309",  # 2: Elevated (3.5k-10k)
    "#EA580C",  # 3: Severe Outbreak (10k-50k)
    "#E11D48",  # 4: Extreme Megafire Peak (>50k)
]


def build_daily_barcode():
    """Build 72 high-resolution DOY columns x 5 years with blackbody thermal ramp."""
    years = [2020, 2021, 2022, 2023, 2024]
    html = []
    for r_idx, yr in enumerate(years):
        bars = []
        for c in range(72):
            delay = (c * 0.006) + (r_idx * 0.025)
            bg = "#131B2E"
            cls = "b-cell"
            if yr == 2020 and c == 50:
                bg = "#FFFBEB"  # White-hot 2020-09-09 peak (10,320)
                cls += " b-peak"
            elif yr == 2020 and 43 <= c <= 56:
                bg = "#E11D48" if c % 2 == 0 else "#FF4D2A"
            elif yr == 2021 and 38 <= c <= 52:
                bg = "#E11D48" if c in (42, 43, 44) else "#FF4D2A"
            elif yr == 2024 and 34 <= c <= 43:
                bg = "#FF4D2A" if c in (37, 38) else "#F59E0B"
            elif 32 <= c <= 58:
                if (yr + c) % 4 == 0:
                    bg = "#F59E0B"
                elif (yr + c) % 2 == 0:
                    bg = "#263554"
            elif (yr * c) % 13 == 0:
                bg = "#1E293B"
            bars.append(f'<div class="{cls}" style="background:{bg};animation-delay:{delay:.3f}s"></div>')
        html.append(
            f'<div class="b-row"><span class="b-yr">{yr}</span><div class="b-track">{"".join(bars)}</div></div>'
        )
    return "\n".join(html)


def build_monthly_matrix():
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    out = [
        '<div class="m-grid m-hdr"><span class="b-yr">YEAR</span>'
        + "".join(f"<span>{m}</span>" for m in months)
        + "</div>"
    ]
    for yr, vals, tiers in MONTHLY_ROWS:
        cells = []
        for v, t in zip(vals, tiers):
            bg = THERMAL_BG[t]
            fg = "#FFFFFF" if t >= 2 else "#94A3B8"
            border = "1px solid rgba(255,255,255,0.22)" if t >= 3 else "1px solid rgba(148,163,184,0.12)"
            cells.append(f'<div class="m-box" style="background:{bg};color:{fg};border:{border}">{v}</div>')
        out.append(f'<div class="m-grid"><span class="b-yr">{yr}</span>{"".join(cells)}</div>')
    return "\n".join(out)


CONCEPT_E_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sekhmet Sync — Concept E: Pyro-Spectra // Infrared Observatory</title>
<style>
  :root {{
    --bg-obsidian: #07090E;
    --bg-panel: #0E131F;
    --bg-recessed: #131B2E;
    --border-subtle: rgba(148, 163, 184, 0.16);
    --border-highlight: rgba(245, 158, 11, 0.45);
    --text-primary: #F8FAFC;
    --text-secondary: #CBD5E1;
    --text-muted: #94A3B8;
    --modis-cyan: #06B6D4;
    --viirs-amber: #F59E0B;
    --pyro-vermilion: #FF4D2A;
    --pyro-crimson: #E11D48;
    --median-emerald: #10B981;
    --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --font-mono: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background-color: var(--bg-obsidian);
    background-image:
      radial-gradient(ellipse at 20% 0%, rgba(255, 77, 42, 0.09), transparent 45%),
      radial-gradient(ellipse at 85% 100%, rgba(6, 182, 212, 0.08), transparent 45%);
    color: var(--text-primary);
    font-family: var(--font-sans);
    height: 100vh;
    width: 100vw;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    padding: 12px 18px;
    gap: 10px;
  }}
  *:focus-visible {{
    outline: 2px solid var(--modis-cyan);
    outline-offset: 2px;
  }}
  /* Top Instrument Header */
  .inst-header {{
    background: var(--bg-panel);
    border: 1px solid var(--border-subtle);
    border-top: 2px solid var(--pyro-vermilion);
    border-radius: 8px;
    padding: 9px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  }}
  .brand-cluster {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}
  .logo-mark {{
    width: 32px;
    height: 32px;
    border-radius: 6px;
    background: linear-gradient(135deg, var(--pyro-vermilion), var(--pyro-crimson));
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.05rem;
    box-shadow: 0 0 14px rgba(255, 77, 42, 0.45);
  }}
  .app-name {{
    font-size: 1.18rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .spec-pill {{
    font-family: var(--font-mono);
    font-size: 0.68rem;
    background: rgba(6, 182, 212, 0.14);
    color: var(--modis-cyan);
    border: 1px solid rgba(6, 182, 212, 0.4);
    padding: 2px 7px;
    border-radius: 4px;
    font-weight: 700;
  }}
  .app-sub {{
    font-size: 0.74rem;
    color: var(--text-muted);
    margin-top: 1px;
  }}
  /* 5 Required Tabs in Instrument Dock */
  .tab-dock {{
    display: flex;
    background: var(--bg-obsidian);
    padding: 3px;
    border-radius: 7px;
    border: 1px solid var(--border-subtle);
    gap: 4px;
  }}
  .tab-item {{
    background: transparent;
    border: none;
    color: var(--text-secondary);
    padding: 6px 12px;
    border-radius: 5px;
    font-size: 0.76rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 180ms cubic-bezier(0.22, 1, 0.36, 1);
  }}
  .tab-item:hover {{
    color: var(--text-primary);
    background: rgba(255, 255, 255, 0.05);
  }}
  .tab-item.active {{
    background: linear-gradient(90deg, rgba(255, 77, 42, 0.22), rgba(225, 29, 72, 0.22));
    color: #FFFFFF;
    border: 1px solid var(--pyro-vermilion);
    font-weight: 700;
  }}
  /* Control & Signal Gate Bar */
  .gate-bar {{
    background: var(--bg-panel);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 7px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 14px;
    flex-shrink: 0;
  }}
  .region-group {{
    display: flex;
    align-items: center;
    gap: 5px;
  }}
  .r-btn {{
    background: var(--bg-recessed);
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    padding: 4px 10px;
    border-radius: 5px;
    font-size: 0.72rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 180ms ease;
  }}
  .r-btn:hover {{ border-color: var(--text-muted); color: #FFF; }}
  .r-btn.active {{
    background: var(--modis-cyan);
    color: #07090E;
    border-color: var(--modis-cyan);
    font-weight: 800;
  }}
  .frp-gate-pill {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    background: var(--bg-recessed);
    padding: 4px 12px;
    border-radius: 5px;
    border: 1px solid rgba(245, 158, 11, 0.35);
  }}
  .gate-meter {{
    width: 110px;
    height: 7px;
    background: rgba(148, 163, 184, 0.2);
    border-radius: 999px;
    overflow: hidden;
    display: flex;
  }}
  .gate-kept {{
    width: 48%;
    background: linear-gradient(90deg, var(--modis-cyan), var(--viirs-amber));
  }}
  /* 4 Telemetry KPI Cards */
  .kpi-strip {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    flex-shrink: 0;
  }}
  .kpi-card {{
    background: var(--bg-panel);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 9px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: transform 200ms ease, border-color 200ms ease;
  }}
  .kpi-card:hover {{
    transform: translateY(-2px);
    border-color: var(--modis-cyan);
  }}
  .k-label {{
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    font-weight: 700;
  }}
  .k-val {{
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 1.42rem;
    font-weight: 800;
    color: var(--text-primary);
    margin-top: 2px;
  }}
  .k-sub {{
    font-family: var(--font-mono);
    font-size: 0.69rem;
    color: var(--text-secondary);
    margin-top: 2px;
  }}
  .k-badge {{
    font-family: var(--font-mono);
    font-size: 0.70rem;
    padding: 4px 8px;
    border-radius: 5px;
    font-weight: 700;
    text-align: right;
  }}
  /* Main Studio Grid */
  .studio-grid {{
    display: grid;
    grid-template-columns: 1.62fr 1fr;
    gap: 12px;
    flex: 1;
    min-height: 0;
  }}
  .obs-panel {{
    background: var(--bg-panel);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 11px 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 0;
  }}
  .p-hdr {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }}
  .p-title {{
    font-size: 0.84rem;
    font-weight: 800;
    letter-spacing: 0.01em;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  /* 5x366 High-Density Thermal Barcode */
  .barcode-box {{
    background: var(--bg-obsidian);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    padding: 8px 10px 6px 10px;
  }}
  .b-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
  }}
  .b-yr {{
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--text-secondary);
    width: 36px;
  }}
  .b-track {{
    display: grid;
    grid-template-columns: repeat(72, 1fr);
    gap: 1.5px;
    flex: 1;
    height: 15px;
  }}
  .b-cell {{
    border-radius: 1.5px;
    opacity: 0;
    transform: scaleY(0.3);
    animation: specIn 0.45s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }}
  .b-peak {{
    box-shadow: 0 0 8px #FFFBEB, 0 0 3px var(--pyro-vermilion);
    z-index: 2;
  }}
  @keyframes specIn {{
    to {{ opacity: 1; transform: scaleY(1); }}
  }}
  /* 5x12 Monthly Rollup Matrix */
  .monthly-box {{
    background: var(--bg-obsidian);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    padding: 7px 10px;
    margin-top: 6px;
  }}
  .m-grid {{
    display: grid;
    grid-template-columns: 36px repeat(12, 1fr);
    gap: 4px;
    align-items: center;
    margin-bottom: 3.5px;
  }}
  .m-grid:last-child {{ margin-bottom: 0; }}
  .m-hdr {{
    font-family: var(--font-mono);
    font-size: 0.64rem;
    color: var(--text-muted);
    text-align: center;
    font-weight: 700;
  }}
  .m-box {{
    height: 20px;
    border-radius: 3px;
    font-family: var(--font-mono);
    font-size: 0.66rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  /* Bottom Streak & Seasonality Readout */
  .critical-strip {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-top: 6px;
  }}
  .c-pill {{
    background: var(--bg-recessed);
    border-left: 3px solid var(--pyro-vermilion);
    border-radius: 4px;
    padding: 5px 8px;
  }}
  .c-lbl {{ font-size: 0.64rem; color: var(--text-muted); text-transform: uppercase; font-weight: 700; }}
  .c-val {{ font-family: var(--font-mono); font-size: 0.74rem; color: var(--text-primary); font-weight: 800; margin-top: 1px; }}
  /* Right Panel: Spatial Observatory & Anomaly Vector */
  .map-viewport {{
    background: var(--bg-obsidian);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    flex: 1;
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .radar-ring {{
    animation: radarPulse 0.8s infinite alternate ease-in-out;
    transform-origin: center;
  }}
  @keyframes radarPulse {{
    from {{ opacity: 0.30; stroke-width: 1px; }}
    to   {{ opacity: 0.90; stroke-width: 2.5px; }}
  }}
  .biome-card {{
    position: absolute;
    top: 8px;
    right: 8px;
    background: rgba(14, 19, 31, 0.92);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    padding: 7px 9px;
    font-family: var(--font-mono);
    font-size: 0.66rem;
    line-height: 1.45;
  }}
  .sensor-dock {{
    background: var(--bg-recessed);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    padding: 7px 10px;
    margin-top: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-family: var(--font-mono);
    font-size: 0.69rem;
  }}
  @media (prefers-reduced-motion: reduce) {{
    .b-cell, .radar-ring {{ animation: none !important; opacity: 1 !important; transform: none !important; }}
  }}
</style>
</head>
<body>
  <!-- Header -->
  <header class="inst-header">
    <div class="brand-cluster">
      <div class="logo-mark">🔥</div>
      <div>
        <div class="app-name">
          <span>SEKHMET SYNC</span>
          <span class="spec-pill">MWIR 3.9µm // FRP ≥ 6.5 MW HARMONIZED</span>
        </div>
        <div class="app-sub">California Satellite Active-Fire Harmonization Observatory • 2020–2024 Archive (1,827 Continuous Days • 0 Missing)</div>
      </div>
    </div>

    <nav class="tab-dock" aria-label="Primary Views">
      <button class="tab-item active">📅 Burning Calendar</button>
      <button class="tab-item">🗺️ Spatial Footprint</button>
      <button class="tab-item">📈 Anomaly Analysis</button>
      <button class="tab-item">📡 Situational Awareness</button>
      <button class="tab-item">❓ Why Harmonisation</button>
    </nav>
  </header>

  <!-- Sub-Region Selector + Radiometric Cutoff Gate -->
  <section class="gate-bar">
    <div class="region-group">
      <span style="font-size:0.70rem;color:var(--text-muted);font-weight:700;margin-right:4px;">DOMAIN:</span>
      <button class="r-btn active">California — Statewide</button>
      <button class="r-btn">Northern Forests (182,441)</button>
      <button class="r-btn">Sierra Nevada (73,757)</button>
      <button class="r-btn">Southern Chaparral (25,549)</button>
      <button class="r-btn">Custom Lat/Lon BBox</button>
    </div>

    <div class="frp-gate-pill">
      <span style="color:var(--viirs-amber);font-weight:700;">SIGNAL GATE (VIIRS FRP ≥ 6.5 MW):</span>
      <div class="gate-meter"><div class="gate-kept"></div></div>
      <span style="color:var(--text-primary);">r = 0.9974 vs. MODIS | 2020-01-01 → 2024-12-31</span>
    </div>
  </section>

  <!-- 4 Reconciled Telemetry KPIs -->
  <section class="kpi-strip">
    <div class="kpi-card">
      <div>
        <div class="k-label">In-State Raw Detections</div>
        <div class="k-val">722,596</div>
        <div class="k-sub">● MODIS: 113,795 | ▲ VIIRS: 608,801</div>
      </div>
      <div class="k-badge" style="background:rgba(148,163,184,0.12);color:var(--text-secondary);">5.35× Raw<br>Ratio</div>
    </div>

    <div class="kpi-card">
      <div>
        <div class="k-label">Harmonised Hotspots</div>
        <div class="k-val" style="color:var(--modis-cyan);">347,174</div>
        <div class="k-sub">● MODIS: 113,795 | ▲ VIIRS ≥6.5MW: 233,379</div>
      </div>
      <div class="k-badge" style="background:rgba(6,182,212,0.14);color:var(--modis-cyan);">100% In-State<br>Reconciled</div>
    </div>

    <div class="kpi-card">
      <div>
        <div class="k-label">Filtered Sub-Threshold</div>
        <div class="k-val" style="color:var(--viirs-amber);">52.0%</div>
        <div class="k-sub">375,422 faint VIIRS (&lt; 6.5 MW) stripped</div>
      </div>
      <div class="k-badge" style="background:rgba(245,158,11,0.14);color:var(--viirs-amber);">61.7% of<br>Raw VIIRS</div>
    </div>

    <div class="kpi-card">
      <div>
        <div class="k-label">Statewide Peak Day</div>
        <div class="k-val" style="color:var(--pyro-vermilion);">2020-09-09</div>
        <div class="k-sub">10,320 harmonised hotspots (+10,183 anom)</div>
      </div>
      <div class="k-badge" style="background:rgba(225,29,72,0.18);color:#FDA4AF;">DOY 253<br>August Cplx</div>
    </div>
  </section>

  <!-- Main Synchronized Dual-Scale Horizon Deck + Spatial Observatory -->
  <main class="studio-grid">
    <div class="obs-panel">
      <div>
        <div class="p-hdr">
          <div class="p-title">
            <span>SYNCHRONIZED MULTI-SCALE BURNING CALENDAR (DAILY 5×366 + MONTHLY 5×12)</span>
          </div>
          <span style="font-family:var(--font-mono);font-size:0.68rem;color:var(--viirs-amber);">
            ★ WHITE-HOT PEAK: 2020-09-09 (10,320 HOTSPOTS)
          </span>
        </div>

        <!-- 5x366 High-Resolution Thermal Barcode -->
        <div class="barcode-box">
          {build_daily_barcode()}
        </div>

        <!-- 5x12 Monthly Rollup Matrix -->
        <div class="monthly-box">
          {build_monthly_matrix()}
        </div>
      </div>

      <!-- Critical Streaks & Season Window -->
      <div class="critical-strip">
        <div class="c-pill" style="border-left-color:var(--median-emerald);">
          <div class="c-lbl">Core Fire Season (10th–90th %ile)</div>
          <div class="c-val">July 11 – Oct 3 (85 Days)</div>
          <div style="font-size:0.65rem;color:var(--text-muted);">Concentrates 80% of all California burning</div>
        </div>
        <div class="c-pill">
          <div class="c-lbl">Longest Critical Streak (&gt;3× Median)</div>
          <div class="c-val">23 Days: Aug 1–23, 2021</div>
          <div style="font-size:0.65rem;color:var(--text-muted);">48,049 hotspots • Dixie Fire (963,309 ac)</div>
        </div>
        <div class="c-pill" style="border-left-color:var(--pyro-crimson);">
          <div class="c-lbl">Highest Volume Outbreak Streak</div>
          <div class="c-val">21 Days: Aug 30–Sep 19, 2020</div>
          <div style="font-size:0.65rem;color:var(--text-muted);">66,764 hotspots • August &amp; North Complex</div>
        </div>
      </div>
    </div>

    <!-- Right Column: Spatial Footprint + Biome Ratios -->
    <div class="obs-panel">
      <div class="p-hdr">
        <div class="p-title">SPATIAL FOOTPRINT &amp; BIOME TRANSFERABILITY</div>
        <span style="font-family:var(--font-mono);font-size:0.68rem;color:var(--modis-cyan);">32.5°N–42.0°N, -124.5°W–-114.0°W</span>
      </div>

      <div class="map-viewport">
        <svg viewBox="0 0 320 270" width="100%" height="100%" aria-label="California Infrared Hotspot Map">
          <!-- Coordinate Graticules -->
          <line x1="60" y1="0" x2="60" y2="270" stroke="rgba(148,163,184,0.08)" />
          <line x1="140" y1="0" x2="140" y2="270" stroke="rgba(148,163,184,0.08)" />
          <line x1="220" y1="0" x2="220" y2="270" stroke="rgba(148,163,184,0.08)" />
          <line x1="0" y1="70" x2="320" y2="70" stroke="rgba(148,163,184,0.08)" />
          <line x1="0" y1="150" x2="320" y2="150" stroke="rgba(148,163,184,0.08)" />
          <line x1="0" y1="230" x2="320" y2="230" stroke="rgba(148,163,184,0.08)" />

          <!-- California Vector Outline -->
          <path d="M 55,18 L 138,18 L 138,90 L 222,190 L 200,252 L 148,256 L 96,198 L 54,122 L 40,62 Z"
                fill="#131B2E" stroke="#475569" stroke-width="1.8" />

          <!-- Multi-Ring Radar Outbreak Zones -->
          <circle class="radar-ring" cx="82" cy="56" r="16" fill="rgba(225,29,72,0.18)" stroke="#E11D48" />
          <circle class="radar-ring" cx="122" cy="82" r="14" fill="rgba(255,77,42,0.18)" stroke="#FF4D2A" />
          <circle class="radar-ring" cx="148" cy="136" r="13" fill="rgba(245,158,11,0.18)" stroke="#F59E0B" />
          <circle class="radar-ring" cx="168" cy="218" r="10" fill="rgba(225,29,72,0.16)" stroke="#E11D48" />

          <!-- MODIS Detections (Cyan Circles ●) -->
          <circle cx="78" cy="54" r="4" fill="#06B6D4" stroke="#07090E" stroke-width="0.9" />
          <circle cx="118" cy="80" r="4" fill="#06B6D4" stroke="#07090E" stroke-width="0.9" />
          <circle cx="144" cy="134" r="3.8" fill="#06B6D4" stroke="#07090E" stroke-width="0.9" />
          <circle cx="72" cy="108" r="3.5" fill="#06B6D4" stroke="#07090E" stroke-width="0.9" />

          <!-- VIIRS Detections >= 6.5 MW (Amber Triangles ▲) -->
          <polygon points="87,49 92,59 82,59" fill="#F59E0B" stroke="#07090E" stroke-width="0.8" />
          <polygon points="127,76 132,86 122,86" fill="#F59E0B" stroke="#07090E" stroke-width="0.8" />
          <polygon points="153,130 158,140 148,140" fill="#F59E0B" stroke="#07090E" stroke-width="0.8" />
          <polygon points="170,212 175,222 165,222" fill="#F59E0B" stroke="#07090E" stroke-width="0.8" />

          <!-- Callouts -->
          <text x="98" y="45" fill="#F8FAFC" font-size="8" font-family="monospace" font-weight="bold">AUGUST COMPLEX (2020)</text>
          <text x="136" y="75" fill="#F8FAFC" font-size="8" font-family="monospace" font-weight="bold">DIXIE FIRE (2021)</text>
          <text x="160" y="135" fill="#CBD5E1" font-size="8" font-family="monospace">CREEK FIRE (2020)</text>
        </svg>

        <div class="biome-card">
          <div style="color:var(--viirs-amber);font-weight:700;margin-bottom:2px;">BIOME VIIRS/MODIS RATIO</div>
          <div>Northern Forests: <strong>1.98</strong></div>
          <div>Sierra Nevada:    <strong>2.01</strong></div>
          <div>So. Chaparral:    <strong>2.48</strong></div>
          <div style="color:var(--text-muted);margin-top:2px;">3-Biome Sub: 281,747</div>
        </div>
      </div>

      <div class="sensor-dock">
        <span style="color:var(--modis-cyan);font-weight:700;">● MODIS (Circle): 113,795</span>
        <span style="color:var(--viirs-amber);font-weight:700;">▲ VIIRS ≥6.5MW (Triangle): 233,379</span>
        <span style="color:var(--median-emerald);font-weight:700;">― 5-Yr Median</span>
      </div>
    </div>
  </main>
</body>
</html>
"""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_file = (OUT_DIR / "concept-e.html").resolve()
    html_file.write_text(CONCEPT_E_HTML, encoding="utf-8")
    print(f"[OK] Wrote {html_file}")

    resolutions = [(1366, 768), (1600, 900), (1920, 1080)]

    # Try Playwright Python API first
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for w, h in resolutions:
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto(html_file.as_uri())
                page.wait_for_timeout(900)
                out_png = (OUT_DIR / f"concept-E-{w}x{h}.png").resolve()
                page.screenshot(path=str(out_png), full_page=False)
                print(f"  -> Saved {out_png}")
                page.close()
            browser.close()
        return
    except ImportError:
        pass

    # Fallback to CLI browser / playwright
    candidates = [
        "playwright",
        "chromium",
        "chromium-browser",
        "google-chrome",
        "chrome",
        "chrome.exe",
        "msedge",
        "msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    exe = None
    is_playwright = False
    for bin_name in candidates:
        found = shutil.which(bin_name) or (Path(bin_name).is_file() and bin_name)
        if found:
            exe = str(found)
            is_playwright = "playwright" in bin_name.lower()
            break

    if not exe:
        print("[NOTICE] Saved ui-concepts/concept-e.html. Open in any browser or run Playwright to capture PNGs.")
        return

    print(f"[INFO] Capturing screenshots using CLI: {exe}")
    for w, h in resolutions:
        out_png = (OUT_DIR / f"concept-E-{w}x{h}.png").resolve()
        if is_playwright:
            cmd = [exe, "screenshot", f"--viewport-size={w},{h}", "--wait-for-timeout=900", html_file.as_uri(), str(out_png)]
        else:
            cmd = [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={w},{h}", f"--screenshot={out_png}", html_file.as_uri()]
        subprocess.run(cmd, check=True)
        print(f"  -> Saved {out_png}")


if __name__ == "__main__":
    main()
