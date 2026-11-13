"""Web video search using local catalog and YouTube Data API v3.
Follows strict quotas, official youtube-nocookie embeds, and never scrapes.
"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
import urllib.request
import urllib.error

CONFIG_PATH = Path("config/trusted_channels.yaml")
CATALOG_PATH = Path("data/video_catalog.jsonl")
CACHE_PATH = Path("data/web_video_cache.json")
DAILY_CALL_CAP = 80
CACHE_TTL_DAYS = 7


def parse_iso8601_duration(dur_str: str) -> int:
    """Parses ISO 8601 duration (e.g. PT4M15S, PT1H2M10S, PT30S) into seconds."""
    if not dur_str:
        return 0
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", dur_str)
    if not m:
        return 0
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def normalize_query(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {"_meta": {"date": datetime.now().strftime("%Y-%m-%d"), "count": 0}, "queries": {}}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if "_meta" not in data:
            data["_meta"] = {"date": datetime.now().strftime("%Y-%m-%d"), "count": 0}
        if "queries" not in data:
            data["queries"] = {}
        return data
    except Exception:
        return {"_meta": {"date": datetime.now().strftime("%Y-%m-%d"), "count": 0}, "queries": {}}


def _save_cache(cache: dict):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"Warning: could not write video cache: {e}")


def check_and_increment_daily_cap(limit: int = DAILY_CALL_CAP) -> tuple[bool, int]:
    """Returns (is_allowed, current_count). Increments count if allowed."""
    cache = _load_cache()
    today = datetime.now().strftime("%Y-%m-%d")
    meta = cache.get("_meta", {})
    if meta.get("date") != today:
        meta["date"] = today
        meta["count"] = 0

    if meta["count"] >= limit:
        return False, meta["count"]

    meta["count"] += 1
    cache["_meta"] = meta
    _save_cache(cache)
    return True, meta["count"]


def get_cached_result(query: str) -> list[dict] | None:
    cache = _load_cache()
    norm = normalize_query(query)
    entry = cache.get("queries", {}).get(norm)
    if not entry:
        return None
    age_seconds = time.time() - entry.get("ts", 0)
    if age_seconds > (CACHE_TTL_DAYS * 86400):
        return None
    return entry.get("videos")


def save_cached_result(query: str, videos: list[dict]):
    cache = _load_cache()
    norm = normalize_query(query)
    if "queries" not in cache:
        cache["queries"] = {}
    cache["queries"][norm] = {
        "ts": time.time(),
        "videos": videos,
    }
    _save_cache(cache)


def load_trusted_channels() -> list[dict]:
    if not CONFIG_PATH.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        return data.get("channels", []) if data else []
    except Exception:
        return []


def load_catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    catalog = []
    try:
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    catalog.append(json.loads(line))
    except Exception:
        pass
    return catalog


def search_local_catalog(query: str, top_k: int = 3) -> list[dict]:
    """Matches query keywords against titles and descriptions in data/video_catalog.jsonl (0 API quota)."""
    catalog = load_catalog()
    if not catalog:
        return []

    q_words = set(re.findall(r"[a-zA-Z0-9]+", query.lower()))
    if not q_words:
        return []

    scored = []
    for item in catalog:
        title = item.get("title", "").lower()
        desc = item.get("description", "").lower()
        title_words = set(re.findall(r"[a-zA-Z0-9]+", title))
        desc_words = set(re.findall(r"[a-zA-Z0-9]+", desc))

        score = (len(q_words & title_words) * 3.0) + (len(q_words & desc_words) * 1.0)
        dur = item.get("duration", 0)
        if dur >= 180 and score >= 2.0:  # Must have duration >= 3m and meaningful match
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for _, item in scored[:top_k]:
        vid = item.get("id")
        results.append({
            "id": vid,
            "title": item.get("title", ""),
            "channel": item.get("channel", ""),
            "duration": item.get("duration", 0),
            "thumbnail": item.get("thumbnail", f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"),
            "embed_url": f"https://www.youtube-nocookie.com/embed/{vid}",
            "source": "catalog",
        })
    return results


def search_youtube_api(query: str, api_key: str | None = None, top_k: int = 3) -> tuple[list[dict], str | None]:
    """Queries official YouTube Data API v3 search.list and videos.list."""
    key = api_key or os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return [], "YOUTUBE_API_KEY environment variable is not configured."

    allowed, current = check_and_increment_daily_cap()
    if not allowed:
        return [], f"Daily YouTube search limit ({DAILY_CALL_CAP}) reached for today."

    try:
        # Step 1: search.list (costs 100 quota units)
        search_url = (
            f"https://www.googleapis.com/youtube/v3/search?"
            f"part=snippet&type=video&videoEmbeddable=true&maxResults=8"
            f"&q={quote_plus(query)}&key={key}"
        )
        req = urllib.request.Request(search_url, headers={"User-Agent": "EETutor/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        items = data.get("items", [])
        if not items:
            return [], None

        video_ids = [it["id"]["videoId"] for it in items if "videoId" in it.get("id", {})]
        if not video_ids:
            return [], None

        # Step 2: videos.list to check duration and embeddable status (costs 1 unit)
        videos_url = (
            f"https://www.googleapis.com/youtube/v3/videos?"
            f"part=contentDetails,snippet,status&id={','.join(video_ids)}&key={key}"
        )
        req2 = urllib.request.Request(videos_url, headers={"User-Agent": "EETutor/1.0"})
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            data2 = json.loads(resp2.read().decode("utf-8"))

        trusted = {ch.get("id") for ch in load_trusted_channels()}
        trusted_names = {ch.get("name", "").lower() for ch in load_trusted_channels()}

        candidates = []
        for v in data2.get("items", []):
            vid = v.get("id")
            snippet = v.get("snippet", {})
            status = v.get("status", {})
            content = v.get("contentDetails", {})

            # Check embeddable
            if not status.get("embeddable", True):
                continue

            dur_sec = parse_iso8601_duration(content.get("duration", ""))
            # Requirement: Drop videos under 3 minutes
            if dur_sec < 180:
                continue

            channel_id = snippet.get("channelId", "")
            channel_title = snippet.get("channelTitle", "")
            is_trusted = (channel_id in trusted) or (channel_title.lower() in trusted_names)

            thumb = snippet.get("thumbnails", {}).get("high", {}).get("url") or f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"

            candidates.append({
                "id": vid,
                "title": snippet.get("title", ""),
                "channel": channel_title,
                "duration": dur_sec,
                "thumbnail": thumb,
                "embed_url": f"https://www.youtube-nocookie.com/embed/{vid}",
                "is_trusted": is_trusted,
                "source": "youtube_api",
            })

        # Rank trusted channels first, then preserve relevance
        candidates.sort(key=lambda x: (not x["is_trusted"]))
        results = [{k: v for k, v in c.items() if k != "is_trusted"} for c in candidates[:top_k]]
        return results, None

    except urllib.error.HTTPError as e:
        err_msg = f"YouTube API HTTP {e.code}: {e.reason}"
        return [], err_msg
    except Exception as e:
        return [], f"YouTube search error: {str(e)}"


def find_web_videos(query: str, top_k: int = 3) -> dict:
    """Top-level function:
    1. Check 7-day cache
    2. Check local catalog (0 quota)
    3. Call YouTube Data API (with daily cap check)
    4. Save to cache
    """
    cached = get_cached_result(query)
    if cached is not None:
        return {"videos": cached, "warning": None, "source": "cache"}

    # 1. Local catalog search
    catalog_hits = search_local_catalog(query, top_k=top_k)
    if len(catalog_hits) >= 2:  # strong catalog match
        save_cached_result(query, catalog_hits)
        return {"videos": catalog_hits, "warning": None, "source": "catalog"}

    # 2. YouTube API fallback
    api_hits, err = search_youtube_api(query, top_k=top_k)
    if api_hits:
        save_cached_result(query, api_hits)
        return {"videos": api_hits, "warning": None, "source": "youtube_api"}

    # If API had an error but we had at least 1 catalog hit, return that
    if catalog_hits:
        save_cached_result(query, catalog_hits)
        return {"videos": catalog_hits, "warning": err, "source": "catalog"}

    return {"videos": [], "warning": err or "No suitable web videos found (>= 3 minutes).", "source": "none"}
