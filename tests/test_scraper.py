from unittest.mock import MagicMock

import httpx
import pytest

from harbor.scraper import (
    RateLimiter,
    ScrapeError,
    fetch_articles,
    newest_timestamp,
    parse_zendesk_time,
    retry_after_seconds,
)


def _response(payload: dict, status: int = 200, headers: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.request = MagicMock()
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status}", request=resp.request, response=resp
        )
    else:
        resp.raise_for_status = MagicMock()
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

    articles = fetch_articles(min_articles=2, client=client, min_interval=0)
    assert [a["id"] for a in articles] == [1, 4]
    assert client.get.call_count == 2


def test_fetch_articles_requires_minimum():
    client = MagicMock()
    client.get.return_value = _response({"articles": [], "next_page": None})
    with pytest.raises(ScrapeError, match="Only fetched 0"):
        fetch_articles(min_articles=30, client=client, min_interval=0)


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
        min_interval=0,
    )
    assert [a["id"] for a in articles] == [1]
    assert client.get.call_count == 1


def test_watermark_helpers():
    assert parse_zendesk_time("2026-09-20T10:00:00Z") is not None
    assert newest_timestamp(["2026-09-10T00:00:00Z", "2026-09-20T10:00:00Z"]) == (
        "2026-09-20T10:00:00Z"
    )


def test_rate_limiter_spaces_calls():
    slept: list[float] = []
    now = {"t": 10.0}

    def clock() -> float:
        return now["t"]

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        now["t"] += seconds

    limiter = RateLimiter(0.5, sleep=fake_sleep, clock=clock)
    limiter.wait()
    limiter.wait()
    assert slept == [pytest.approx(0.5)]


def test_retry_after_header():
    resp = MagicMock()
    resp.headers = {"Retry-After": "3"}
    assert retry_after_seconds(resp, 1) == 3.0
    resp.headers = {}
    assert retry_after_seconds(resp, 3) == 8.0


def test_retries_on_http_429():
    page = {
        "articles": [{"id": 1, "draft": False, "body": "<p>one</p>"}],
        "next_page": None,
    }
    client = MagicMock()
    client.get.side_effect = [
        _response({}, status=429, headers={"Retry-After": "1.5"}),
        _response(page),
    ]
    slept: list[float] = []
    articles = fetch_articles(
        min_articles=1,
        client=client,
        min_interval=0,
        sleep=slept.append,
    )
    assert [a["id"] for a in articles] == [1]
    assert client.get.call_count == 2
    assert slept == [1.5]


def test_rate_limit_waits_between_pages():
    page1 = {
        "articles": [{"id": 1, "draft": False, "body": "<p>one</p>"}],
        "next_page": "https://example.invalid/page2",
    }
    page2 = {
        "articles": [{"id": 2, "draft": False, "body": "<p>two</p>"}],
        "next_page": None,
    }
    client = MagicMock()
    client.get.side_effect = [_response(page1), _response(page2)]
    slept: list[float] = []
    articles = fetch_articles(
        min_articles=2,
        client=client,
        min_interval=0.4,
        sleep=slept.append,
    )
    assert [a["id"] for a in articles] == [1, 2]
    assert slept
    assert slept[0] == pytest.approx(0.4, abs=0.05)
