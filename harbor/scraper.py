"""Fetch published Help Center articles from the public Zendesk API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from harbor.config import ARTICLES_API, MIN_ARTICLES, ZENDESK_LOCALE

log = logging.getLogger(__name__)

USER_AGENT = "harbor-kb/0.1 (+https://github.com/)"
PAGE_SIZE = 100


class ScrapeError(RuntimeError):
    pass


def parse_zendesk_time(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def newest_timestamp(values: list[str]) -> str:
    best: datetime | None = None
    best_raw = ""
    for value in values:
        parsed = parse_zendesk_time(value)
        if parsed is None:
            continue
        if best is None or parsed > best:
            best = parsed
            best_raw = value
    return best_raw


def fetch_articles(
    *,
    locale: str = ZENDESK_LOCALE,
    min_articles: int = MIN_ARTICLES,
    updated_after: str | None = None,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Pull published articles, newest first.

    If updated_after is set (ISO timestamp), stop paging once Zendesk returns
    an article at or older than that watermark. min_articles is enforced only
    on a full scrape (no watermark).
    """
    own_client = client is None
    if own_client:
        client = httpx.Client(
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )
    assert client is not None

    watermark = parse_zendesk_time(updated_after)
    articles: list[dict[str, Any]] = []
    url: str | None = ARTICLES_API.format(locale=locale)
    params: dict[str, Any] | None = {
        "per_page": PAGE_SIZE,
        "sort_by": "updated_at",
        "sort_order": "desc",
    }

    try:
        while url:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            page = payload.get("articles") or []
            reached_watermark = False
            for item in page:
                if item.get("draft"):
                    continue
                if not (item.get("body") or "").strip():
                    continue
                if watermark is not None:
                    stamped = parse_zendesk_time(
                        str(item.get("updated_at") or item.get("edited_at") or "")
                    )
                    if stamped is not None and stamped <= watermark:
                        reached_watermark = True
                        break
                articles.append(item)
            if reached_watermark:
                log.info("stopped at watermark %s after %s newer articles", updated_after, len(articles))
                break
            url = payload.get("next_page")
            params = None
            log.info("fetched %s published articles so far", len(articles))
    except httpx.HTTPError as exc:
        raise ScrapeError(f"Zendesk Help Center request failed: {exc}") from exc
    finally:
        if own_client:
            client.close()

    if watermark is None and len(articles) < min_articles:
        raise ScrapeError(
            f"Only fetched {len(articles)} published articles; need at least {min_articles}."
        )
    log.info("scrape complete: %s published articles", len(articles))
    return articles
