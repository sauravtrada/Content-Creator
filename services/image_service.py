"""
Image Service — Tiered image fetching system.

Priority order:
  1. Unsplash API  (requires UNSPLASH_ACCESS_KEY or Image_Key in .env)
  2. Pexels API    (requires PEXELS_API_KEY in .env)
  3. Direct URL    (if the input already is an http/https URL)
  4. DuckDuckGo    (no API key, last resort — may hit rate limits)
  5. None          (presentation continues without an image, never crashes)

All results are cached in memory so the same query is never fetched twice.
Parallel fetching is handled by the caller (ppt_utils / agent_graph) via
ThreadPoolExecutor — this module is intentionally synchronous per call.
"""

import os
import requests
import urllib.parse
from io import BytesIO
from dotenv import load_dotenv

load_dotenv(override=True)

# ── API keys ──────────────────────────────────────────────────────────────────
# Support both naming conventions
_UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY") or os.getenv("Image_Key") or ""
_PEXELS_KEY   = os.getenv("PEXELS_API_KEY", "")

# ── In-memory cache: query/url → BytesIO (seeked to 0) ───────────────────────
_image_cache: dict = {}

# ── Request helpers ───────────────────────────────────────────────────────────

def _download_url(url: str, timeout: int = 12) -> BytesIO | None:
    """Download a raw image URL and return a BytesIO stream, or None on failure."""
    try:
        resp = requests.get(url, timeout=timeout,
                            headers={"User-Agent": "PPT-Generator/1.0"},
                            allow_redirects=True)
        if resp.status_code == 200:
            ct = resp.headers.get("Content-Type", "").lower()
            if "image" in ct:
                buf = BytesIO(resp.content)
                buf.seek(0)
                return buf
            print(f"[ImageService] Non-image content-type at {url}: {ct}")
    except Exception as e:
        print(f"[ImageService] Download error ({url}): {e}")
    return None


# ── Tier 1: Unsplash ──────────────────────────────────────────────────────────

def _fetch_unsplash(query: str) -> BytesIO | None:
    if not _UNSPLASH_KEY:
        return None
    try:
        api_url = (
            "https://api.unsplash.com/search/photos"
            f"?query={urllib.parse.quote(query)}&per_page=1&orientation=landscape"
        )
        resp = requests.get(
            api_url,
            headers={"Authorization": f"Client-ID {_UNSPLASH_KEY}"},
            timeout=10
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                img_url = results[0]["urls"]["regular"]
                print(f"[ImageService] Unsplash hit for '{query}': {img_url[:60]}...")
                return _download_url(img_url)
        else:
            print(f"[ImageService] Unsplash API error {resp.status_code} for '{query}'")
    except Exception as e:
        print(f"[ImageService] Unsplash exception for '{query}': {e}")
    return None


# ── Tier 2: Pexels ────────────────────────────────────────────────────────────

def _fetch_pexels(query: str) -> BytesIO | None:
    if not _PEXELS_KEY:
        return None
    try:
        api_url = (
            "https://api.pexels.com/v1/search"
            f"?query={urllib.parse.quote(query)}&per_page=1&orientation=landscape"
        )
        resp = requests.get(
            api_url,
            headers={"Authorization": _PEXELS_KEY},
            timeout=10
        )
        if resp.status_code == 200:
            photos = resp.json().get("photos", [])
            if photos:
                img_url = photos[0]["src"]["large"]
                print(f"[ImageService] Pexels hit for '{query}': {img_url[:60]}...")
                return _download_url(img_url)
        else:
            print(f"[ImageService] Pexels API error {resp.status_code} for '{query}'")
    except Exception as e:
        print(f"[ImageService] Pexels exception for '{query}': {e}")
    return None


# ── Tier 3: DuckDuckGo (no key, last resort) ─────────────────────────────────

def _fetch_duckduckgo(query: str) -> BytesIO | None:
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=3))
        if results:
            img_url = results[0].get("image", "")
            if img_url:
                print(f"[ImageService] DuckDuckGo hit for '{query}': {img_url[:60]}...")
                return _download_url(img_url, timeout=8)
    except Exception as e:
        print(f"[ImageService] DuckDuckGo exception for '{query}': {e}")
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_image_for_query(query_or_url: str) -> BytesIO | None:
    """
    Given a search query string OR a direct image URL, return a BytesIO image
    stream positioned at 0, or None if all tiers fail.

    Results are cached so repeated calls with the same input are free.
    Never raises — always returns BytesIO or None.
    """
    if not query_or_url:
        return None

    cache_key = query_or_url.strip().lower()
    if cache_key in _image_cache:
        buf = _image_cache[cache_key]
        buf.seek(0)
        return buf

    result: BytesIO | None = None

    is_url = query_or_url.startswith(("http://", "https://"))

    if is_url:
        # Direct URL — skip search APIs
        result = _download_url(query_or_url)
    else:
        # Search tiers: Unsplash → Pexels → DuckDuckGo
        result = _fetch_unsplash(query_or_url)
        if result is None:
            result = _fetch_pexels(query_or_url)
        if result is None:
            result = _fetch_duckduckgo(query_or_url)

    if result:
        result.seek(0)
        _image_cache[cache_key] = result

    if result is None:
        print(f"[ImageService] All tiers failed for '{query_or_url}' — slide will have no image.")

    return result


def clear_cache():
    """Clear the in-memory image cache (useful between requests in long-running servers)."""
    _image_cache.clear()
