"""Daily job: scrape → clean Markdown → SHA-256 delta → Gemini upload → exit 0."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harbor.catalog import (
    ArticleRecord,
    Catalog,
    Delta,
    record_from_article,
    sha256_text,
    write_markdown_if_changed,
)
from harbor.config import ARTICLES_DIR, LAST_RUN_PATH, LOG_DIR, MIN_ARTICLES, persist_vector_store_id
from harbor.convert import article_to_markdown, slug_for
from harbor.scraper import fetch_articles, newest_timestamp
from harbor.uploader import apply_delta, estimate_chunks

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def scrape_to_disk(
    catalog: Catalog,
    *,
    min_articles: int = MIN_ARTICLES,
    full: bool = False,
) -> tuple[list[ArticleRecord], int, dict[str, Any]]:
    catalog_count = len(catalog.articles)
    # First run (or --full, or catalog below the assignment's 30-article floor)
    # walks every published page. Later runs only fetch articles newer than
    # scrape_watermark, then merge them into the existing catalog.
    watermark = None if full or catalog_count < min_articles else catalog.scrape_watermark
    incremental = watermark is not None
    articles = fetch_articles(
        min_articles=min_articles,
        updated_after=watermark,
    )

    fetched: list[ArticleRecord] = []
    written = 0
    for article in articles:
        markdown = article_to_markdown(article)
        path, changed = write_markdown_if_changed(
            slug_for(article), markdown, directory=ARTICLES_DIR
        )
        written += int(changed)
        fetched.append(record_from_article(article, markdown, path))

    if incremental:
        # Watermarked fetch is a prefix of the catalog, not a replacement.
        by_id = {record.article_id: record for record in catalog.articles.values()}
        for record in fetched:
            by_id[record.article_id] = record
        current = list(by_id.values())
    else:
        current = fetched

    catalog.scrape_watermark = newest_timestamp(
        [record.updated_at for record in current if record.updated_at]
    ) or catalog.scrape_watermark

    estimated_all = sum(
        estimate_chunks(Path(record.path).read_text(encoding="utf-8"))
        for record in fetched
        if Path(record.path).exists()
    )
    stats = {
        "incremental": incremental,
        "watermark": watermark,
        "fetched": len(fetched),
        "files_written": written,
    }
    log.info(
        "scrape fetched=%s written=%s incremental=%s watermark=%s estimated_chunks=%s",
        len(fetched),
        written,
        incremental,
        watermark,
        estimated_all,
    )
    return current, estimated_all, stats


def records_from_disk(catalog: Catalog) -> list[ArticleRecord]:
    by_slug = {record.slug: record for record in catalog.articles.values()}
    current: list[ArticleRecord] = []
    for path in sorted(ARTICLES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        previous = by_slug.get(path.stem)
        current.append(
            ArticleRecord(
                article_id=previous.article_id if previous else path.stem,
                slug=path.stem,
                content_hash=sha256_text(text),
                updated_at=previous.updated_at if previous else "",
                html_url=previous.html_url if previous else "",
                path=str(path),
                openai_file_id=previous.openai_file_id if previous else None,
            )
        )
    return current


def write_last_run(payload: dict[str, Any]) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LAST_RUN_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return LAST_RUN_PATH


def run(*, scrape_only: bool = False, upload_only: bool = False, full: bool = False) -> dict[str, Any]:
    if upload_only and scrape_only:
        raise ValueError("Choose at most one of --scrape-only / --upload-only")
    if upload_only and full:
        raise ValueError("--full cannot be combined with --upload-only")

    catalog = Catalog.load()
    estimated_all = 0
    scrape_stats: dict[str, Any] = {}

    if upload_only:
        current = records_from_disk(catalog)
        files_on_disk = len(current)
    else:
        current, estimated_all, scrape_stats = scrape_to_disk(catalog, full=full)
        files_on_disk = len(list(ARTICLES_DIR.glob("*.md"))) if ARTICLES_DIR.exists() else len(current)

    # Hash compare happens after scrape (or --upload-only disk read). Unchanged
    # bodies are skipped even if Zendesk bumped updated_at.
    delta: Delta = catalog.diff(current)
    log.info(
        "delta added=%s updated=%s skipped=%s",
        len(delta.added),
        len(delta.updated),
        len(delta.skipped),
    )

    upload_stats: dict[str, Any] = {}
    if scrape_only:
        for record in [*delta.added, *delta.updated, *delta.skipped]:
            previous = catalog.articles.get(record.article_id)
            if previous:
                record.openai_file_id = previous.openai_file_id
            catalog.upsert(record)
    else:
        try:
            upload_stats = apply_delta(delta, catalog)
            if upload_stats.get("vector_store_id"):
                persist_vector_store_id(str(upload_stats["vector_store_id"]))
        finally:
            catalog.save()

    catalog.save()
    summary = {
        "ran_at": _now(),
        "files_on_disk": files_on_disk,
        "estimated_chunks_on_disk": estimated_all,
        "added": len(delta.added),
        "updated": len(delta.updated),
        "skipped": len(delta.skipped),
        **upload_stats,
        "scrape_only": scrape_only,
        "upload_only": upload_only,
        "full": full,
        **scrape_stats,
    }
    write_last_run(summary)
    log.info("run complete: %s", summary)
    return summary
