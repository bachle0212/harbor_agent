"""Compact, wrap-safe run logs (no dumped dicts)."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("harbor")

_MAX_SLUGS = 8


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)


def _slugs(summary: dict[str, Any], key: str) -> str:
    items = [str(item) for item in (summary.get(key) or []) if item]
    if not items:
        return ""
    shown = items[:_MAX_SLUGS]
    extra = len(items) - len(shown)
    text = ", ".join(shown)
    if extra:
        text += f" +{extra} more"
    return text


def format_run_report(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    if "fetched" in summary or summary.get("watermark") is not None:
        if summary.get("full"):
            kind = "full"
        elif summary.get("incremental"):
            kind = "incremental"
        elif summary.get("upload_only"):
            kind = "disk"
        else:
            kind = "scrape"
        lines.append(
            "scrape   {kind}  fetched={fetched}  written={written}  watermark={watermark}".format(
                kind=kind,
                fetched=summary.get("fetched", 0),
                written=summary.get("files_written", 0),
                watermark=summary.get("watermark") or "-",
            )
        )
    lines.append(
        "delta    added={added}  updated={updated}  skipped={skipped}  removed={removed}".format(
            added=summary.get("added", 0),
            updated=summary.get("updated", 0),
            skipped=summary.get("skipped", 0),
            removed=summary.get("removed", 0),
        )
    )
    pending = _slugs(summary, "added_slugs")
    if pending:
        label = "pending upload" if summary.get("scrape_only") else "added"
        lines.append(f"         {label}: {pending}")
    updated = _slugs(summary, "updated_slugs")
    if updated:
        lines.append(f"         updated: {updated}")
    removed = _slugs(summary, "removed_slugs")
    if removed:
        lines.append(f"         removed: {removed}")
    flags: list[str] = [f"files={summary.get('files_on_disk', 0)}"]
    if summary.get("scrape_only"):
        flags.append("scrape-only")
    if summary.get("upload_only"):
        flags.append("upload-only")
    if summary.get("files_uploaded") is not None:
        flags.append(f"uploaded={summary.get('files_uploaded')}")
    store = summary.get("vector_store_id") or ""
    if store:
        flags.append(store)
    lines.append("done     " + "  ".join(flags))
    return "\n".join(lines)


def log_run_report(summary: dict[str, Any]) -> None:
    for line in format_run_report(summary).splitlines():
        log.info("%s", line)
