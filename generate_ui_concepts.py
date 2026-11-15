#!/usr/bin/env python3
"""
generate_ui_concepts.py — Sekhmet Sync UI/UX Concept Generator & Screenshotter
Generates 4 self-contained static HTML mockups in ui-concepts/ and captures
1366x768 and 1920x1080 PNG screenshots via Playwright or headless Chromium.

Strict compliance:
- Exact California 2020-2024 numbers (347,174 harmonised, 722,596 raw, 375,422 / 52.0% filtered,
  Peak Day 2020-09-09 with 10,320 hotspots, 1,827 days, Season Jul 11 - Oct 3 / 85 days / 80%,
  Streaks: 23-day Aug 1-23, 2021 Dixie / 21-day Aug 30-Sep 19, 2020 August Complex).
- Exact Sekhmet WCAG AA palette: Papyrus #E8DCC4, Warm Sand #D8C3A5, Basalt #1C1B1A,
  Crimson #A82E2E, Dark Crimson #8B1E1E, Solar Gold #D4AF37, Ocher #C68B25,
  Lapis #1B365D, Malachite #2E6F40, Rich Bronze Ocher #5E4605 (gold text on light bg).
- No NASA logos. Does NOT touch app.py or any data files.
"""

import shutil
import subprocess
from pathlib import Path

OUT_DIR = Path("ui-concepts")

# ---------------------------------------------------------------------------
# Shared Data Constants & SVG Helpers
# ---------------------------------------------------------------------------

MONTHLY_DATA = [
    # yr,  Jan, Feb, Mar, Apr,  May,   Jun,    Jul,    Aug,    Sep,    Oct,   Nov,  Dec
    (2020, "180", "310", "240", "290", "820", "2.4k", "6.1k", "41.8k", "79.4k", "7.1k", "1.1k", "322"),
    (2021, "290", "195", "310", "540", "1.1k", "3.8k", "18.9k", "66.7k", "24.2k", "2.9k", "680", "298"),
    (2022, "210", "340", "410", "380", "690", "1.5k", "3.9k", "3.4k", "4.1k", "610", "190", "117"),
    (2023, "140", "190", "230", "390", "780", "1.4k", "4.2k", "9.8k", "5.4k", "3.1k", "980", "396"),
    (2024, "175", "220", "310", "460", "1.2k", "4.9k", "19.7k", "8.6k", "6.2k", "1.8k", "490", "251"),
]

MONTHLY_COLORS = [
    # 2020
    ["#E8DCC4", "#E8DCC4", "#E8DCC4", "#E8DCC4", "#D8C3A5", "#D8C3A5", "#C68B25", "#A82E2E", "#8B1E1E", "#C68B25", "#D8C3A5", "#E8DCC4"],
    # 2021
    ["#E8DCC4", "#E8DCC4", "#E8DCC4", "#E8DCC4", "#D8C3A5", "#C68B25", "#A82E2E", "#8B1E1E", "#A82E2E", "#D8C3A5", "#E8DCC4", "#E8DCC4"],
    # 2022
    ["#E8DCC4", "#E8DCC4", "#E8DCC4", "#E8DCC4", "#E8DCC4", "#D8C3A5", "#C68B25", "#C68B25", "#C68B25", "#E8DCC4", "#E8DCC4", "#E8DCC4"],
    # 2023
    ["#E8DCC4", "#E8DCC4", "#E8DCC4", "#E8DCC4", "#D8C3A5", "#D8C3A5", "#C68B25", "#A82E2E", "#C68B25", "#D8C3A5", "#D8C3A5", "#E8DCC4"],
    # 2024
    ["#E8DCC4", "#E8DCC4", "#E8DCC4", "#E8DCC4", "#D8C3A5", "#C68B25", "#A82E2E", "#C68B25", "#C68B25", "#D8C3A5", "#E8DCC4", "#E8DCC4"],
]


def build_daily_strip_cells():
    """Generate 60 representative DOY columns x 5 years with staggered animation delays."""
    years = [2020, 2021, 2022, 2023, 2024]
    rows_html = []
    for r_idx, yr in enumerate(years):
        cells = []
        for c_idx in range(60):
            delay = (c_idx * 0.008) + (r_idx * 0.03)
            # Peak window around Sep (cols 38..46)
            color = "#E8DCC4"
            is_peak = False
            if yr == 2020 and c_idx == 41:
                color = "#8B1E1E"
                is_peak = True
            elif yr == 2020 and 36 <= c_idx <= 47:
                color = "#A82E2E" if c_idx % 2 == 0 else "#8B1E1E"
            elif yr == 2021 and 32 <= c_idx <= 43:
                color = "#A82E2E" if c_idx != 36 else "#8B1E1E"
            elif yr == 2024 and 28 <= c_idx <= 35:
                color = "#A82E2E"
            elif 25 <= c_idx <= 48:
                if (yr + c_idx) % 5 == 0:
                    color = "#C68B25"
                elif (yr + c_idx) % 3 == 0:
                    color = "#D8C3A5"
            elif (yr + c_idx) % 11 == 0:
                color = "#D8C3A5"

            peak_cls = " peak-cell" if is_peak else ""
            title = "2020-09-09: 10,320 harmonised hotspots (Statewide Peak)" if is_peak else f"{yr} DOY slice"
            cells.append(
                f'<div class="d-cell{peak_cls}" style="background:{color};animation-delay:{delay:.2f}s" title="{title}"></div>'
            )
        rows_html.append(
            f'<div class="d-row"><span class="yr-lbl">{yr}</span><div class="d-cells">{"".join(cells)}</div></div>'
        )
    return "\n".join(rows_html)


def build_monthly_grid_html():
    rows = []
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    header = '<div class="m-row m-head"><span class="yr-lbl">Year</span>' + "".join(
        f'<span class="m-hdr">{m}</span>' for m in months
    ) + "</div>"
    rows.append(header)
    for r_idx, tup in enumerate(MONTHLY_DATA):
        yr = tup[0]
        vals = tup[1:]
        cols = []
        for c_idx, val in enumerate(vals):
            bg = MONTHLY_COLORS[r_idx][c_idx]
            fg = "#FFFFFF" if bg in ("#A82E2E", "#8B1E1E") else "#1C1B1A"
            cols.append(
                f'<div class="m-cell" style="background:{bg};color:{fg};animation-delay:{(r_idx*0.04+c_idx*0.02):.2f}s">{val}</div>'
            )
        rows.append(f'<div class="m-row"><span class="yr-lbl">{yr}</span>{"".join(cols)}</div>')
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Concept A — "Sekhmet / Cinematic Papyrus"
# ---------------------------------------------------------------------------

