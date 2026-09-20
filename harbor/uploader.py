"""Upload changed Markdown files to a Gemini File Search store via API.

Chunking is `white_space_config` at 512 / 256: Gemini caps `max_tokens_per_chunk`
at 512 and overlap at half the chunk. MIME is `text/plain` because `text/markdown`
is rejected. Only `delta.uploads` (added + updated) go to the API.
"""

from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from google import genai

from harbor.catalog import ArticleRecord, Catalog, Delta
from harbor.config import (
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    EMBEDDING_MODEL,
    api_key,
    persist_vector_store_id,
    vector_store_id,
)

log = logging.getLogger(__name__)

STORE_DISPLAY_NAME = "harbor-support-docs"

CHUNKING_CONFIG: dict[str, Any] = {
    "white_space_config": {
        "max_tokens_per_chunk": CHUNK_SIZE_TOKENS,
        "max_overlap_tokens": CHUNK_OVERLAP_TOKENS,
    }
}


class UploadError(RuntimeError):
    pass


def estimate_chunks(
    text: str,
    *,
    chunk_size: int = CHUNK_SIZE_TOKENS,
    overlap: int = CHUNK_OVERLAP_TOKENS,
) -> int:
    """Match Gemini white-space chunking: ~4 chars/token, overlap ≤ half chunk size."""
    tokens = max(1, math.ceil(len(text) / 4))
    if tokens <= chunk_size:
        return 1
    step = max(1, chunk_size - overlap)
    return 1 + math.ceil((tokens - chunk_size) / step)


def _client() -> genai.Client:
    key = api_key()
    if not key:
        raise UploadError("Missing GEMINI_API_KEY (or GOOGLE_API_KEY / API_KEY).")
    return genai.Client(api_key=key)


