"""Download EUR-Lex HTML with a local cache.

Raw HTML is kept under data/corpus/raw/<celex>.html next to a <celex>.meta.json that
records the URL and retrieval time, so an ingestion run is reproducible and the parser
can be re-run offline (`python -m ingest.seed stats`).

EUR-Lex sometimes answers a first request with a short interstitial page (cookie set-up
plus a meta-refresh or JavaScript redirect) instead of the document. The fetcher uses a
cookie-keeping session with browser-like headers and follows such redirects; a response
that still does not look like a document is written to <celex>.debug.html for inspection.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import requests

from compliance_agent.config import DATA_DIR

RAW_DIR = DATA_DIR / "corpus" / "raw"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://eur-lex.europa.eu/homepage.html",
}
MIN_DOC_CHARS = 50_000

CELLAR_URL = "https://publications.europa.eu/resource/celex/{celex}"
_WAF_MARKERS = ("awsWafCookieDomainList", "gokuProps", "challenge.js", "aws-waf-token")
_DOC_LINK = re.compile(r"""href=["']([^"']*?/DOC_1[^"']*)["']""", re.I)

_META_REFRESH = re.compile(
    r"""<meta[^>]+http-equiv=["']?refresh["']?[^>]+content=["'][^;]*;\s*url=([^"'>]+)""", re.I
)
_JS_REDIRECT = re.compile(r"""(?:window\.)?location(?:\.href)?\s*=\s*["']([^"']+)["']""", re.I)
_FORM_ACTION = re.compile(r"""<form[^>]+action=["']([^"']+)["']""", re.I)


@dataclass
class Fetched:
    celex: str
    url: str
    html: str
    retrieved_at: datetime
    from_cache: bool


