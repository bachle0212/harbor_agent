from harbor.ask import split_reply, urls_from_hints, urls_from_question
from harbor.catalog import ArticleRecord, Catalog, sha256_text


def test_split_reply_keeps_citations():
    raw = (
        "Paste the YouTube URL.\n"
        "\n"
        "Article URL: https://support.optisigns.com/hc/en-us/articles/360051014713\n"
        "Source: youtube.md\n"
    )
    split = split_reply(raw)
    assert "Paste the YouTube URL." in split["text"]
    assert split["citations"] == [
        "Article URL: https://support.optisigns.com/hc/en-us/articles/360051014713",
    ]
    assert not any(item.startswith("Source:") for item in split["citations"])


def test_urls_from_filename_hint():
    record = ArticleRecord(
        article_id="360016247974",
        slug="360016247974-How-to-Upload-Manage-Your-Files-Assets",
        content_hash=sha256_text("body"),
        updated_at="2026-09-10T09:39:25Z",
        html_url="https://support.optisigns.com/hc/en-us/articles/360016247974-How-to-Upload-Manage-Your-Files-Assets",
        path="360016247974-How-to-Upload-Manage-Your-Files-Assets.md",
    )
    catalog = Catalog(articles={record.article_id: record})
    urls = urls_from_hints(
        catalog,
        ["360016247974-How-to-Upload-Manage-Your-Files-Assets.md"],
    )
    assert urls == [record.html_url]
    compact = urls_from_hints(catalog, ["360016247974howtouploadmana-ocyly7whvsk1"])
    assert compact == [record.html_url]
    titled = urls_from_question(catalog, "How to Upload & Manage Your Files/ Assets")
    assert titled == [record.html_url]


def test_website_question_matches_catalog_slug():
    record = ArticleRecord(
        article_id="360016382473",
        slug="360016382473-How-to-Use-the-Website-App-and-Display-URLs-on-OptiSigns",
        content_hash=sha256_text("body"),
        updated_at="2026-09-10T09:39:57Z",
        html_url="https://support.optisigns.com/hc/en-us/articles/360016382473-How-to-Use-the-Website-App-and-Display-URLs-on-OptiSigns",
        path="website.md",
    )
    catalog = Catalog(articles={record.article_id: record})
    urls = urls_from_question(catalog, "How to Use the Website App and Display URLs")
    assert urls == [record.html_url]
