"""Local article catalog: content hashes decide added / updated / skipped."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from harbor.config import ARTICLES_DIR, STATE_PATH


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class ArticleRecord:
    article_id: str
    slug: str
    content_hash: str
    updated_at: str
    html_url: str
    path: str
    openai_file_id: str | None = None


@dataclass
class Delta:
    added: list[ArticleRecord] = field(default_factory=list)
    updated: list[ArticleRecord] = field(default_factory=list)
    skipped: list[ArticleRecord] = field(default_factory=list)

    @property
    def uploads(self) -> list[ArticleRecord]:
        return [*self.added, *self.updated]


@dataclass
class Catalog:
    vector_store_id: str | None = None
    scrape_watermark: str | None = None
    articles: dict[str, ArticleRecord] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path = STATE_PATH) -> Catalog:
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        articles = {}
        for key, value in (raw.get("articles") or {}).items():
            allowed = {field.name for field in ArticleRecord.__dataclass_fields__.values()}
            record = ArticleRecord(**{k: v for k, v in value.items() if k in allowed})
            articles[key] = record
        store_id = raw.get("vector_store_id")
        # Previous OpenAI runs stored vs_/file- ids; Gemini needs a fresh store.
        if store_id and (str(store_id).startswith("vs_") or str(store_id).startswith("file-")):
            store_id = None
            for record in articles.values():
                record.openai_file_id = None
        watermark = (raw.get("scrape_watermark") or "").strip() or None
        if watermark is None:
            stamps = [record.updated_at for record in articles.values() if record.updated_at]
            watermark = max(stamps) if stamps else None
        return cls(vector_store_id=store_id, scrape_watermark=watermark, articles=articles)

    def save(self, path: Path | None = None) -> None:
        path = path or STATE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "vector_store_id": self.vector_store_id,
            "scrape_watermark": self.scrape_watermark,
            "articles": {key: asdict(record) for key, record in self.articles.items()},
        }
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    def diff(self, current: list[ArticleRecord]) -> Delta:
        delta = Delta()
        for record in current:
            previous = self.articles.get(record.article_id)
            if previous is None:
                delta.added.append(record)
            elif previous.content_hash != record.content_hash:
                record.openai_file_id = previous.openai_file_id
                delta.updated.append(record)
            elif not previous.openai_file_id:
                # Scraped before, never uploaded — treat as added.
                delta.added.append(record)
            else:
                record.openai_file_id = previous.openai_file_id
                delta.skipped.append(record)
        return delta

    def upsert(self, record: ArticleRecord) -> None:
        self.articles[record.article_id] = record


def write_markdown(slug: str, markdown: str, *, directory: Path = ARTICLES_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slug}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def write_markdown_if_changed(
    slug: str, markdown: str, *, directory: Path = ARTICLES_DIR
) -> tuple[Path, bool]:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slug}.md"
    incoming = sha256_text(markdown)
    if path.exists() and sha256_text(path.read_text(encoding="utf-8")) == incoming:
        return path, False
    path.write_text(markdown, encoding="utf-8")
    return path, True


def record_from_article(
    article: dict[str, Any],
    markdown: str,
    path: Path,
) -> ArticleRecord:
    return ArticleRecord(
        article_id=str(article["id"]),
        slug=path.stem,
        content_hash=sha256_text(markdown),
        updated_at=str(article.get("updated_at") or article.get("edited_at") or ""),
        html_url=str(article.get("html_url") or ""),
        path=str(path),
    )
