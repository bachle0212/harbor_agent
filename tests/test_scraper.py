from unittest.mock import MagicMock

import pytest

from harbor.scraper import ScrapeError, fetch_articles, newest_timestamp, parse_zendesk_time


def _response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    return resp


def test_fetch_articles_skips_drafts_and_paginates():
    page1 = {
        "articles": [
            {"id": 1, "draft": False, "body": "<p>one</p>", "title": "One"},
            {"id": 2, "draft": True, "body": "<p>secret</p>", "title": "Draft"},
            {"id": 3, "draft": False, "body": "   ", "title": "Empty"},
        ],
        "next_page": "https://example.invalid/page2",
    }
    page2 = {
        "articles": [
            {"id": 4, "draft": False, "body": "<p>four</p>", "title": "Four"},
        ],
        "next_page": None,
    }
    client = MagicMock()
    client.get.side_effect = [_response(page1), _response(page2)]

    articles = fetch_articles(min_articles=2, client=client)
    assert [a["id"] for a in articles] == [1, 4]
    assert client.get.call_count == 2


def test_fetch_articles_requires_minimum():
    client = MagicMock()
    client.get.return_value = _response({"articles": [], "next_page": None})
    with pytest.raises(ScrapeError, match="Only fetched 0"):
        fetch_articles(min_articles=30, client=client)


def test_fetch_articles_stops_at_watermark():
    page1 = {
        "articles": [
            {
                "id": 1,
                "draft": False,
                "body": "<p>new</p>",
                "updated_at": "2026-09-20T10:00:00Z",
            },
            {
                "id": 2,
                "draft": False,
                "body": "<p>old</p>",
                "updated_at": "2026-09-10T10:00:00Z",
            },
        ],
        "next_page": "https://example.invalid/page2",
    }
    client = MagicMock()
    client.get.return_value = _response(page1)

    articles = fetch_articles(
        min_articles=30,
        updated_after="2026-09-15T00:00:00Z",
        client=client,
    )
    assert [a["id"] for a in articles] == [1]
    assert client.get.call_count == 1


def test_watermark_helpers():
    assert parse_zendesk_time("2026-09-20T10:00:00Z") is not None
    assert newest_timestamp(["2026-09-10T00:00:00Z", "2026-09-20T10:00:00Z"]) == (
        "2026-09-20T10:00:00Z"
    )
