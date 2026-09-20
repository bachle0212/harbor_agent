"""Ask the Gemini File Search assistant a question (sanity check)."""

from __future__ import annotations

import argparse
import re
import sys

from google.genai import types

from harbor.catalog import Catalog
from harbor.config import GEMINI_MODEL, SYSTEM_PROMPT, api_key, vector_store_id
from harbor.uploader import UploadError, _client, ensure_vector_store

_ARTICLE_URL = re.compile(
    r"https://support\.optisigns\.com/hc/[^/\s)]+/articles/\d+[^\s)\]\"']*",
    re.IGNORECASE,
)


def split_reply(text: str) -> dict[str, object]:
    body: list[str] = []
    citations: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        if line.startswith("Source:"):
            continue
        if line.startswith("Article URL:"):
            url = line.split("Article URL:", 1)[1].strip()
            if url and url not in seen:
                seen.add(url)
                citations.append(f"Article URL: {url}")
            continue
        body.append(line)
        for url in _ARTICLE_URL.findall(line):
            if url not in seen:
                seen.add(url)
                citations.append(f"Article URL: {url}")
    return {"text": "\n".join(body).strip(), "citations": citations}


def urls_from_hints(catalog: Catalog, hints: list[str]) -> list[str]:
    """Map Gemini file names / document ids back to Help Center URLs."""
    by_id = catalog.articles
    by_slug = {record.slug.lower(): record for record in by_id.values()}
    urls: list[str] = []
    for hint in hints:
        raw = (hint or "").strip()
        if raw.startswith("http"):
            if raw not in urls:
                urls.append(raw)
            if len(urls) >= 3:
                break
            continue
        key = raw.split("/")[-1].removesuffix(".md").strip().lower()
        record = by_slug.get(key)
        if record is None:
            digits = []
            for char in key:
                if char.isdigit():
                    digits.append(char)
                elif digits:
                    break
            record = by_id.get("".join(digits))
        url = (record.html_url if record else "").strip()
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= 3:
            break
    return urls


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def urls_from_question(catalog: Catalog, question: str) -> list[str]:
    """Match a title-like question to slugs when Gemini cites no URL."""
    compact = _compact(question)
    tokens = {tok for tok in re.findall(r"[a-z]{4,}", question.lower())}
    scored: list[tuple[int, str]] = []
    for record in catalog.articles.values():
        if not record.html_url:
            continue
        slug = _compact(record.slug)
        tail = _compact(record.html_url.rsplit("/", 1)[-1])
        if compact and len(compact) >= 12 and (compact in slug or compact in tail):
            scored.append((100 + len(compact), record.html_url))
            continue
        overlap = tokens & set(re.findall(r"[a-z]{4,}", record.slug.lower()))
        if len(overlap) >= 3:
            scored.append((len(overlap), record.html_url))
    scored.sort(key=lambda item: item[0], reverse=True)
    found: list[str] = []
    for _, url in scored:
        if url not in found:
            found.append(url)
        if len(found) >= 3:
            break
    return found


def ensure_citations(text: str, catalog: Catalog, question: str, hints: list[str] | None = None) -> str:
    reply = _attach_urls(text, urls_from_hints(catalog, hints or []))
    if not split_reply(reply)["citations"]:
        reply = _attach_urls(reply, urls_from_question(catalog, question))
    return reply


def _attach_urls(text: str, urls: list[str]) -> str:
    existing = {line.split("Article URL:", 1)[1].strip() for line in text.splitlines() if line.startswith("Article URL:")}
    extra = [url for url in urls if url not in existing]
    if not extra:
        return text
    lines = [text.rstrip()]
    for url in extra[: max(0, 3 - len(existing))]:
        lines.append(f"Article URL: {url}")
    return "\n".join(lines).strip()


def ask(question: str) -> str:
    client = _client()
    catalog = Catalog.load()
    store_id = vector_store_id() or catalog.vector_store_id
    if not store_id:
        store_id = ensure_vector_store(client, catalog)

    try:
        reply = _ask_interactions(client, catalog, store_id, question)
    except Exception as interaction_error:  # noqa: BLE001
        print(f"interactions failed ({interaction_error}); trying generate_content", file=sys.stderr)
        reply = _ask_generate(client, catalog, store_id, question)
    return ensure_citations(reply, catalog, question)


def _ask_generate(client, catalog: Catalog, store_id: str, question: str) -> str:
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[
                types.Tool(
                    file_search=types.FileSearch(file_search_store_names=[store_id])
                )
            ],
        ),
    )
    text = (getattr(response, "text", None) or "").strip()
    if not text:
        raise UploadError("Empty Gemini generate_content reply")
    hints: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        grounding = getattr(candidate, "grounding_metadata", None)
        for chunk in getattr(grounding, "grounding_chunks", None) or []:
            context = getattr(chunk, "retrieved_context", None)
            if context is None:
                continue
            for attr in ("uri", "title", "name"):
                value = getattr(context, attr, None)
                if value:
                    hints.append(str(value))
    return ensure_citations(text, catalog, question, hints)


def _ask_interactions(client, catalog: Catalog, store_id: str, question: str) -> str:
    interaction = client.interactions.create(
        model=GEMINI_MODEL,
        input=question,
        system_instruction=SYSTEM_PROMPT,
        tools=[{"type": "file_search", "file_search_store_names": [store_id]}],
    )
    chunks: list[str] = []
    hints: list[str] = []
    for step in getattr(interaction, "steps", None) or []:
        if getattr(step, "type", None) != "model_output":
            continue
        for block in getattr(step, "content", None) or []:
            if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                chunks.append(block.text)
                for annotation in getattr(block, "annotations", None) or []:
                    if getattr(annotation, "type", None) != "file_citation":
                        continue
                    source = (getattr(annotation, "source", None) or "").strip()
                    file_name = (getattr(annotation, "file_name", None) or "").strip()
                    if source.startswith("http"):
                        chunks.append(f"Article URL: {source}")
                    elif file_name:
                        hints.append(file_name)
                    elif source:
                        hints.append(source)
    text = "\n".join(chunks).strip()
    if not text:
        raise UploadError("Empty Gemini interactions reply")
    seen: set[str] = set()
    unique: list[str] = []
    for line in text.splitlines():
        if line.startswith("Source:"):
            continue
        if line.startswith("Article URL:"):
            if not line.split("Article URL:", 1)[1].strip():
                continue
            if line in seen or sum(1 for item in unique if item.startswith("Article URL:")) >= 3:
                continue
            seen.add(line)
        unique.append(line)
    return ensure_citations("\n".join(unique).strip(), catalog, question, hints)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query the uploaded support docs.")
    parser.add_argument("question", nargs="*", default=["How do I add a YouTube video?"])
    parser.add_argument("--ui", action="store_true", help="Open the local Harbor desk in a browser.")
    parser.add_argument("--repl", action="store_true", help="Ask in the terminal, one question at a time.")
    args = parser.parse_args(argv)
    if args.ui or args.repl:
        from harbor.console import main as console_main

        extra = ["--repl"] if args.repl else []
        return console_main(extra)
    question = " ".join(args.question).strip()
    if not api_key():
        print("Missing GEMINI_API_KEY (or GOOGLE_API_KEY / API_KEY).", file=sys.stderr)
        return 1
    print(ask(question))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
