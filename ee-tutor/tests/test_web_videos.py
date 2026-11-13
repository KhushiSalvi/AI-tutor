"""Unit tests for Web Video Finder (YouTube API, catalog, duration parsing, cache, and quota cap)."""
import json
try:
    import pytest
except ImportError:
    pytest = None
from unittest.mock import patch, MagicMock
from core.video.web_videos import (
    parse_iso8601_duration,
    check_and_increment_daily_cap,
    search_local_catalog,
    get_cached_result,
    save_cached_result,
    search_youtube_api,
    find_web_videos,
)


def test_parse_iso8601_duration():
    assert parse_iso8601_duration("PT4M15S") == 255
    assert parse_iso8601_duration("PT1H2M10S") == 3730
    assert parse_iso8601_duration("PT50S") == 50
    assert parse_iso8601_duration("PT10M") == 600
    assert parse_iso8601_duration("PT2H") == 7200
    assert parse_iso8601_duration("") == 0
    assert parse_iso8601_duration("invalid") == 0


def test_daily_call_cap():
    mock_cache = {"_meta": {"date": "2026-11-12", "count": 79}, "queries": {}}
    with patch("core.video.web_videos._load_cache", return_value=mock_cache), \
         patch("core.video.web_videos._save_cache"):
        # 80th call allowed
        allowed, count = check_and_increment_daily_cap(limit=80)
        assert allowed is True
        assert count == 80

        # 81st call blocked
        allowed, count = check_and_increment_daily_cap(limit=80)
        assert allowed is False
        assert count == 80


def test_search_local_catalog_filtering():
    fake_catalog = [
        {
            "id": "vid1",
            "title": "MOSFET saturation operation and transconductance",
            "description": "Explaining the drain current equation in saturation region",
            "channel": "Razavi Electronics",
            "duration": 600,  # 10 mins (valid)
        },
        {
            "id": "vid2",
            "title": "Short MOSFET overview",
            "description": "Short explanation",
            "channel": "Random Channel",
            "duration": 90,  # 1.5 mins (< 3 mins! Must be dropped)
        },
        {
            "id": "vid3",
            "title": "French Revolution History",
            "description": "Bastille day storming",
            "channel": "History Hub",
            "duration": 500,
        }
    ]

    with patch("core.video.web_videos.load_catalog", return_value=fake_catalog):
        hits = search_local_catalog("MOSFET saturation transconductance", top_k=3)
        assert len(hits) == 1
        assert hits[0]["id"] == "vid1"
        assert hits[0]["embed_url"] == "https://www.youtube-nocookie.com/embed/vid1"


def test_find_web_videos_cache_hit():
    cached_vids = [{"id": "cached1", "title": "Cached Video", "channel": "EE Channel", "duration": 300, "thumbnail": "", "embed_url": ""}]
    with patch("core.video.web_videos.get_cached_result", return_value=cached_vids):
        res = find_web_videos("MOSFET saturation")
        assert res["source"] == "cache"
        assert len(res["videos"]) == 1
        assert res["videos"][0]["id"] == "cached1"


def test_search_youtube_api_mocked():
    search_json = {
        "items": [
            {"id": {"videoId": "vid_long"}, "snippet": {"title": "Full Lecture"}},
            {"id": {"videoId": "vid_short"}, "snippet": {"title": "Short Clip"}},
        ]
    }
    videos_json = {
        "items": [
            {
                "id": "vid_long",
                "snippet": {
                    "title": "Full Lecture on Thevenin",
                    "channelId": "UCwNjyff_5zFkQfQp2fLgZqg",
                    "channelTitle": "NPTEL-NOC IITM",
                    "thumbnails": {"high": {"url": "https://img.youtube.com/thumb.jpg"}}
                },
                "status": {"embeddable": True},
                "contentDetails": {"duration": "PT25M30S"}  # > 3 mins
            },
            {
                "id": "vid_short",
                "snippet": {
                    "title": "Short Thevenin 30s",
                    "channelId": "random123",
                    "channelTitle": "Quick Tips",
                    "thumbnails": {}
                },
                "status": {"embeddable": True},
                "contentDetails": {"duration": "PT45S"}  # < 3 mins, must be dropped!
            }
        ]
    }

    mock_resp1 = MagicMock()
    mock_resp1.read.return_value = json.dumps(search_json).encode("utf-8")
    mock_resp1.__enter__.return_value = mock_resp1

    mock_resp2 = MagicMock()
    mock_resp2.read.return_value = json.dumps(videos_json).encode("utf-8")
    mock_resp2.__enter__.return_value = mock_resp2

    with patch("core.video.web_videos.check_and_increment_daily_cap", return_value=(True, 1)), \
         patch("urllib.request.urlopen", side_effect=[mock_resp1, mock_resp2]):
        vids, err = search_youtube_api("Thevenin theorem", api_key="FAKE_KEY", top_k=3)
        assert err is None
        assert len(vids) == 1
        assert vids[0]["id"] == "vid_long"
        assert vids[0]["channel"] == "NPTEL-NOC IITM"
        assert vids[0]["duration"] == 1530
        assert vids[0]["embed_url"] == "https://www.youtube-nocookie.com/embed/vid_long"
