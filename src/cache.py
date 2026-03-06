"""File-based enrichment cache — avoids re-calling APIs for companies already processed."""

import json
from pathlib import Path

_CACHE_FILE = Path(__file__).parent.parent / "cache" / "enrichment_cache.json"


def _load() -> dict:
    if _CACHE_FILE.exists():
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(cache: dict) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _key(company_name: str) -> str:
    return company_name.lower().strip()


def get(company_name: str) -> dict | None:
    """Return cached enrichment data, or None if not yet cached."""
    return _load().get(_key(company_name))


def put(company_name: str, data: dict) -> None:
    """Store enrichment result in the cache for future runs."""
    cache = _load()
    cache[_key(company_name)] = data
    _save(cache)


def size() -> int:
    """Return total number of cached companies."""
    return len(_load())
