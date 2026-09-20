#!/usr/bin/env python3
"""Daily job entrypoint: scrape, detect deltas, upload, exit 0 on success."""

from __future__ import annotations

import argparse
import logging
import sys

from harbor.pipeline import run
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
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        summary = run(scrape_only=args.scrape_only, upload_only=args.upload_only, full=args.full)
    except (ScrapeError, UploadError, ValueError) as exc:
        logging.error("%s", exc)
        return 1

    print(
        "added={added} updated={updated} skipped={skipped} files_on_disk={files_on_disk}".format(
            **summary
        )
    )
    if summary.get("files_uploaded") is not None:
        print(
            "uploaded={files_uploaded} estimated_chunks_uploaded={estimated_chunks_uploaded} "
            "vector_store={vector_store_id}".format(**{**{"estimated_chunks_uploaded": 0, "vector_store_id": ""}, **summary})
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
