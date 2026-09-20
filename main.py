#!/usr/bin/env python3
"""Daily job entrypoint: scrape, detect deltas, upload, exit 0 on success."""

from __future__ import annotations

import argparse
import logging

from harbor.pipeline import run
from harbor.report import configure_logging
from harbor.uploader import UploadError
from harbor.scraper import ScrapeError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape Help Center docs and sync a vector store.")
    parser.add_argument("--scrape-only", action="store_true", help="Write Markdown; skip Gemini upload.")
    parser.add_argument("--upload-only", action="store_true", help="Upload existing Markdown; skip scrape.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Ignore the updated_at watermark and scrape every published article.",
    )
    parser.add_argument(
        "--remove",
        nargs="+",
        metavar="ID",
        help="Delete article(s) from disk, catalog, and File Search (id, slug, or .md name).",
    )
    args = parser.parse_args(argv)

    configure_logging()
    try:
        run(
            scrape_only=args.scrape_only,
            upload_only=args.upload_only,
            full=args.full,
            remove=args.remove,
        )
    except (ScrapeError, UploadError, ValueError) as exc:
        logging.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