def _paths(celex: str) -> tuple[Path, Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    return RAW_DIR / f"{celex}.html", RAW_DIR / f"{celex}.meta.json"


def looks_like_document(html: str) -> bool:
    return len(html) >= MIN_DOC_CHARS and "<html" in html[:2000].lower() and "Article" in html


def _redirect_target(html: str, current_url: str) -> str | None:
    for rx in (_META_REFRESH, _JS_REDIRECT):
        m = rx.search(html)
        if m:
            return urljoin(current_url, unescape(m.group(1).strip()))
    return None


def is_waf_challenge(html: str) -> bool:
    return any(marker in html for marker in _WAF_MARKERS)


def _download_cellar(celex: str, timeout: int) -> tuple[str, str]:
    """Official machine-access route: Cellar content negotiation for the HTML manifestation."""
    session = requests.Session()
    session.headers.update({**HEADERS, "Accept": "text/html", "Accept-Language": "eng"})
    url = CELLAR_URL.format(celex=celex)
    resp = session.get(url, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    html = resp.text
    if looks_like_document(html):
        return html, resp.url
    # Multi-file manifestations come back as a small index page linking DOC_1, DOC_2, ...
    m = _DOC_LINK.search(html)
    if m:
        doc_url = urljoin(resp.url, unescape(m.group(1)))
        resp = session.get(doc_url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.encoding or "utf-8"
        html = resp.text
        return html, resp.url
    return html, resp.url


def _download(url: str, timeout: int) -> tuple[str, str]:
    """GET with a cookie-keeping session; follow interstitial redirects. Returns (html, final_url)."""
    session = requests.Session()
    session.headers.update(HEADERS)
    # A visit to the homepage first lets EUR-Lex set its session cookies.
    try:
        session.get("https://eur-lex.europa.eu/homepage.html", timeout=timeout)
    except requests.RequestException:
        pass
    current = url
    html = ""
    for _hop in range(4):
        resp = session.get(current, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.encoding or "utf-8"
        html = resp.text
        if looks_like_document(html):
            return html, resp.url
        target = _redirect_target(html, resp.url)
        if not target or target == current:
            break
        current = target
        time.sleep(1)
    return html, current


def fetch(celex: str, url: str, *, force: bool = False, timeout: int = 60, retries: int = 3) -> Fetched:
    html_path, meta_path = _paths(celex)
    if html_path.exists() and meta_path.exists() and not force:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return Fetched(
            celex=celex,
            url=meta.get("url", url),
            html=html_path.read_text(encoding="utf-8"),
            retrieved_at=datetime.fromisoformat(meta["retrieved_at"]),
            from_cache=True,
        )

    # Manually saved file (browser "Save as... Webpage, HTML only") without meta: adopt it.
    if html_path.exists() and not meta_path.exists():
        html = html_path.read_text(encoding="utf-8", errors="replace")
        if not looks_like_document(html):
            raise RuntimeError(
                f"{html_path} exists but does not look like a full EUR-Lex document ({len(html)} chars). "
                f"Save the page again with 'Webpage, HTML only' from {url}."
            )
        retrieved_at = datetime.fromtimestamp(html_path.stat().st_mtime, tz=timezone.utc)
        _write_meta(meta_path, celex, url, "manual-browser-save", retrieved_at, len(html))
        return Fetched(celex=celex, url=url, html=html, retrieved_at=retrieved_at, from_cache=True)

    last_err: Exception | None = None
    html = ""
    final_url = url
    waf_seen = False
    for attempt in range(1, retries + 1):
        try:
            # 1) Cellar (official machine-access endpoint), 2) EUR-Lex web page.
            try:
                html, final_url = _download_cellar(celex, timeout)
            except Exception as cellar_exc:
                html, final_url = "", f"cellar failed: {cellar_exc}"
            if not looks_like_document(html):
                html, final_url = _download(url, timeout)
            if looks_like_document(html):
                break
            debug_path = RAW_DIR / f"{celex}.debug.html"
            debug_path.write_text(html, encoding="utf-8")
            if is_waf_challenge(html):
                waf_seen = True
                raise RuntimeError("EUR-Lex answered with an AWS WAF browser challenge (bot protection)")
            snippet = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))[:300]
            raise RuntimeError(
                f"Response for {celex} does not look like a full EUR-Lex document "
                f"({len(html)} chars, final url {final_url}); saved to {debug_path}. Starts with: {snippet!r}"
            )
        except Exception as exc:  # network hiccups, EUR-Lex 5xx, interstitial pages
            last_err = exc
            if waf_seen:
                break
            if attempt < retries:
                time.sleep(3 * attempt)
    else:
        last_err = last_err or RuntimeError("no response")
    if not looks_like_document(html):
        raise RuntimeError(
            f"Could not download {celex} automatically ({last_err}).\n\n"
            f"Manual fallback (takes a minute per document):\n"
            f"  1. Open this URL in your browser:  {url}\n"
            f"  2. Press Ctrl+S and choose 'Webpage, HTML only'.\n"
            f"  3. Save it as:  {html_path}\n"
            f"  4. Re-run the same command; the saved file is picked up automatically."
        )

    retrieved_at = datetime.now(timezone.utc)
    html_path.write_text(html, encoding="utf-8")
    _write_meta(meta_path, celex, url, final_url, retrieved_at, len(html))
    return Fetched(celex=celex, url=url, html=html, retrieved_at=retrieved_at, from_cache=False)


def _write_meta(meta_path: Path, celex: str, url: str, final_url: str, retrieved_at: datetime, nbytes: int) -> None:
    meta_path.write_text(
        json.dumps(
            {"celex": celex, "url": url, "final_url": final_url, "retrieved_at": retrieved_at.isoformat(), "bytes": nbytes},
            indent=2,
        ),
        encoding="utf-8",
    )


def load_cached(celex: str) -> Fetched | None:
    html_path, meta_path = _paths(celex)
    if not (html_path.exists() and meta_path.exists()):
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return Fetched(
        celex=celex,
        url=meta["url"],
        html=html_path.read_text(encoding="utf-8"),
        retrieved_at=datetime.fromisoformat(meta["retrieved_at"]),
        from_cache=True,
    )
