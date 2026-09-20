"""Turn Zendesk article HTML into clean Markdown."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

from harbor.config import HELP_CENTER_ORIGIN

JUNK_SELECTORS = (
    "script",
    "style",
    "noscript",
    "iframe",
    "form",
    "nav",
    "aside",
    ".article-votes",
    ".article-subscribe",
    ".related-articles",
    ".breadcrumbs",
    ".share",
    ".sidenav",
    ".sub-nav",
)

_SLUG_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")
_DATA_URI = re.compile(
    r"!\[[^\]]*\]\(data:[^)]+\)|data:image/[a-zA-Z0-9+.-]+;base64,[A-Za-z0-9+/=\s]+",
    re.DOTALL,
)
_FILENAME_ALT = re.compile(
    r"(?i)^[\w\s()\[\].,+-]+\.(png|jpe?g|gif|webp|svg|bmp|ico)$"
)
_MARKDOWN_FILENAME_ALT = re.compile(
    r"!\[(?:[^\]]*\.(?:png|jpe?g|gif|webp|svg|bmp|ico))\]",
    re.IGNORECASE,
)


class ArticleConverter(MarkdownConverter):
    """ATX headings, fenced code, lists. In-page hash links stay relative."""

    def convert_pre(self, el, text, parent_tags=None, **kwargs):  # type: ignore[override]
        code = el.find("code") if isinstance(el, Tag) else None
        body = (code.get_text() if code else el.get_text()).strip("\n")
        lang = _code_language(code)
        return f"\n\n```{lang}\n{body}\n```\n\n"

    def convert_img(self, el, text, parent_tags=None, **kwargs):  # type: ignore[override]
        src = (el.get("src") or "").strip()
        alt = _image_alt(el)
        if src.startswith("data:"):
            return f"\n\n[{alt}]\n\n"
        if not src:
            return f"\n\n[{alt}]\n\n"
        return f"\n\n![{alt}]({src})\n\n"


def _image_alt(el: Tag) -> str:
    for key in ("alt", "title"):
        value = (el.get(key) or "").strip()
        if value and not _FILENAME_ALT.match(value):
            return value
    return "image"


def _code_language(code: Tag | None) -> str:
    if code is None:
        return ""
    for cls in code.get("class") or []:
        if cls.startswith("language-"):
            return cls.split("language-", 1)[1]
        if cls.startswith("lang-"):
            return cls.split("lang-", 1)[1]
    return ""


def normalize_url(value: str, *, keep_hash_relative: bool = True) -> str:
    href = (value or "").strip()
    if not href:
        return href
    if href.startswith(("mailto:", "tel:", "data:")):
        return href
    if keep_hash_relative and href.startswith("#"):
        return href
    if href.startswith("//"):
        return "https:" + href
    parsed = urlparse(href)
    if parsed.scheme:
        return href
    return urljoin(HELP_CENTER_ORIGIN + "/", href.lstrip("/"))


def clean_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "lxml")
    for selector in JUNK_SELECTORS:
        for node in soup.select(selector):
            node.decompose()

    for tag in soup.find_all("a", href=True):
        tag["href"] = normalize_url(tag["href"])
    for tag in soup.find_all("img", src=True):
        tag["src"] = normalize_url(tag["src"], keep_hash_relative=False)

    for span in list(soup.find_all("span")):
        if not isinstance(span, Tag):
            continue
        has_media = span.find(["img", "video", "svg"]) is not None
        if not span.get_text(strip=True) and not has_media:
            span.decompose()
            continue
        extra = set(span.attrs) - {"style", "class", "id"}
        if not extra:
            span.unwrap()
    return soup


def html_to_markdown(html: str) -> str:
    soup = clean_html(html)
    markdown = ArticleConverter(
        heading_style="ATX",
        bullets="-",
        strip=["script", "style"],
        escape_asterisks=False,
        escape_underscores=False,
    ).convert_soup(soup)
    markdown = _DATA_URI.sub("[embedded-image]", markdown or "")
    markdown = _MARKDOWN_FILENAME_ALT.sub("![image]", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
    return markdown


def slug_for(article: dict[str, Any]) -> str:
    url = article.get("html_url") or ""
    tail = urlparse(url).path.rstrip("/").split("/")[-1]
    slug = _SLUG_SAFE.sub("-", tail).strip("-.")
    return slug or str(article["id"])


def article_to_markdown(article: dict[str, Any]) -> str:
    title = (article.get("title") or article.get("name") or "Untitled").strip()
    html_url = article.get("html_url") or ""
    body = html_to_markdown(article.get("body") or "")
    labels = ", ".join(article.get("label_names") or [])
    lines = [
        f"# {title}",
        "",
        f"Article URL: {html_url}",
        f"Article ID: {article.get('id')}",
        f"Updated: {article.get('updated_at') or article.get('edited_at') or ''}",
    ]
    if labels:
        lines.append(f"Labels: {labels}")
    lines.extend(["", body, ""])
    return "\n".join(lines)
