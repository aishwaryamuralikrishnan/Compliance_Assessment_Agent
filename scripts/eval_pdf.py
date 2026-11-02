"""Print the evaluation report's print view (/evaluation/print, public, every section in sequence) of the running
web app to a PDF (and a PNG), so the pages and the file are one and the same rendering.

    python scripts/eval_pdf.py                                   # http://localhost:3000, eval/report/evaluation.pdf
    python scripts/eval_pdf.py --base http://localhost:3000 --out eval/report/evaluation.pdf --png

Needs the API and the web app running and Playwright with Chromium installed (pip install playwright; playwright
install chromium). No login: the report is public. A4, backgrounds on, the definitions printed under each section.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3000")
    ap.add_argument("--out", default=str(ROOT / "eval" / "report" / "evaluation.pdf"))
    ap.add_argument("--png", action="store_true", help="also save a full-page PNG next to the PDF")
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed: pip install playwright && playwright install chromium", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{a.base}/evaluation/print")
        page.wait_for_selector(".printsection .glossary, .band.wait", timeout=30000)
        if page.query_selector(".band.wait"):
            print("the page shows no report: " + (page.inner_text(".band.wait") or ""), file=sys.stderr)
            browser.close()
            return 1
        page.wait_for_timeout(500)
        page.emulate_media(media="print")
        page.pdf(path=str(out), format="A4", print_background=True, margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"},
                 display_header_footer=True, header_template="<div></div>",
                 footer_template="<div style='font-size:8px;color:#5B6B85;width:100%;text-align:center;font-family:Inter,system-ui,sans-serif'>Compliance Assistant · evaluation report · page <span class='pageNumber'></span> of <span class='totalPages'></span></div>")
        if a.png:
            page.emulate_media(media="screen")
            page.screenshot(path=str(out.with_suffix(".png")), full_page=True)
        browser.close()
    print(f"wrote {out}" + (f" and {out.with_suffix('.png')}" if a.png else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
