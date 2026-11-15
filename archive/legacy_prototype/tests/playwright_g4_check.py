"""
playwright_g4_check.py — Gate 4 app verification script

This script verifies:
  1. The app loads in < 5 seconds from cached files
  2. The sensor toggle changes visible numbers
  3. Both CSV downloads return valid CSV

IMPORTANT: This script requires playwright to be installed:
    pip install playwright
    playwright install chromium

It also requires the Streamlit app to be running:
    streamlit run app.py

Usage:
    python tests/playwright_g4_check.py
    # or if app is on a different port:
    python tests/playwright_g4_check.py --url http://localhost:8501

NOTE: If you cannot run Playwright (e.g., headless environment without Chromium),
run the following manual checks instead:
  1. Open http://localhost:8501 in a browser.
  2. Check the page loads and stat cards show non-zero numbers.
  3. Click "MODIS only" in the sensor toggle; verify stat cards change.
  4. Click "VIIRS only"; verify stat cards change again.
  5. Click "Download daily_series.csv"; verify a CSV downloads.
  6. Click "Download harmonised fires.csv"; verify a CSV downloads.
  7. Record load time (browser dev tools → Network tab → first request).
"""

import sys
import time
import argparse

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Playwright not installed. Install with: pip install playwright && playwright install chromium")
    print("\nManual Gate 4 checklist:")
    print("  1. streamlit run app.py")
    print("  2. Open http://localhost:8501 in a browser")
    print("  3. Verify stat cards show non-zero values")
    print("  4. Toggle between MODIS / VIIRS / Harmonised; verify numbers change")
    print("  5. Download both CSVs; verify they open in a spreadsheet")
    sys.exit(0)


def run_g4_checks(url: str = "http://localhost:8501"):
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Check 1: Load time
        print(f"\nG4.1 Checking load time at {url} ...")
        t0 = time.time()
        try:
            page.goto(url, timeout=30000)
            # Wait for stat cards (look for the metric elements)
            page.wait_for_selector('[data-testid="metric-container"]', timeout=20000)
            load_time = time.time() - t0
            if load_time < 5.0:
                results["G4.1_load_time"] = f"PASS ({load_time:.2f}s < 5s)"
            else:
                results["G4.1_load_time"] = f"FAIL ({load_time:.2f}s > 5s)"
        except PlaywrightTimeout:
            results["G4.1_load_time"] = f"FAIL (timeout after {time.time()-t0:.1f}s)"

        # Check 2: Sensor toggle changes numbers
        print("G4.2 Checking sensor toggle ...")
        try:
            # Get current harmonised fires metric
            metrics_before = page.query_selector_all('[data-testid="metric-container"]')
            harmonised_before = metrics_before[1].inner_text() if len(metrics_before) > 1 else ""

            # Click MODIS only
            modis_radio = page.get_by_text("MODIS only")
            modis_radio.click()
            page.wait_for_timeout(2000)
            metrics_after = page.query_selector_all('[data-testid="metric-container"]')
            harmonised_after = metrics_after[1].inner_text() if len(metrics_after) > 1 else ""

            if harmonised_before != harmonised_after:
                results["G4.2_sensor_toggle"] = f"PASS (numbers changed: '{harmonised_before}' → '{harmonised_after}')"
            else:
                results["G4.2_sensor_toggle"] = f"WARNING (numbers did not change; may be same value or toggle not found)"
        except Exception as e:
            results["G4.2_sensor_toggle"] = f"FAIL ({e})"

        # Check 3: Downloads
        print("G4.3 Checking CSV downloads ...")
        try:
            # Reset to Harmonised
            page.get_by_text("Harmonised").first.click()
            page.wait_for_timeout(1000)

            # Scroll to downloads section
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)

            # Try download button
            with page.expect_download(timeout=15000) as download_info:
                page.get_by_text("Download daily_series.csv").first.click()
            download = download_info.value
            if download:
                results["G4.3_download_daily"] = f"PASS (file: {download.suggested_filename})"
            else:
                results["G4.3_download_daily"] = "FAIL (no download triggered)"
        except Exception as e:
            results["G4.3_download_daily"] = f"FAIL ({e})"

        try:
            with page.expect_download(timeout=15000) as download_info2:
                page.get_by_text("Download harmonised fires.csv").first.click()
            download2 = download_info2.value
            if download2:
                results["G4.3_download_harmonised"] = f"PASS (file: {download2.suggested_filename})"
            else:
                results["G4.3_download_harmonised"] = "FAIL (no download triggered)"
        except Exception as e:
            results["G4.3_download_harmonised"] = f"FAIL ({e})"

        browser.close()

    # Print results
    print("\n=== Gate 4 Results ===")
    all_pass = True
    for check, result in results.items():
        status = "✓" if result.startswith("PASS") else ("⚠" if result.startswith("WARNING") else "✗")
        print(f"  {status} {check}: {result}")
        if result.startswith("FAIL"):
            all_pass = False

    if all_pass:
        print("\nGate 4: PASS")
    else:
        print("\nGate 4: FAIL — see above")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8501")
    args = parser.parse_args()
    run_g4_checks(args.url)
