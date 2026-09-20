from pathlib import Path

import pytest

from harbor.catalog import (
    ArticleRecord,
    Catalog,
    sha256_text,
    write_markdown,
    write_markdown_if_changed,
)
from harbor.pipeline import remove_by_hints, run
from harbor.uploader import estimate_chunks


def _record(article_id: str, text: str, slug: str | None = None) -> ArticleRecord:
    slug = slug or article_id
    return ArticleRecord(
        article_id=article_id,
        slug=slug,
        content_hash=sha256_text(text),
        updated_at="2026-01-01T00:00:00Z",
        html_url=f"https://support.optisigns.com/hc/en-us/articles/{slug}",
        path=f"{slug}.md",
    )


def test_delta_added_updated_skipped():
    first = _record("1", "hello")
    first.openai_file_id = "file-old"
    catalog = Catalog(articles={"1": first})
    current = [
        _record("1", "hello"),
        _record("2", "brand new"),
    ]
    delta = catalog.diff(current)
    assert [r.article_id for r in delta.skipped] == ["1"]
    assert [r.article_id for r in delta.added] == ["2"]
    assert delta.updated == []

    current[0] = _record("1", "changed")
    delta = catalog.diff(current)
    assert [r.article_id for r in delta.updated] == ["1"]
    assert delta.updated[0].openai_file_id == "file-old"
    assert [r.article_id for r in delta.added] == ["2"]
    assert delta.removed == []


def test_delta_removed_when_article_missing():
    catalog = Catalog(
        articles={
            "1": _record("1", "keep"),
            "2": _record("2", "gone"),
        }
    )
    catalog.articles["1"].openai_file_id = "doc-1"
    catalog.articles["2"].openai_file_id = "doc-2"
    delta = catalog.diff([_record("1", "keep")])
    assert [r.article_id for r in delta.skipped] == ["1"]
    assert [r.article_id for r in delta.removed] == ["2"]
    assert delta.removed[0].openai_file_id == "doc-2"


def test_lookup_id_slug_and_filename():
    rec = _record("9", "body", slug="9-nine")
    catalog = Catalog(articles={"9": rec})
    assert catalog.lookup("9") is rec
    assert catalog.lookup("9-nine") is rec
    assert catalog.lookup("9-nine.md") is rec
    assert catalog.lookup(r"data\articles\9-nine.md") is rec
    assert catalog.lookup("missing") is None


def test_purge_deletes_markdown_and_catalog_row(tmp_path: Path):
    path = write_markdown("gone", "# x\n", directory=tmp_path)
    rec = _record("1", "# x\n", slug="gone")
    rec.path = str(path)
    catalog = Catalog(articles={"1": rec})
    dropped = catalog.purge([rec])
    assert dropped == ["gone"]
    assert not path.exists()
    assert "1" not in catalog.articles


def test_remove_rejects_scrape_flags():
    with pytest.raises(ValueError, match="--remove"):
        run(remove=["1"], full=True)


def test_remove_by_hints_drops_file(tmp_path: Path, monkeypatch):
    from harbor import catalog as catalog_mod
    from harbor import pipeline as pipeline_mod

    monkeypatch.setattr(catalog_mod, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(catalog_mod, "ARTICLES_DIR", tmp_path)
    monkeypatch.setattr(pipeline_mod, "ARTICLES_DIR", tmp_path)
    monkeypatch.setattr(pipeline_mod, "LOG_DIR", tmp_path)
    monkeypatch.setattr(pipeline_mod, "LAST_RUN_PATH", tmp_path / "last-run.json")

    path = write_markdown("gone", "# x\n", directory=tmp_path)
    rec = _record("1", "# x\n", slug="gone")
    rec.path = str(path)
    catalog = Catalog(articles={"1": rec})
    summary = remove_by_hints(["gone.md"], catalog=catalog)
    assert summary["removed"] == 1
    assert summary["removed_slugs"] == ["gone"]
    assert not path.exists()
    assert "1" not in catalog.articles


def test_remove_unknown_hint():
    with pytest.raises(ValueError, match="Unknown"):
        remove_by_hints(["no-such-article"], catalog=Catalog())


def test_never_uploaded_hash_is_added_not_skipped():
    catalog = Catalog(articles={"1": _record("1", "hello")})
    delta = catalog.diff([_record("1", "hello")])
    assert [r.article_id for r in delta.added] == ["1"]
    assert delta.skipped == []


def test_catalog_roundtrip(tmp_path: Path):
    path = tmp_path / "state.json"
    catalog = Catalog(vector_store_id="vs_123")
    catalog.upsert(_record("9", "body", slug="nine"))
    catalog.save(path)
    loaded = Catalog.load(path)
    assert loaded.vector_store_id is None
    assert loaded.articles["9"].openai_file_id is None
    assert loaded.articles["9"].content_hash == sha256_text("body")


def test_catalog_keeps_gemini_store_id(tmp_path: Path):
    path = tmp_path / "state.json"
    catalog = Catalog(vector_store_id="fileSearchStores/abc")
    rec = _record("9", "body", slug="nine")
    rec.openai_file_id = "fileSearchStores/abc/documents/xyz"
    catalog.upsert(rec)
    catalog.save(path)
    loaded = Catalog.load(path)
    assert loaded.vector_store_id == "fileSearchStores/abc"
    assert loaded.articles["9"].openai_file_id == "fileSearchStores/abc/documents/xyz"


def test_write_markdown(tmp_path: Path):
    path = write_markdown("hello-world", "# Hello\n", directory=tmp_path)
    assert path.name == "hello-world.md"
    assert path.read_text(encoding="utf-8").startswith("# Hello")


def test_write_markdown_if_changed(tmp_path: Path):
    path, changed = write_markdown_if_changed("same", "# Hi\n", directory=tmp_path)
    assert changed is True
    again, changed_again = write_markdown_if_changed("same", "# Hi\n", directory=tmp_path)
    assert again == path
    assert changed_again is False


def test_catalog_persists_scrape_watermark(tmp_path: Path):
    path = tmp_path / "state.json"
    catalog = Catalog(scrape_watermark="2026-09-19T17:56:30Z")
    catalog.upsert(_record("1", "hello"))
    catalog.save(path)
    loaded = Catalog.load(path)
    assert loaded.scrape_watermark == "2026-09-19T17:56:30Z"


def test_estimate_chunks_short_and_long():
    assert estimate_chunks("abcd", chunk_size=800, overlap=400) == 1
    huge = "x" * (4 * 2000)
    assert estimate_chunks(huge, chunk_size=800, overlap=400) >= 4
