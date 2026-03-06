import os
from typing import Any, Dict, List

import requests


GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX", "")


def search_web(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Lightweight wrapper around Google Programmable Search JSON API.

    Returns a list of dicts with keys: title, snippet, link.
    If GOOGLE_SEARCH_API_KEY / GOOGLE_SEARCH_CX are not configured, returns an empty list.
    """
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_CX:
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_SEARCH_API_KEY,
        "cx": GOOGLE_SEARCH_CX,
        "q": query,
        "num": max_results,
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", []) or []
        results: List[Dict[str, Any]] = []
        for item in items[:max_results]:
            results.append(
                {
                    "title": item.get("title"),
                    "snippet": item.get("snippet"),
                    "link": item.get("link"),
                }
            )
        return results
    except Exception:
        return []

