"""Fetch published Help Center articles from the public Zendesk API.

No auth: `GET /api/v2/help_center/{locale}/articles.json`. Incremental
exports (`/incremental/tickets`, etc.) need an admin token, so daily runs
instead sort `updated_at desc` and stop at `Catalog.scrape_watermark`.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from harbor.config import (
    ARTICLES_API,
    MIN_ARTICLES,
    SCRAPE_MAX_RETRIES,
    SCRAPE_MIN_INTERVAL,
    ZENDESK_LOCALE,
)

log = logging.getLogger(__name__)

USER_AGENT = "harbor-kb/0.1 (+https://github.com/)"
PAGE_SIZE = 100


class ScrapeError(RuntimeError):
    pass


class RateLimiter:
    """Space requests by min_interval seconds (no-op when interval ≤ 0)."""

    def __init__(
        self,
        min_interval: float,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.min_interval = max(0.0, min_interval)
        self._sleep = sleep
        self._clock = clock
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        gap = self.min_interval - (self._clock() - self._last)
        if gap > 0:
            self._sleep(gap)
        self._last = self._clock()

    def backoff(self, seconds: float) -> None:
        if seconds > 0:
            self._sleep(seconds)
        self._last = self._clock()


def retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    raw = (response.headers.get("Retry-After") or response.headers.get("retry-after") or "").strip()
    if raw:
        try:
            return min(max(float(raw), 0.0), 60.0)
        except ValueError:
            pass
    return min(2.0**attempt, 30.0)


def _get_json(
    client: httpx.Client,
    url: str,
    params: dict[str, Any] | None,
    limiter: RateLimiter,
    *,
    max_retries: int,
) -> dict[str, Any]:
    last_error: Exception | None = None
    attempts = max(1, max_retries)
    for attempt in range(1, attempts + 1):
        limiter.wait()
        try:
            response = client.get(url, params=params)
        except httpx.TransportError as exc:
            last_error = exc
            delay = min(2.0**attempt, 16.0)
            log.warning("scrape   transport error, sleep %.1fs (%s/%s): %s", delay, attempt, attempts, exc)
            limiter.backoff(delay)
            continue
        if response.status_code == 429:
            delay = retry_after_seconds(response, attempt)
            log.warning("scrape   HTTP 429, sleep %.1fs (%s/%s)", delay, attempt, attempts)
            limiter.backoff(delay)
            last_error = httpx.HTTPStatusError(
                "Too Many Requests", request=response.request, response=response
            )
            continue
        if response.status_code >= 500:
            delay = min(2.0**attempt, 16.0)
            log.warning(
                "scrape   HTTP %s, sleep %.1fs (%s/%s)",
                response.status_code,
                delay,
                attempt,
                attempts,
            )
            limiter.backoff(delay)
            last_error = httpx.HTTPStatusError(
                f"Server error {response.status_code}",
                request=response.request,
                response=response,
            )
            continue
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ScrapeError(f"Zendesk Help Center request failed: {exc}") from exc
        payload = response.json()
        if not isinstance(payload, dict):
            raise ScrapeError("Zendesk Help Center returned a non-object JSON body.")
        return payload
    raise ScrapeError(f"Zendesk Help Center request failed after {attempts} attempts: {last_error}")


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
    min_interval: float | None = None,
    max_retries: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Pull published articles, newest first.

    If updated_after is set (ISO timestamp), stop paging once Zendesk returns
    an article at or older than that watermark. min_articles is enforced only
    on a full scrape (no watermark). Pages are spaced by min_interval; HTTP 429
    waits Retry-After (capped at 60s) and retries.
    """
    own_client = client is None
    if own_client:
        client = httpx.Client(
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )
    assert client is not None

    limiter = RateLimiter(
        SCRAPE_MIN_INTERVAL if min_interval is None else min_interval,
        sleep=sleep,
    )
    retries = SCRAPE_MAX_RETRIES if max_retries is None else max_retries
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
            payload = _get_json(client, url, params, limiter, max_retries=retries)
            page = payload.get("articles") or []
            reached_watermark = False
            for item in page:
                if item.get("draft"):
                    continue
                if not (item.get("body") or "").strip():
                    continue
                # Sorted newest-first: first article ≤ watermark means the rest is old.
                if watermark is not None:
                    stamped = parse_zendesk_time(
                        str(item.get("updated_at") or item.get("edited_at") or "")
                    )
                    if stamped is not None and stamped <= watermark:
                        reached_watermark = True
                        break
                articles.append(item)
            if reached_watermark:
                break
            url = payload.get("next_page")
            params = None
            if url:
                log.info("scrape   %s articles so far", len(articles))
    except httpx.HTTPError as exc:
        raise ScrapeError(f"Zendesk Help Center request failed: {exc}") from exc
    finally:
        if own_client:
            client.close()

    if watermark is None and len(articles) < min_articles:
        raise ScrapeError(
            f"Only fetched {len(articles)} published articles; need at least {min_articles}."
        )
    return articles