def _is_openai_id(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith("vs_") or value.startswith("file-")


def ensure_vector_store(client: genai.Client, catalog: Catalog) -> str:
    store_id = vector_store_id() or catalog.vector_store_id
    if store_id and _is_openai_id(store_id):
        store_id = None
    if store_id:
        client.file_search_stores.get(name=store_id)
        catalog.vector_store_id = store_id
        return store_id
    created = client.file_search_stores.create(
        config={"display_name": STORE_DISPLAY_NAME, "embedding_model": EMBEDDING_MODEL}
    )
    catalog.vector_store_id = created.name
    catalog.save()
    persist_vector_store_id(created.name)
    log.info("created Gemini File Search store %s", created.name)
    return created.name


def _wait_operation(client: genai.Client, operation: Any, *, slug: str) -> Any:
    while not getattr(operation, "done", False):
        time.sleep(2)
        operation = client.operations.get(operation)
    error = getattr(operation, "error", None)
    if error:
        raise UploadError(f"Indexing {slug} failed: {error}")
    return operation


def _document_name(operation: Any) -> str:
    payload = getattr(operation, "response", None) or getattr(operation, "result", None)
    if payload is None:
        return ""
    if isinstance(payload, dict):
        return str(payload.get("document_name") or payload.get("name") or "")
    name = getattr(payload, "document_name", None) or getattr(payload, "name", None)
    return str(name or "")


def _delete_old_file(client: genai.Client, file_id: str | None) -> None:
    if not file_id or _is_openai_id(file_id):
        return
    try:
        client.file_search_stores.documents.delete(name=file_id, config={"force": True})
    except Exception as exc:  # noqa: BLE001 — stale IDs should not abort a delta run
        log.warning("could not delete Gemini document %s: %s", file_id, exc)


def _upload_file(client: genai.Client, store_id: str, record: ArticleRecord) -> str:
    operation = client.file_search_stores.upload_to_file_search_store(
        file=record.path,
        file_search_store_name=store_id,
        config={
            "display_name": f"{record.slug}.md",
            "mime_type": "text/plain",
            "chunking_config": CHUNKING_CONFIG,
        },
    )
    operation = _wait_operation(client, operation, slug=record.slug)
    name = _document_name(operation)
    if not name:
        name = _lookup_document(client, store_id, f"{record.slug}.md")
    if not name:
        raise UploadError(f"Upload of {record.slug} succeeded but returned no document name")
    return name


def _lookup_document(client: genai.Client, store_id: str, display_name: str) -> str:
    for document in client.file_search_stores.documents.list(parent=store_id):
        if getattr(document, "display_name", None) == display_name:
            return str(document.name)
    return ""


def _upload_file_with_retry(
    client: genai.Client, store_id: str, record: ArticleRecord, attempts: int = 5
) -> str:
    delay = 2.0
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _upload_file(client, store_id, record)
        except Exception as exc:  # noqa: BLE001 — retry transient Gemini errors
            last_error = exc
            log.warning("upload %s attempt %s/%s failed: %s", record.slug, attempt, attempts, exc)
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise UploadError(f"Failed to upload {record.slug}: {last_error}") from last_error


def apply_delta(delta: Delta, catalog: Catalog) -> dict[str, Any]:
    """Upload only added/updated files. Returns counts for the run log."""
    client = _client()
    store_id = ensure_vector_store(client, catalog)

    for record in delta.updated:
        _delete_old_file(client, record.openai_file_id)
        record.openai_file_id = None

    new_ids: list[str] = []
    failed: list[str] = []
    estimated = 0
    uploads = list(delta.uploads)
    for record in uploads:
        estimated += estimate_chunks(Path(record.path).read_text(encoding="utf-8"))

    if uploads:
        log.info("uploading %s files to Gemini File Search", len(uploads))
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                pool.submit(_upload_file_with_retry, client, store_id, record): record
                for record in uploads
            }
            done = 0
            failed: list[str] = []
            for future in as_completed(futures):
                record = futures[future]
                try:
                    file_id = future.result()
                except Exception as exc:  # noqa: BLE001 — keep remaining files moving
                    failed.append(record.slug)
                    log.error("giving up on %s: %s", record.slug, exc)
                    continue
                record.openai_file_id = file_id
                new_ids.append(file_id)
                catalog.upsert(record)
                done += 1
                if done % 25 == 0 or done == len(uploads):
                    catalog.save()
                    log.info("uploaded %s/%s files", done, len(uploads))
            if failed:
                log.warning("failed uploads (%s): %s", len(failed), ", ".join(failed[:20]))

    for record in delta.skipped:
        catalog.upsert(record)

    catalog.save()
    persist_vector_store_id(store_id)
    usage_bytes = _usage_bytes(client, store_id)
    return {
        "vector_store_id": store_id,
        "files_uploaded": len(new_ids),
        "estimated_chunks_uploaded": estimated,
        "batch_status": "completed" if new_ids else None,
        "store_usage_bytes": usage_bytes,
        "chunking": {
            "type": "white_space",
            "static": {
                "max_chunk_size_tokens": CHUNK_SIZE_TOKENS,
                "chunk_overlap_tokens": CHUNK_OVERLAP_TOKENS,
            },
        },
        "provider": "gemini",
        "upload_failures": failed,
    }


def _usage_bytes(client: genai.Client, store_id: str) -> int:
    store = client.file_search_stores.get(name=store_id)
    for attr in ("size_bytes", "total_size_bytes", "usage_bytes"):
        value = getattr(store, attr, None)
        if value:
            return int(value)
    return 0


def hydrate_catalog_from_store(store_id: str, catalog: Catalog | None = None) -> dict[str, int]:
    """Map existing File Search documents back onto the local catalog by display name."""
    client = _client()
    catalog = catalog or Catalog.load()
    catalog.vector_store_id = store_id
    persist_vector_store_id(store_id)
    by_slug = {record.slug: record for record in catalog.articles.values()}
    mapped = 0
    listed = 0
    for document in client.file_search_stores.documents.list(parent=store_id):
        listed += 1
        display = (getattr(document, "display_name", None) or "").removesuffix(".md")
        record = by_slug.get(display)
        if record is None:
            continue
        record.openai_file_id = str(document.name)
        catalog.upsert(record)
        mapped += 1
    catalog.save()
    usage = _usage_bytes(client, store_id)
    log.info("hydrated catalog from %s: listed=%s mapped=%s usage_bytes=%s", store_id, listed, mapped, usage)
    return {"listed": listed, "mapped": mapped, "store_usage_bytes": usage}