CONCEPT_A_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sekhmet Sync — Concept A: Sekhmet / Cinematic Papyrus</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background-color: #E8DCC4;
    color: #1C1B1A;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Georgia, serif;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }}
  /* Keyboard focus accessibility */
  *:focus-visible {{
    outline: 2px solid #1B365D;
    outline-offset: 2px;
  }}
  /* Dark Basalt Hero Header with Rising Ember Particles */
  .hero-header {{
    position: relative;
    background-color: #1C1B1A;
    color: #E8DCC4;
    padding: 12px 24px;
    border-bottom: 2px solid #D4AF37;
    display: flex;
    justify-content: space-between;
    align-items: center;
    overflow: hidden;
    flex-shrink: 0;
  }}
  .embers {{
    position: absolute;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
  }}
  .ember {{
    position: absolute;
    bottom: -10px;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: radial-gradient(circle, #D4AF37 0%, #A82E2E 80%, transparent 100%);
    opacity: 0.28;
    animation: rise 4.5s infinite ease-in;
  }}
  .ember:nth-child(1) {{ left: 12%; animation-delay: 0.1s; animation-duration: 4.0s; }}
  .ember:nth-child(2) {{ left: 26%; animation-delay: 0.8s; animation-duration: 5.1s; width: 4px; height: 4px; }}
  .ember:nth-child(3) {{ left: 44%; animation-delay: 0.3s; animation-duration: 4.4s; }}
  .ember:nth-child(4) {{ left: 61%; animation-delay: 1.2s; animation-duration: 4.8s; width: 6px; height: 6px; }}
  .ember:nth-child(5) {{ left: 77%; animation-delay: 0.5s; animation-duration: 3.9s; }}
  .ember:nth-child(6) {{ left: 90%; animation-delay: 1.5s; animation-duration: 4.6s; }}
  @keyframes rise {{
    0%   {{ transform: translateY(0) scale(0.8); opacity: 0.0; }}
    30%  {{ opacity: 0.32; }}
    100% {{ transform: translateY(-68px) scale(1.25); opacity: 0.0; }}
  }}
  .brand-title {{
    font-size: 1.35rem;
    font-weight: 800;
    color: #D4AF37;
    letter-spacing: 0.03em;
    display: flex;
    align-items: center;
    gap: 10px;
    position: relative;
    z-index: 2;
  }}
  .badge-challenge {{
    background: rgba(212, 175, 55, 0.15);
    color: #E8DCC4;
    border: 1px solid #D4AF37;
    font-size: 0.72rem;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-family: sans-serif;
  }}
  .brand-sub {{
    font-size: 0.80rem;
    color: #D8C3A5;
    margin-top: 2px;
    font-family: sans-serif;
    position: relative;
    z-index: 2;
  }}
  .header-right {{
    display: flex;
    align-items: center;
    gap: 12px;
    position: relative;
    z-index: 2;
    font-family: sans-serif;
  }}
  .notice-pill {{
    background: #D8C3A5;
    color: #1C1B1A;
    border-left: 4px solid #5E4605;
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 0.74rem;
    font-weight: 600;
  }}
  /* Main Workspace */
  .workspace {{
    display: grid;
    grid-template-columns: 245px 1fr;
    flex: 1;
    min-height: 0;
  }}
  /* Sidebar */
  .sidebar {{
    background: #D8C3A5;
    border-right: 1px solid #5E4605;
    padding: 14px 16px;
    font-family: sans-serif;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .side-heading {{
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #5E4605;
    font-weight: 800;
    border-bottom: 1px solid rgba(28, 27, 26, 0.2);
    padding-bottom: 4px;
  }}
  .reg-list {{
    display: flex;
    flex-direction: column;
    gap: 5px;
  }}
  .reg-btn {{
    background: #E8DCC4;
    color: #1C1B1A;
    border: 1px solid rgba(28, 27, 26, 0.25);
    border-radius: 5px;
    padding: 6px 9px;
    font-size: 0.76rem;
    font-weight: 600;
    text-align: left;
    cursor: pointer;
    transition: all 180ms ease;
  }}
  .reg-btn:hover {{
    border-color: #5E4605;
    transform: translateX(2px);
  }}
  .reg-btn.active {{
    background: #1C1B1A;
    color: #D4AF37;
    border-color: #1C1B1A;
    font-weight: 700;
  }}
  .date-box {{
    background: #E8DCC4;
    border: 1px solid rgba(28, 27, 26, 0.25);
    border-radius: 5px;
    padding: 7px 9px;
    font-size: 0.76rem;
  }}
  .sensor-legend {{
    background: #E8DCC4;
    border: 1px solid rgba(28, 27, 26, 0.25);
    border-radius: 5px;
    padding: 8px 10px;
    font-size: 0.74rem;
    line-height: 1.45;
  }}
  .tag-modis {{ color: #1B365D; font-weight: 800; }}
  .tag-viirs {{ color: #5E4605; font-weight: 800; }}
  /* Content Area */
  .content {{
    padding: 14px 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
    font-family: sans-serif;
  }}
  /* KPI Cards */
  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }}
  .kpi-card {{
    background: #D8C3A5;
    border: 1px solid rgba(94, 70, 5, 0.45);
    border-top: 3px solid #5E4605;
    border-radius: 6px;
    padding: 10px 14px;
    transition: transform 200ms ease, border-color 200ms ease;
  }}
  .kpi-card:hover {{
    transform: translateY(-2px);
    border-color: #1C1B1A;
  }}
  .kpi-lbl {{
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #5E4605;
    font-weight: 800;
  }}
  .kpi-val {{
    font-size: 1.45rem;
    font-weight: 800;
    color: #1C1B1A;
    margin-top: 2px;
  }}
  .kpi-sub {{
    font-size: 0.72rem;
    color: #1C1B1A;
    margin-top: 2px;
    font-weight: 600;
  }}
  /* Tabs with sliding gold underline */
  .tabs-bar {{
    display: flex;
    gap: 6px;
    border-bottom: 2px solid #D8C3A5;
    position: relative;
  }}
  .tab-btn {{
    background: transparent;
    border: none;
    color: #1C1B1A;
    padding: 7px 14px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    position: relative;
    transition: color 200ms ease;
  }}
  .tab-btn:hover {{
    color: #A82E2E;
  }}
  .tab-btn.active {{
    color: #8B1E1E;
    font-weight: 800;
  }}
  .tab-btn.active::after {{
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    bottom: -2px;
    height: 3px;
    background: #5E4605;
    transition: transform 250ms cubic-bezier(0.22, 1, 0.36, 1);
  }}
  /* Main Split Grid: Hero Calendar + Pulsing Footprint Map */
  .main-grid {{
    display: grid;
    grid-template-columns: 1.65fr 1fr;
    gap: 14px;
    flex: 1;
    min-height: 0;
  }}
  .panel {{
    background: #D8C3A5;
    border: 1px solid rgba(28, 27, 26, 0.22);
    border-radius: 8px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 0;
  }}
  .panel-hdr {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }}
  .panel-title {{
    font-size: 0.88rem;
    font-weight: 800;
    color: #1C1B1A;
  }}
  .panel-badge {{
    font-size: 0.72rem;
    background: #E8DCC4;
    color: #5E4605;
    border: 1px solid #5E4605;
    padding: 2px 7px;
    border-radius: 4px;
    font-weight: 700;
  }}
  /* Staggered 5x366 Heatmap Matrix */
  .matrix-wrap {{
    background: #E8DCC4;
    border: 1px solid rgba(28, 27, 26, 0.2);
    border-radius: 6px;
    padding: 10px 10px 6px 10px;
    position: relative;
  }}
  .d-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 5px;
  }}
  .yr-lbl {{
    font-size: 0.76rem;
    font-weight: 800;
    width: 34px;
    color: #1C1B1A;
  }}
  .d-cells {{
    display: grid;
    grid-template-columns: repeat(60, 1fr);
    gap: 2px;
    flex: 1;
    height: 22px;
  }}
  .d-cell {{
    border-radius: 2px;
    opacity: 0;
    transform: scaleY(0.4);
    animation: cellIn 0.45s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }}
  .d-cell:hover {{
    outline: 1.5px solid #1C1B1A;
    z-index: 3;
  }}
  .peak-cell {{
    outline: 2px solid #1C1B1A;
    box-shadow: 0 0 0 2px #D4AF37;
  }}
  @keyframes cellIn {{
    to {{ opacity: 1; transform: scaleY(1); }}
  }}
  .m-axis {{
    display: flex;
    justify-content: space-between;
    padding-left: 42px;
    font-size: 0.68rem;
    color: #1C1B1A;
    font-weight: 700;
    margin-top: 4px;
  }}
  .peak-callout {{
    margin-top: 8px;
    background: #E8DCC4;
    border-left: 3px solid #8B1E1E;
    padding: 6px 10px;
    font-size: 0.74rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  /* Streak & Season Strip */
  .season-strip {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-top: 8px;
  }}
  .s-box {{
    background: #E8DCC4;
    border: 1px solid rgba(28, 27, 26, 0.18);
    border-radius: 5px;
    padding: 6px 8px;
  }}
  .s-lbl {{ font-size: 0.67rem; color: #5E4605; font-weight: 800; text-transform: uppercase; }}
  .s-val {{ font-size: 0.80rem; color: #1C1B1A; font-weight: 800; margin-top: 2px; }}
  /* Map Canvas with Pulsing Fire Dots */
  .map-stage {{
    background: #E8DCC4;
    border: 1px solid rgba(28, 27, 26, 0.22);
    border-radius: 6px;
    flex: 1;
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .pulse-ring {{
    animation: firePulse 0.75s infinite alternate ease-in-out;
    transform-origin: center;
  }}
  @keyframes firePulse {{
    0%   {{ opacity: 0.35; r: 7px; }}
    100% {{ opacity: 0.85; r: 12px; }}
  }}
  .map-legend {{
    position: absolute;
    bottom: 8px;
    left: 8px;
    right: 8px;
    background: rgba(232, 220, 196, 0.94);
    border: 1px solid #1C1B1A;
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 0.70rem;
    display: flex;
    justify-content: space-between;
    font-weight: 700;
  }}
  @media (prefers-reduced-motion: reduce) {{
    .ember, .d-cell, .pulse-ring {{ animation: none !important; opacity: 1 !important; transform: none !important; }}
  }}
</style>
</head>
<body>
  <header class="hero-header">
    <div class="embers">
      <div class="ember"></div><div class="ember"></div><div class="ember"></div>
      <div class="ember"></div><div class="ember"></div><div class="ember"></div>
    </div>
    <div>
      <div class="brand-title">
        <span>🔥 SEKHMET SYNC</span>
        <span class="badge-challenge">Space Apps 2026</span>
      </div>
      <div class="brand-sub">Harmonized Satellite Hotspot Activity Calendar • California Archive (2020–2024 • 1,827 Continuous Days)</div>
    </div>
    <div class="header-right">
      <div class="notice-pill">⚠️ Experimental VIIRS FRP ≥ 6.5 MW Threshold (r = 0.9974 vs. Pre-Drift MODIS)</div>
    </div>
  </header>

  <div class="workspace">
    <aside class="sidebar">
      <div class="side-heading">Region & Ecosection</div>
      <div class="reg-list">
        <button class="reg-btn active">California — Statewide</button>
        <button class="reg-btn">Northern Forests (Klamath)</button>
        <button class="reg-btn">Sierra Nevada / Central</button>
        <button class="reg-btn">Southern Chaparral</button>
        <button class="reg-btn">Custom Lat / Lon BBox</button>
      </div>

      <div class="side-heading">Archive Date Window</div>
      <div class="date-box">
        <div><strong>Start:</strong> 2020-01-01</div>
        <div style="margin-top:3px;"><strong>End:</strong> 2024-12-31 (1,827 days)</div>
      </div>

      <div class="side-heading">Sensor Encoding (Shape + Color)</div>
      <div class="sensor-legend">
        <div><span class="tag-modis">● MODIS C6.1 (Circle):</span><br>113,795 in-state detections (conf ≥ 30)</div>
        <div style="margin-top:6px;"><span class="tag-viirs">▲ VIIRS N20/N21 (Triangle):</span><br>233,379 harmonised (FRP ≥ 6.5 MW)<br>608,801 raw in-state</div>
      </div>
    </aside>

    <main class="content">
      <section class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-lbl">In-State Raw Hotspots</div>
          <div class="kpi-val">722,596</div>
          <div class="kpi-sub">MODIS: 113,795 • VIIRS: 608,801</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-lbl">Harmonised Hotspots</div>
          <div class="kpi-val">347,174</div>
          <div class="kpi-sub">MODIS + VIIRS (FRP ≥ 6.5 MW)</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-lbl">Filtered Sub-Threshold</div>
          <div class="kpi-val">52.0%</div>
          <div class="kpi-sub">375,422 faint VIIRS (&lt; 6.5 MW)</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-lbl">Statewide Peak Day</div>
          <div class="kpi-val">2020-09-09</div>
          <div class="kpi-sub">10,320 harmonised hotspots</div>
        </div>
      </section>

      <nav class="tabs-bar" aria-label="Primary Views">
        <button class="tab-btn active">📅 Burning Calendar</button>
        <button class="tab-btn">🗺️ Spatial Footprint</button>
        <button class="tab-btn">📈 Anomaly Analysis</button>
        <button class="tab-btn">📡 Situational Awareness</button>
        <button class="tab-btn">❓ Why Harmonisation</button>
      </nav>

      <section class="main-grid">
        <div class="panel">
          <div>
            <div class="panel-hdr">
              <span class="panel-title">Burning Activity Calendar (5×366 Daily Matrix) — California Statewide</span>
              <span class="panel-badge">Staggered Entrance • 0 Missing Dates</span>
            </div>
            <div class="matrix-wrap">
              {build_daily_strip_cells()}
              <div class="m-axis">
                <span>Jan</span><span>Feb</span><span>Mar</span><span>Apr</span><span>May</span><span>Jun</span>
                <span>Jul</span><span>Aug</span><span>Sep</span><span>Oct</span><span>Nov</span><span>Dec</span>
              </div>
            </div>
            <div class="peak-callout">
              <span><strong>★ Peak Ignition Burst:</strong> 2020-09-09 (10,320 hotspots — August Complex &amp; Creek Fire)</span>
              <span style="color:#5E4605;font-weight:800;">5-Yr Median Baseline: #2E6F40</span>
            </div>
          </div>

          <div class="season-strip">
            <div class="s-box">
              <div class="s-lbl">Core Fire Season Window</div>
              <div class="s-val">July 11 – Oct 3 (85 days)</div>
              <div style="font-size:0.68rem;">Contains 80% of cumulative activity</div>
            </div>
            <div class="s-box">
              <div class="s-lbl">2021 Dixie Outbreak Streak</div>
              <div class="s-val">23 Days (Aug 1–23, 2021)</div>
              <div style="font-size:0.68rem;">48,049 harmonised hotspots (&gt;3× med)</div>
            </div>
            <div class="s-box">
              <div class="s-lbl">2020 Aug Complex Streak</div>
              <div class="s-val">21 Days (Aug 30–Sep 19)</div>
              <div style="font-size:0.68rem;">66,764 harmonised hotspots (&gt;3× med)</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-hdr">
            <span class="panel-title">Spatial Hotspot Footprint (Pulsing Active Zones)</span>
            <span class="panel-badge">347,174 Detections</span>
          </div>
          <div class="map-stage">
            <svg viewBox="0 0 260 280" width="100%" height="100%" aria-label="California Fire Map">
              <!-- Stylized California Polygon -->
              <path d="M 55,20 L 135,20 L 135,95 L 215,195 L 195,255 L 145,260 L 95,205 L 55,125 L 40,65 Z"
                    fill="#D8C3A5" stroke="#1C1B1A" stroke-width="2" />
              <!-- Pulsing Crimson Halo Zones -->
              <circle class="pulse-ring" cx="85" cy="58" r="9" fill="#A82E2E" />
              <circle class="pulse-ring" cx="122" cy="84" r="10" fill="#8B1E1E" />
              <circle class="pulse-ring" cx="148" cy="138" r="9" fill="#A82E2E" />
              <circle class="pulse-ring" cx="165" cy="218" r="7" fill="#A82E2E" />
              <!-- MODIS Circles (Lapis #1B365D) -->
              <circle cx="82" cy="55" r="3.8" fill="#1B365D" stroke="#E8DCC4" stroke-width="0.8" />
              <circle cx="118" cy="82" r="4.2" fill="#1B365D" stroke="#E8DCC4" stroke-width="0.8" />
              <circle cx="144" cy="135" r="3.8" fill="#1B365D" stroke="#E8DCC4" stroke-width="0.8" />
              <circle cx="72" cy="110" r="3.5" fill="#1B365D" stroke="#E8DCC4" stroke-width="0.8" />
              <!-- VIIRS Triangles (Ocher #C68B25 / Crimson #A82E2E) -->
              <polygon points="90,52 95,61 85,61" fill="#C68B25" stroke="#1C1B1A" stroke-width="0.7" />
              <polygon points="127,78 132,87 122,87" fill="#C68B25" stroke="#1C1B1A" stroke-width="0.7" />
              <polygon points="152,132 157,141 147,141" fill="#C68B25" stroke="#1C1B1A" stroke-width="0.7" />
              <polygon points="168,213 173,222 163,222" fill="#C68B25" stroke="#1C1B1A" stroke-width="0.7" />
              <!-- Labels -->
              <text x="96" y="48" font-size="8" font-weight="bold" fill="#1C1B1A">August Complex (2020)</text>
              <text x="132" y="76" font-size="8" font-weight="bold" fill="#1C1B1A">Dixie Fire (2021)</text>
              <text x="155" y="132" font-size="8" font-weight="bold" fill="#1C1B1A">Creek Fire (2020)</text>
            </svg>
            <div class="map-legend">
              <span style="color:#1B365D;">● MODIS (113,795)</span>
              <span style="color:#5E4605;">▲ VIIRS ≥ 6.5 MW (233,379)</span>
              <span style="color:#8B1E1E;">◉ Peak Outbreak Core</span>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Concept B — "Mission Control / Live Telemetry"
# ---------------------------------------------------------------------------

CONCEPT_B_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sekhmet Sync — Concept B: Mission Control / Live Telemetry</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background-color: #1C1B1A;
    background-image:
      radial-gradient(circle at 15% 15%, rgba(212, 175, 55, 0.08), transparent 35%),
      radial-gradient(circle at 85% 80%, rgba(168, 46, 46, 0.10), transparent 40%);
    color: #E8DCC4;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    padding: 12px 18px;
    gap: 10px;
  }
  *:focus-visible {
    outline: 2px solid #D4AF37;
    outline-offset: 2px;
  }
  .glass {
    background: rgba(232, 220, 196, 0.06);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(212, 175, 55, 0.38);
    border-radius: 8px;
  }
  /* Top Telemetry Bar */
  .topbar {
    padding: 10px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .title-group {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .sys-title {
    font-size: 1.25rem;
    font-weight: 800;
    color: #D4AF37;
    letter-spacing: 0.05em;
  }
  .telemetry-tag {
    background: rgba(46, 111, 64, 0.25);
    border: 1px solid #2E6F40;
    color: #E8DCC4;
    font-size: 0.72rem;
    padding: 3px 8px;
    border-radius: 4px;
    font-family: monospace;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #D4AF37;
    box-shadow: 0 0 8px #D4AF37;
    animation: blink 0.75s infinite alternate;
  }
  @keyframes blink {
    from { opacity: 0.35; transform: scale(0.85); }
    to   { opacity: 1.0; transform: scale(1.15); }
  }
  .region-pills {
    display: flex;
    gap: 6px;
  }
  .r-pill {
    background: rgba(232, 220, 196, 0.08);
    color: #D8C3A5;
    border: 1px solid rgba(212, 175, 55, 0.3);
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 0.73rem;
    cursor: pointer;
    transition: all 180ms ease;
  }
  .r-pill:hover, .r-pill.active {
    background: rgba(212, 175, 55, 0.22);
    color: #E8DCC4;
    border-color: #D4AF37;
    font-weight: 700;
  }
  /* Tabs + KPI Strip */
  .nav-strip {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 14px;
  }
  .tabs {
    display: flex;
    gap: 8px;
  }
  .t-item {
    background: transparent;
    border: 1px solid transparent;
    color: #D8C3A5;
    padding: 5px 12px;
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 180ms ease;
  }
  .t-item:hover {
    border-color: rgba(212, 175, 55, 0.4);
    color: #E8DCC4;
  }
  .t-item.active {
    background: rgba(168, 46, 46, 0.35);
    border-color: #D4AF37;
    color: #D4AF37;
    font-weight: 700;
  }
  .window-readout {
    font-family: monospace;
    font-size: 0.75rem;
    color: #D8C3A5;
  }
  /* 4 Live-Counting KPI Cards */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
  }
  .kpi-box {
    padding: 10px 14px;
    position: relative;
    transition: border-color 200ms ease;
  }
  .kpi-box:hover {
    border-color: #D4AF37;
  }
  .k-title {
    font-size: 0.70rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #D8C3A5;
  }
  .k-num {
    font-size: 1.5rem;
    font-weight: 800;
    color: #D4AF37;
    font-family: monospace;
    margin-top: 3px;
  }
  .k-meta {
    font-size: 0.72rem;
    color: #E8DCC4;
    margin-top: 2px;
  }
  /* Main Telemetry Deck */
  .deck {
    display: grid;
    grid-template-columns: 1.55fr 1fr;
    gap: 12px;
    flex: 1;
    min-height: 0;
  }
  .deck-panel {
    padding: 12px 15px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 0;
  }
  .p-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(212, 175, 55, 0.25);
    padding-bottom: 6px;
    margin-bottom: 8px;
  }
  .p-title {
    font-size: 0.86rem;
    font-weight: 700;
    color: #D4AF37;
    letter-spacing: 0.03em;
  }
  /* Animated SVG Anomaly Chart */
  .chart-box {
    background: rgba(28, 27, 26, 0.65);
    border: 1px solid rgba(212, 175, 55, 0.25);
    border-radius: 6px;
    padding: 10px;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  .anomaly-line {
    stroke-dasharray: 900;
    stroke-dashoffset: 900;
    animation: drawLine 0.75s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }
  @keyframes drawLine {
    to { stroke-dashoffset: 0; }
  }
  .streak-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.73rem;
    margin-top: 8px;
    font-family: monospace;
  }
  .streak-table th {
    text-align: left;
    color: #D4AF37;
    border-bottom: 1px solid rgba(212, 175, 55, 0.3);
    padding: 4px 6px;
  }
  .streak-table td {
    padding: 5px 6px;
    color: #E8DCC4;
    border-bottom: 1px solid rgba(232, 220, 196, 0.1);
  }
  /* Situational Awareness Live Feed Panel */
  .feed-banner {
    background: rgba(168, 46, 46, 0.22);
    border-left: 3px solid #D4AF37;
    padding: 8px 10px;
    border-radius: 4px;
    font-size: 0.72rem;
    line-height: 1.4;
    color: #E8DCC4;
  }
  .feed-stats {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    margin: 8px 0;
  }
  .f-stat {
    background: rgba(28, 27, 26, 0.7);
    border: 1px solid rgba(212, 175, 55, 0.28);
    border-radius: 5px;
    padding: 8px 10px;
  }
  .f-lbl { font-size: 0.68rem; color: #D8C3A5; text-transform: uppercase; }
  .f-val { font-size: 0.92rem; color: #D4AF37; font-weight: 800; font-family: monospace; margin-top: 2px; }
  @media (prefers-reduced-motion: reduce) {
    .live-dot, .anomaly-line { animation: none !important; stroke-dashoffset: 0 !important; }
  }
</style>
</head>
<body>
  <header class="topbar glass">
    <div class="title-group">
      <span class="sys-title">🔥 SEKHMET SYNC // MISSION TELEMETRY</span>
      <span class="telemetry-tag"><span class="live-dot"></span>ARCHIVE VERIFIED: 1,827 DAYS (0 MISSING)</span>
    </div>
    <div class="region-pills">
      <button class="r-pill active">CA Statewide</button>
      <button class="r-pill">Northern Forests</button>
      <button class="r-pill">Sierra Nevada</button>
      <button class="r-pill">Southern Chaparral</button>
      <button class="r-pill">Custom BBox</button>
    </div>
  </header>

  <nav class="nav-strip glass">
    <div class="tabs">
      <button class="t-item">📅 Burning Calendar</button>
      <button class="t-item">🗺️ Spatial Footprint</button>
      <button class="t-item active">📈 Anomaly Analysis</button>
      <button class="t-item">📡 Situational Awareness</button>
      <button class="t-item">❓ Why Harmonisation</button>
    </div>
    <div class="window-readout">
      DOMAIN: [32.5°N–42.0°N, -124.5°W–-114.0°W] • THRESHOLD: VIIRS FRP ≥ 6.5 MW
    </div>
  </nav>

  <section class="kpi-grid">
    <div class="kpi-box glass">
      <div class="k-title">In-State Raw Detections</div>
      <div class="k-num" data-target="722596">722,596</div>
      <div class="k-meta">● MODIS: 113,795 | ▲ VIIRS: 608,801</div>
    </div>
    <div class="kpi-box glass">
      <div class="k-title">Harmonised Hotspots</div>
      <div class="k-num" data-target="347174">347,174</div>
      <div class="k-meta">● MODIS: 113,795 | ▲ VIIRS ≥6.5MW: 233,379</div>
    </div>
    <div class="kpi-box glass">
      <div class="k-title">Sub-Threshold Filtered</div>
      <div class="k-num" data-target="375422">375,422 (52.0%)</div>
      <div class="k-meta">61.7% of raw VIIRS (&lt; 6.5 MW) removed</div>
    </div>
    <div class="kpi-box glass">
      <div class="k-title">Peak Anomaly Event</div>
      <div class="k-num" data-target="10320">10,320 (2020-09-09)</div>
      <div class="k-meta">+10,183 above 5-Yr DOY median</div>
    </div>
  </section>

  <main class="deck">
    <div class="deck-panel glass">
      <div class="p-head">
        <span class="p-title">DAILY HARMONISED HOTSPOTS VS. 5-YEAR MEDIAN (2020–2024)</span>
        <span style="font-size:0.72rem;color:#D8C3A5;font-family:monospace;">CORE SEASON: JUL 11 – OCT 3 (85 DAYS • 80% OF BURNING)</span>
      </div>
      <div class="chart-box">
        <svg viewBox="0 0 680 185" width="100%" height="185" aria-label="Anomaly Telemetry Line Chart">
          <!-- Grid lines -->
          <line x1="40" y1="25" x2="660" y2="25" stroke="rgba(232,220,196,0.12)" />
          <line x1="40" y1="75" x2="660" y2="75" stroke="rgba(232,220,196,0.12)" />
          <line x1="40" y1="125" x2="660" y2="125" stroke="rgba(232,220,196,0.12)" />
          <line x1="40" y1="160" x2="660" y2="160" stroke="rgba(212,175,55,0.4)" />
          <text x="6" y="28" fill="#D8C3A5" font-size="9" font-family="monospace">10k</text>
          <text x="6" y="78" fill="#D8C3A5" font-size="9" font-family="monospace">5k</text>
          <text x="6" y="128" fill="#D8C3A5" font-size="9" font-family="monospace">1k</text>
          <text x="14" y="162" fill="#D8C3A5" font-size="9" font-family="monospace">0</text>

          <!-- 5-Year Historical Median Baseline (Malachite #2E6F40 dashed) -->
          <path d="M 40,158 L 95,156 L 135,142 L 165,157 L 215,156 L 255,140 L 290,157 L 340,156 L 380,143 L 415,157 L 465,156 L 505,142 L 540,157 L 600,155 L 630,143 L 660,158"
                fill="none" stroke="#2E6F40" stroke-width="2" stroke-dasharray="5,4" />

          <!-- Shaded Crimson Anomaly Fill -->
          <path d="M 40,158 L 105,155 L 122,85 L 134,18 L 148,95 L 165,157 L 235,155 L 252,48 L 268,72 L 285,156 L 365,155 L 382,132 L 400,157 L 490,155 L 506,120 L 525,157 L 610,154 L 624,98 L 642,156 L 660,158 Z"
                fill="rgba(168, 46, 46, 0.28)" />

          <!-- Animated Harmonised Line (Crimson #A82E2E / Gold #D4AF37) -->
          <path class="anomaly-line"
                d="M 40,158 L 105,155 L 122,85 L 134,18 L 148,95 L 165,157 L 235,155 L 252,48 L 268,72 L 285,156 L 365,155 L 382,132 L 400,157 L 490,155 L 506,120 L 525,157 L 610,154 L 624,98 L 642,156 L 660,158"
                fill="none" stroke="#D4AF37" stroke-width="2.2" />

          <!-- Peak Star Marker -->
          <circle cx="134" cy="18" r="5" fill="#A82E2E" stroke="#D4AF37" stroke-width="1.5" />
          <text x="144" y="22" fill="#D4AF37" font-size="10" font-weight="bold" font-family="monospace">★ 2020-09-09: 10,320 hotspots</text>
          <circle cx="252" cy="48" r="4.5" fill="#A82E2E" stroke="#D4AF37" stroke-width="1.2" />
          <text x="262" y="52" fill="#E8DCC4" font-size="9.5" font-family="monospace">2021-08-18 (Dixie Surge)</text>

          <!-- X Axis Labels -->
          <text x="110" y="176" fill="#D8C3A5" font-size="9.5" font-family="monospace">2020</text>
          <text x="235" y="176" fill="#D8C3A5" font-size="9.5" font-family="monospace">2021</text>
          <text x="365" y="176" fill="#D8C3A5" font-size="9.5" font-family="monospace">2022</text>
          <text x="490" y="176" fill="#D8C3A5" font-size="9.5" font-family="monospace">2023</text>
          <text x="615" y="176" fill="#D8C3A5" font-size="9.5" font-family="monospace">2024</text>
        </svg>

        <table class="streak-table">
          <thead>
            <tr>
              <th>SUSTAINED CRITICAL OUTBREAK STREAK</th>
              <th>START – END DATE</th>
              <th>DURATION</th>
              <th>TOTAL HOTSPOTS</th>
              <th>INCIDENT CORRELATION</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="color:#D4AF37;font-weight:bold;">#1 Sustained Streak (&gt;3× Median)</td>
              <td>2021-08-01 → 2021-08-23</td>
              <td>23 Days</td>
              <td>48,049</td>
              <td>Dixie Fire (963,309 ac)</td>
            </tr>
            <tr>
              <td style="color:#D4AF37;font-weight:bold;">#2 Sustained Streak (&gt;3× Median)</td>
              <td>2020-08-30 → 2020-09-19</td>
              <td>21 Days</td>
              <td>66,764</td>
              <td>August Complex &amp; Creek Fire</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="deck-panel glass">
      <div class="p-head">
        <span class="p-title">📡 SITUATIONAL AWARENESS // LIVE NRT FEED</span>
        <span class="telemetry-tag"><span class="live-dot"></span>STANDBY (0 API CALLS ON LOAD)</span>
      </div>
      <div class="feed-banner">
        <strong>⚠️ PROVISIONAL NRT DATA — SITUATIONAL AWARENESS ONLY</strong><br>
        NRT active fire detections are processed within 1–3 hours using predicted satellite ephemeris. Standard Processing (SP) replaces NRT after orbital calibration. Do not mix NRT with SP 2020–2024 multi-year trend analysis.
      </div>
      <div class="feed-stats">
        <div class="f-stat">
          <div class="f-lbl">Core Season Concentration</div>
          <div class="f-val">80% in 85 Days</div>
          <div style="font-size:0.68rem;color:#D8C3A5;">Jul 11 (DOY 192) – Oct 3 (DOY 276)</div>
        </div>
        <div class="f-stat">
          <div class="f-lbl">Biome Ratio (VIIRS/MODIS)</div>
          <div class="f-val">1.98 vs 2.01</div>
          <div style="font-size:0.68rem;color:#D8C3A5;">Northern Forests vs Sierra Nevada</div>
        </div>
        <div class="f-stat">
          <div class="f-lbl">● MODIS Reference</div>
          <div class="f-val">113,795 Kept</div>
          <div style="font-size:0.68rem;color:#D8C3A5;">Confidence ≥ 30 (Terra + Aqua)</div>
        </div>
        <div class="f-stat">
          <div class="f-lbl">▲ VIIRS Thresholded</div>
          <div class="f-val">233,379 Kept</div>
          <div style="font-size:0.68rem;color:#D8C3A5;">FRP ≥ 6.5 MW (NOAA-20 / NOAA-21)</div>
        </div>
      </div>
      <div style="background:rgba(28,27,26,0.75);border:1px solid rgba(212,175,55,0.3);border-radius:6px;padding:10px;display:flex;justify-content:space-between;align-items:center;">
        <div>
          <div style="font-size:0.76rem;font-weight:700;color:#E8DCC4;">Live FIRMS Area API Query (30-Day Rolling)</div>
          <div style="font-size:0.68rem;color:#D8C3A5;">Sources: MODIS_NRT, VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT</div>
        </div>
        <button style="background:#D4AF37;color:#1C1B1A;border:none;padding:7px 12px;border-radius:5px;font-weight:800;font-size:0.75rem;cursor:pointer;">🔄 Fetch Live FIRMS NRT</button>
      </div>
    </div>
  </main>

  <script>
    // 800ms count-up animation for telemetry KPIs
    document.querySelectorAll('.k-num[data-target]').forEach(el => {
      const target = parseInt(el.getAttribute('data-target'), 10);
      const suffix = el.textContent.includes('%') ? ' (52.0%)' : (el.textContent.includes('2020') ? ' (2020-09-09)' : '');
      const duration = 750;
      const start = performance.now();
      function step(now) {
        const p = Math.min((now - start) / duration, 1);
        const val = Math.floor(p * target);
        el.textContent = val.toLocaleString() + suffix;
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  </script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Concept C — "Minimal Scientific / Fluid Morph"
# ---------------------------------------------------------------------------

CONCEPT_C_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sekhmet Sync — Concept C: Minimal Scientific / Fluid Morph</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background-color: #E8DCC4;
    color: #1C1B1A;
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    padding: 20px 36px;
    gap: 16px;
  }}
  *:focus-visible {{
    outline: 2px solid #1B365D;
    outline-offset: 2px;
  }}
  /* Editorial Top Bar */
  .top-editorial {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    border-bottom: 1.5px solid #1C1B1A;
    padding-bottom: 12px;
  }}
  .journal-tag {{
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #5E4605;
    font-weight: 800;
  }}
  .main-title {{
    font-size: 1.55rem;
    font-weight: 800;
    color: #1C1B1A;
    letter-spacing: -0.02em;
    margin-top: 2px;
  }}
  /* Pill Navigation for 5 Tabs */
  .tab-pills {{
    display: flex;
    background: #D8C3A5;
    padding: 4px;
    border-radius: 999px;
    border: 1px solid rgba(28, 27, 26, 0.2);
    gap: 4px;
  }}
  .pill-tab {{
    border: none;
    background: transparent;
    color: #1C1B1A;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 220ms cubic-bezier(0.22, 1, 0.36, 1);
  }}
  .pill-tab:hover {{
    background: rgba(28, 27, 26, 0.08);
  }}
  .pill-tab.active {{
    background: #1C1B1A;
    color: #E8DCC4;
    font-weight: 700;
  }}
  /* Sliding Region Selector + KPI Summary Strip */
  .control-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
  }}
  .region-slider {{
    display: flex;
    background: #D8C3A5;
    padding: 4px;
    border-radius: 999px;
    border: 1px solid rgba(28, 27, 26, 0.18);
    gap: 4px;
  }}
  .reg-pill {{
    border: none;
    background: transparent;
    color: #1C1B1A;
    padding: 5px 12px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 220ms ease;
  }}
  .reg-pill.active {{
    background: #5E4605;
    color: #FFFFFF;
    font-weight: 700;
  }}
  .inline-metrics {{
    display: flex;
    gap: 22px;
    align-items: center;
  }}
  .im-item {{
    display: flex;
    flex-direction: column;
  }}
  .im-lbl {{
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #5E4605;
    font-weight: 800;
  }}
  .im-val {{
    font-size: 1.15rem;
    font-weight: 800;
    color: #1C1B1A;
  }}
  /* Centerpiece Fluid Morph Stage */
  .morph-stage {{
    background: #D8C3A5;
    border: 1px solid rgba(28, 27, 26, 0.22);
    border-radius: 12px;
    padding: 18px 24px;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 0;
  }}
  .stage-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .stage-title {{
    font-size: 1.02rem;
    font-weight: 800;
    color: #1C1B1A;
  }}
  .stage-sub {{
    font-size: 0.78rem;
    color: #5E4605;
    font-weight: 700;
    margin-top: 2px;
  }}
  .morph-toggle {{
    display: flex;
    background: #E8DCC4;
    padding: 3px;
    border-radius: 999px;
    border: 1px solid #5E4605;
  }}
  .m-btn {{
    border: none;
    background: transparent;
    color: #1C1B1A;
    padding: 5px 14px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 220ms ease;
  }}
  .m-btn.active {{
    background: #1C1B1A;
    color: #E8DCC4;
  }}
  /* 5x12 Monthly Heatmap Rollup with smooth scale entrance */
  .monthly-container {{
    background: #E8DCC4;
    border: 1px solid rgba(28, 27, 26, 0.18);
    border-radius: 8px;
    padding: 12px 16px;
    animation: fluidMorph 0.55s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }}
  @keyframes fluidMorph {{
    0%   {{ opacity: 0.2; transform: scale(0.97); }}
    100% {{ opacity: 1.0; transform: scale(1.0); }}
  }}
  .m-row {{
    display: grid;
    grid-template-columns: 48px repeat(12, 1fr);
    gap: 6px;
    align-items: center;
    margin-bottom: 6px;
  }}
  .m-row:last-child {{ margin-bottom: 0; }}
  .m-head {{
    margin-bottom: 8px;
    font-size: 0.74rem;
    font-weight: 800;
    color: #5E4605;
    text-align: center;
  }}
  .yr-lbl {{
    font-size: 0.80rem;
    font-weight: 800;
    color: #1C1B1A;
  }}
  .m-cell {{
    height: 36px;
    border-radius: 5px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.76rem;
    font-weight: 800;
    border: 1px solid rgba(28, 27, 26, 0.15);
    transition: transform 180ms ease;
  }}
  .m-cell:hover {{
    transform: scale(1.06);
    border-color: #1C1B1A;
    z-index: 2;
  }}
  /* Scientific Footnote & Season Summary */
  .sci-footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid rgba(28, 27, 26, 0.2);
    padding-top: 10px;
    font-size: 0.76rem;
  }}
  .legend-pills {{
    display: flex;
    gap: 14px;
    font-weight: 700;
  }}
  @media (prefers-reduced-motion: reduce) {{
    .monthly-container {{ animation: none !important; }}
  }}
</style>
</head>
<body>
  <header class="top-editorial">
    <div>
      <div class="journal-tag">NASA Space Apps 2026 • Empirical Sensor Harmonization Study (2020–2024)</div>
      <h1 class="main-title">Sekhmet Sync — California Burning Activity Calendar</h1>
    </div>
    <nav class="tab-pills" aria-label="Main Tabs">
      <button class="pill-tab active">📅 Burning Calendar</button>
      <button class="pill-tab">🗺️ Spatial Footprint</button>
      <button class="pill-tab">📈 Anomaly Analysis</button>
      <button class="pill-tab">📡 Situational Awareness</button>
      <button class="pill-tab">❓ Why Harmonisation</button>
    </nav>
  </header>

  <section class="control-bar">
    <div class="region-slider" role="radiogroup" aria-label="Region Selector">
      <button class="reg-pill active">California — Statewide</button>
      <button class="reg-pill">Northern Forests</button>
      <button class="reg-pill">Sierra Nevada / Central</button>
      <button class="reg-pill">Southern Chaparral</button>
      <button class="reg-pill">Custom BBox</button>
    </div>

    <div class="inline-metrics">
      <div class="im-item">
        <span class="im-lbl">Raw Hotspots</span>
        <span class="im-val">722,596</span>
      </div>
      <div class="im-item">
        <span class="im-lbl">Harmonised (≥6.5 MW)</span>
        <span class="im-val">347,174</span>
      </div>
      <div class="im-item">
        <span class="im-lbl">Filtered Faint VIIRS</span>
        <span class="im-val">52.0% (375,422)</span>
      </div>
      <div class="im-item">
        <span class="im-lbl">Peak Day (2020-09-09)</span>
        <span class="im-val">10,320</span>
      </div>
    </div>
  </section>

  <main class="morph-stage">
    <div class="stage-header">
      <div>
        <div class="stage-title">Monthly Burning Activity Rollup (5×12 Matrix) — Smooth Fluid Morph View</div>
        <div class="stage-sub">Core Fire Season Window: July 11 – Oct 3 (85 days • 80% of activity) • 1,827 Continuous Days Verified</div>
      </div>
      <div class="morph-toggle">
        <button class="m-btn">📅 Daily Matrix (5×366)</button>
        <button class="m-btn active">🗓️ Monthly Heatmap (5×12)</button>
        <button class="m-btn">📈 Daily Line vs. Median</button>
      </div>
    </div>

    <div class="monthly-container">
      {build_monthly_grid_html()}
    </div>

    <footer class="sci-footer">
      <div class="legend-pills">
        <span style="color:#1B365D;">● MODIS Reference: 113,795 (conf ≥ 30)</span>
        <span style="color:#5E4605;">▲ VIIRS Harmonised: 233,379 (FRP ≥ 6.5 MW)</span>
        <span style="color:#2E6F40;">― 5-Yr Median Baseline</span>
      </div>
      <div>
        <strong>Critical Streaks:</strong> 23-day Aug 1–23, 2021 (Dixie: 48,049) • 21-day Aug 30 – Sep 19, 2020 (August Complex: 66,764)
      </div>
    </footer>
  </main>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Concept D — "Map-First / Immersive"
# ---------------------------------------------------------------------------

CONCEPT_D_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sekhmet Sync — Concept D: Map-First / Immersive</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background-color: #1C1B1A;
    color: #E8DCC4;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    height: 100vh;
    width: 100vw;
    overflow: hidden;
    position: relative;
  }
  *:focus-visible {
    outline: 2px solid #D4AF37;
    outline-offset: 2px;
  }
  /* Full-Screen Map Canvas Background */
  .map-canvas {
    position: absolute;
    inset: 0;
    background:
      radial-gradient(circle at 48% 45%, rgba(27, 54, 93, 0.35), #1C1B1A 75%);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1;
  }
  /* Floating Glass Panels */
  .float-panel {
    background: rgba(28, 27, 26, 0.88);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(212, 175, 55, 0.45);
    border-radius: 10px;
    z-index: 10;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.45);
  }
  /* Top Floating Navigation Dock */
  .top-dock {
    position: absolute;
    top: 14px;
    left: 18px;
    right: 18px;
    padding: 9px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .dock-brand {
    font-size: 1.15rem;
    font-weight: 800;
    color: #D4AF37;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .dock-tabs {
    display: flex;
    gap: 6px;
  }
  .d-tab {
    background: rgba(232, 220, 196, 0.08);
    border: 1px solid transparent;
    color: #E8DCC4;
    padding: 5px 11px;
    border-radius: 6px;
    font-size: 0.76rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 180ms ease;
  }
  .d-tab:hover { border-color: #D4AF37; }
  .d-tab.active {
    background: #A82E2E;
    border-color: #D4AF37;
    color: #FFFFFF;
    font-weight: 700;
  }
  /* Left Slide-In Panel: Filters + KPIs */
  .left-drawer {
    position: absolute;
    top: 72px;
    left: 18px;
    bottom: 92px;
    width: 295px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    animation: slideLeft 0.45s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }
  @keyframes slideLeft {
    from { transform: translateX(-24px); opacity: 0; }
    to   { transform: translateX(0); opacity: 1; }
  }
  /* Right Slide-In Panel: Mini Calendar + Streaks */
  .right-drawer {
    position: absolute;
    top: 72px;
    right: 18px;
    bottom: 92px;
    width: 340px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    animation: slideRight 0.45s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }
  @keyframes slideRight {
    from { transform: translateX(24px); opacity: 0; }
    to   { transform: translateX(0); opacity: 1; }
  }
  .drawer-hdr {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #D4AF37;
    font-weight: 800;
    border-bottom: 1px solid rgba(212, 175, 55, 0.3);
    padding-bottom: 5px;
    margin-bottom: 8px;
  }
  .stat-stack {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .s-card {
    background: rgba(232, 220, 196, 0.08);
    border: 1px solid rgba(212, 175, 55, 0.28);
    border-radius: 6px;
    padding: 8px 10px;
  }
  .s-card-lbl { font-size: 0.66rem; color: #D8C3A5; text-transform: uppercase; }
  .s-card-val { font-size: 1.08rem; font-weight: 800; color: #E8DCC4; margin-top: 2px; }
  .reg-chips {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .r-chip {
    background: rgba(232, 220, 196, 0.07);
    border: 1px solid rgba(232, 220, 196, 0.2);
    color: #E8DCC4;
    padding: 6px 10px;
    border-radius: 5px;
    font-size: 0.74rem;
    text-align: left;
    cursor: pointer;
    transition: all 180ms ease;
  }
  .r-chip.active {
    background: rgba(212, 175, 55, 0.22);
    border-color: #D4AF37;
    color: #D4AF37;
    font-weight: 700;
  }
  /* Expanded Fire Tooltip on Map */
  .map-tooltip {
    position: absolute;
    top: 34%;
    left: 45%;
    background: #E8DCC4;
    color: #1C1B1A;
    border: 2px solid #5E4605;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 0.74rem;
    z-index: 15;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    transition: transform 200ms ease;
  }
  .map-tooltip:hover { transform: scale(1.04); }
  /* Bottom Interactive Timeline Scrubber */
  .bottom-scrubber {
    position: absolute;
    left: 18px;
    right: 18px;
    bottom: 14px;
    height: 64px;
    padding: 10px 18px;
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .scrub-track {
    flex: 1;
    height: 10px;
    background: rgba(232, 220, 196, 0.15);
    border-radius: 999px;
    position: relative;
    cursor: pointer;
  }
  .scrub-fill {
    width: 34%;
    height: 100%;
    background: linear-gradient(90deg, #C68B25, #A82E2E);
    border-radius: 999px;
  }
  .scrub-handle {
    position: absolute;
    left: 34%;
    top: -5px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #D4AF37;
    border: 2px solid #1C1B1A;
    box-shadow: 0 0 10px #D4AF37;
  }
  @media (prefers-reduced-motion: reduce) {
    .left-drawer, .right-drawer { animation: none !important; }
  }
</style>
</head>
<body>
  <!-- Full-Screen Spatial Map Canvas -->
  <div class="map-canvas">
    <svg viewBox="0 0 800 560" width="840" height="540" aria-label="Full Screen California Hotspot Map">
      <!-- Graticule Grid -->
      <line x1="150" y1="0" x2="150" y2="560" stroke="rgba(232,220,196,0.07)" />
      <line x1="300" y1="0" x2="300" y2="560" stroke="rgba(232,220,196,0.07)" />
      <line x1="450" y1="0" x2="450" y2="560" stroke="rgba(232,220,196,0.07)" />
      <line x1="600" y1="0" x2="600" y2="560" stroke="rgba(232,220,196,0.07)" />
      <line x1="0" y1="140" x2="800" y2="140" stroke="rgba(232,220,196,0.07)" />
      <line x1="0" y1="280" x2="800" y2="280" stroke="rgba(232,220,196,0.07)" />
      <line x1="0" y1="420" x2="800" y2="420" stroke="rgba(232,220,196,0.07)" />

      <!-- California Boundary -->
      <path d="M 275,75 L 405,75 L 405,205 L 545,365 L 515,465 L 435,470 L 345,380 L 285,255 L 255,150 Z"
            fill="rgba(232, 220, 196, 0.08)" stroke="#D4AF37" stroke-width="2" />

      <!-- Glowing Hotspot Clusters -->
      <circle cx="325" cy="145" r="26" fill="rgba(168, 46, 46, 0.35)" />
      <circle cx="385" cy="185" r="24" fill="rgba(168, 46, 46, 0.35)" />
      <circle cx="430" cy="275" r="22" fill="rgba(198, 139, 37, 0.32)" />
      <circle cx="465" cy="405" r="18" fill="rgba(168, 46, 46, 0.30)" />

      <!-- MODIS Circles (Lapis #1B365D with light rim) -->
      <circle cx="318" cy="142" r="5.5" fill="#1B365D" stroke="#E8DCC4" stroke-width="1.2" />
      <circle cx="378" cy="182" r="5.5" fill="#1B365D" stroke="#E8DCC4" stroke-width="1.2" />
      <circle cx="422" cy="272" r="5" fill="#1B365D" stroke="#E8DCC4" stroke-width="1.2" />
      <circle cx="310" cy="235" r="4.5" fill="#1B365D" stroke="#E8DCC4" stroke-width="1.2" />

      <!-- VIIRS Triangles (Ocher #C68B25) -->
      <polygon points="332,135 339,149 325,149" fill="#C68B25" stroke="#E8DCC4" stroke-width="1" />
      <polygon points="392,176 399,190 385,190" fill="#C68B25" stroke="#E8DCC4" stroke-width="1" />
      <polygon points="436,268 443,282 429,282" fill="#C68B25" stroke="#E8DCC4" stroke-width="1" />
      <polygon points="468,398 475,412 461,412" fill="#C68B25" stroke="#E8DCC4" stroke-width="1" />
    </svg>

    <!-- Hover-Expanded Tooltip -->
    <div class="map-tooltip">
      <div style="font-weight:800;color:#8B1E1E;">▲ VIIRS NOAA-20 Hotspot (Harmonised)</div>
      <div style="margin-top:3px;"><strong>Date:</strong> 2020-09-09 (Statewide Peak: 10,320)</div>
      <div><strong>FRP:</strong> 142.8 MW (Threshold ≥ 6.5 MW)</div>
      <div><strong>Location:</strong> 39.812°N, -122.941°W (August Complex)</div>
    </div>
  </div>

  <!-- Top Navigation Bar -->
  <header class="top-dock float-panel">
    <div class="dock-brand">
      <span>🔥 SEKHMET SYNC</span>
      <span style="font-size:0.74rem;color:#D8C3A5;font-weight:600;">California 2020–2024 • 1,827 Days • 347,174 Harmonised Hotspots</span>
    </div>
    <nav class="dock-tabs">
      <button class="d-tab">📅 Burning Calendar</button>
      <button class="d-tab active">🗺️ Spatial Footprint</button>
      <button class="d-tab">📈 Anomaly Analysis</button>
      <button class="d-tab">📡 Situational Awareness</button>
      <button class="d-tab">❓ Why Harmonisation</button>
    </nav>
  </header>

  <!-- Left Floating Panel: KPIs + Region Filter -->
  <aside class="left-drawer float-panel">
    <div>
      <div class="drawer-hdr">Archive Telemetry (2020–2024)</div>
      <div class="stat-stack">
        <div class="s-card">
          <div class="s-card-lbl">Raw Hotspots</div>
          <div class="s-card-val">722,596</div>
        </div>
        <div class="s-card">
          <div class="s-card-lbl">Harmonised</div>
          <div class="s-card-val" style="color:#D4AF37;">347,174</div>
        </div>
        <div class="s-card">
          <div class="s-card-lbl">Filtered (&lt;6.5 MW)</div>
          <div class="s-card-val">52.0%</div>
        </div>
        <div class="s-card">
          <div class="s-card-lbl">Peak (2020-09-09)</div>
          <div class="s-card-val" style="color:#A82E2E;">10,320</div>
        </div>
      </div>
    </div>

    <div>
      <div class="drawer-hdr">Ecosection / Region Filter</div>
      <div class="reg-chips">
        <button class="r-chip active">California — Statewide (347,174)</button>
        <button class="r-chip">Northern Forests (182,441)</button>
        <button class="r-chip">Sierra Nevada / Central (73,757)</button>
        <button class="r-chip">Southern Chaparral (25,549)</button>
        <button class="r-chip">Custom Lat / Lon Bounding Box</button>
      </div>
    </div>

    <div style="font-size:0.72rem;background:rgba(232,220,196,0.08);padding:8px;border-radius:6px;line-height:1.4;">
      <div><strong style="color:#D4AF37;">Shape + Color Legend:</strong></div>
      <div>● Circle (Lapis #1B365D) = MODIS (113,795)</div>
      <div>▲ Triangle (Ocher #C68B25) = VIIRS ≥6.5MW (233,379)</div>
    </div>
  </aside>

  <!-- Right Floating Panel: Calendar Mini-Matrix + Critical Periods -->
  <aside class="right-drawer float-panel">
    <div>
      <div class="drawer-hdr">Season Window &amp; Outbreak Streaks</div>
      <div style="background:rgba(232,220,196,0.08);padding:9px;border-radius:6px;font-size:0.74rem;line-height:1.45;">
        <div><strong style="color:#D4AF37;">Core Fire Season:</strong> July 11 – Oct 3</div>
        <div>Duration: <strong>85 days</strong> (80% of annual hotspots)</div>
        <hr style="border:none;border-top:1px solid rgba(232,220,196,0.15);margin:6px 0;">
        <div><strong>• 23-Day Streak (Aug 1–23, 2021):</strong><br>48,049 hotspots (Dixie Fire)</div>
        <div style="margin-top:4px;"><strong>• 21-Day Streak (Aug 30–Sep 19, 2020):</strong><br>66,764 hotspots (August Complex)</div>
      </div>
    </div>

    <div>
      <div class="drawer-hdr">5×12 Monthly Intensity Overlay</div>
      <div style="font-size:0.71rem;font-family:monospace;line-height:1.65;background:rgba(232,220,196,0.06);padding:8px;border-radius:6px;">
        <div>2020: [Jan..Jun Low] <span style="color:#C68B25;">Jul 6.1k</span> <span style="color:#A82E2E;">Aug 41.8k</span> <strong style="color:#D4AF37;">Sep 79.4k</strong></div>
        <div>2021: [Jan..Jun Low] <span style="color:#A82E2E;">Jul 18.9k</span> <strong style="color:#D4AF37;">Aug 66.7k</strong> <span style="color:#A82E2E;">Sep 24.2k</span></div>
        <div>2022: [Atmospheric River Suppression — Peak Sep 4.1k]</div>
        <div>2023: [NOAA-21 Added — Aug 9.8k, Sep 5.4k]</div>
        <div>2024: [Early Park Fire Surge — <strong style="color:#D4AF37;">Jul 19.7k</strong>, Aug 8.6k]</div>
      </div>
    </div>

    <div style="font-size:0.70rem;color:#D8C3A5;">
      ⚠️ Experimental 6.5 MW VIIRS threshold (375,422 faint detections filtered).
    </div>
  </aside>

  <!-- Bottom Timeline Scrubber -->
  <footer class="bottom-scrubber float-panel">
    <div style="font-size:0.76rem;font-weight:800;color:#D4AF37;white-space:nowrap;">
      ▶ SCRUB ARCHIVE: 2020-09-09 (DOY 253)
    </div>
    <div class="scrub-track">
      <div class="scrub-fill"></div>
      <div class="scrub-handle" tabindex="0" aria-label="Timeline Scrubber Handle"></div>
    </div>
    <div style="font-size:0.74rem;font-family:monospace;color:#E8DCC4;white-space:nowrap;">
      10,320 Hotspots • Day 618 of 1,827
    </div>
  </footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Write HTMLs & Capture Screenshots (1366x768 and 1920x1080)
# ---------------------------------------------------------------------------

CONCEPTS = [
    ("a", "A", CONCEPT_A_HTML),
    ("b", "B", CONCEPT_B_HTML),
    ("c", "C", CONCEPT_C_HTML),
    ("d", "D", CONCEPT_D_HTML),
]

RESOLUTIONS = [
    (1366, 768),
    (1920, 1080),
]


def capture_with_playwright(html_paths):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    print("[INFO] Capturing screenshots with Playwright Python API...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for lower_id, upper_id, _ in CONCEPTS:
            html_file = (OUT_DIR / f"concept-{lower_id}.html").resolve()
            for w, h in RESOLUTIONS:
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto(html_file.as_uri())
                page.wait_for_timeout(1100)  # Let <800ms animations finish settling
                out_png = OUT_DIR / f"concept-{upper_id}-{w}x{h}.png"
                page.screenshot(path=str(out_png), full_page=False)
                print(f"  -> Saved {out_png}")
                page.close()
        browser.close()
    return True


def capture_with_cli():
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
        return False

    print(f"[INFO] Capturing screenshots using CLI: {exe}")
    for lower_id, upper_id, _ in CONCEPTS:
        html_file = (OUT_DIR / f"concept-{lower_id}.html").resolve()
        for w, h in RESOLUTIONS:
            out_png = (OUT_DIR / f"concept-{upper_id}-{w}x{h}.png").resolve()
            if is_playwright:
                cmd = [
                    exe, "screenshot",
                    f"--viewport-size={w},{h}",
                    "--wait-for-timeout=1100",
                    html_file.as_uri(),
                    str(out_png),
                ]
            else:
                cmd = [
                    exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--window-size={w},{h}",
                    f"--screenshot={out_png}",
                    html_file.as_uri(),
                ]
            subprocess.run(cmd, check=True)
            print(f"  -> Saved {out_png}")
    return True


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_paths = []
    for lower_id, _, html_content in CONCEPTS:
        p = OUT_DIR / f"concept-{lower_id}.html"
        p.write_text(html_content, encoding="utf-8")
        html_paths.append(p)
        print(f"[OK] Wrote {p}")

    if not capture_with_playwright(html_paths):
        if not capture_with_cli():
            print(
                "\n[NOTICE] HTML files generated in ui-concepts/. "
                "Install playwright (`pip install playwright && playwright install chromium`) "
                "and re-run `python generate_ui_concepts.py` to generate the PNGs."
            )


if __name__ == "__main__":
    main()
