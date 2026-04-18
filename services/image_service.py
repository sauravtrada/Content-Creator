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

# ── In-memory cache ───────────────────────────────────────────────────────────
_url_cache: dict = {}      # query -> url
_image_cache: dict = {}    # url/query -> BytesIO (seeked to 0)

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


# ── Search Tiers ──────────────────────────────────────────────────────────────

def _search_unsplash_url(query: str) -> str | None:
    if not _UNSPLASH_KEY: return None
    try:
        api_url = f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(query)}&per_page=1&orientation=landscape"
        resp = requests.get(api_url, headers={"Authorization": f"Client-ID {_UNSPLASH_KEY}"}, timeout=10)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results: return results[0]["urls"]["regular"]
    except Exception as e: print(f"[ImageService] Unsplash search error: {e}")
    return None

def _search_pexels_url(query: str) -> str | None:
    if not _PEXELS_KEY: return None
    try:
        api_url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page=1&orientation=landscape"
        resp = requests.get(api_url, headers={"Authorization": _PEXELS_KEY}, timeout=10)
        if resp.status_code == 200:
            photos = resp.json().get("photos", [])
            if photos: return photos[0]["src"]["large"]
    except Exception as e: print(f"[ImageService] Pexels search error: {e}")
    return None

def _search_duckduckgo_url(query: str) -> str | None:
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=3))
        if results: return results[0].get("image")
    except Exception as e: print(f"[ImageService] DDG search error: {e}")
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def search_image_url(query: str) -> str | None:
    """Search for a relevant image URL using tiered providers."""
    if not query: return None
    
    clean_query = query.strip().lower()
    if clean_query in _url_cache:
        return _url_cache[clean_query]

    # Tiered search
    url = _search_unsplash_url(query)
    if not url: url = _search_pexels_url(query)
    if not url: url = _search_duckduckgo_url(query)

    if url:
        _url_cache[clean_query] = url
    return url

def fetch_image_for_query(query_or_url: str) -> BytesIO | None:
    """
    Given a search query string OR a direct image URL, return a BytesIO image
    stream positioned at 0.
    """
    if not query_or_url: return None

    # Check image cache first
    cache_key = query_or_url.strip().lower()
    if cache_key in _image_cache:
        buf = _image_cache[cache_key]
        buf.seek(0)
        return buf

    # 1. Determine the URL
    is_url = query_or_url.startswith(("http://", "https://"))
    url = query_or_url if is_url else search_image_url(query_or_url)

    if not url:
        return None

    # 2. Check if we have the image for THIS specific URL cached
    if url in _image_cache:
        buf = _image_cache[url]
        buf.seek(0)
        return buf

    # 3. Download
    result = _download_url(url)
    if result:
        result.seek(0)
        _image_cache[url] = result
    
    return result


def clear_cache():
    _url_cache.clear()
    _image_cache.clear()
