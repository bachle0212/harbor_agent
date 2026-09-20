from harbor.convert import article_to_markdown, html_to_markdown, normalize_url, slug_for


SAMPLE_HTML = """
<nav class="sub-nav">Ignore me</nav>
<aside class="related-articles">Ads and related</aside>
<h2 id="add-video">Add a YouTube video</h2>
<p>See the <a href="#add-video">in-page jump</a> and the
<a href="/hc/en-us/articles/123-other">other article</a>.</p>
<pre><code class="language-bash">curl https://example.com</code></pre>
<script>alert("ads")</script>
"""


def test_html_to_markdown_drops_filename_image_alts():
    md = html_to_markdown(
        '<p>Step</p>'
        '<img alt="firefox_0SsesYq2vw(1).png" '
        'src="https://support.optisigns.com/hc/article_attachments/123">'
        '<img alt="T2aDfvelcX.png" '
        'src="https://support.optisigns.com/hc/article_attachments/456">'
        '<img alt="Settings page" '
        'src="https://support.optisigns.com/hc/article_attachments/789">'
    )
    assert "firefox_0SsesYq2vw" not in md
    assert "T2aDfvelcX.png" not in md
    assert "![image](https://support.optisigns.com/hc/article_attachments/123)" in md
    assert "![Settings page](https://support.optisigns.com/hc/article_attachments/789)" in md


def test_html_to_markdown_strips_data_uri_images():
    md = html_to_markdown(
        '<p>Photo</p><img alt="chart" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==">'
    )
    assert "base64" not in md
    assert "data:image" not in md
    assert "chart" in md or "embedded-image" in md


def test_html_to_markdown_strips_nav_and_keeps_structure():
    md = html_to_markdown(SAMPLE_HTML)
    assert "Ignore me" not in md
    assert "Ads and related" not in md
    assert "alert(" not in md
    assert md.startswith("## Add a YouTube video")
    assert "[in-page jump](#add-video)" in md
    assert "https://support.optisigns.com/hc/en-us/articles/123-other" in md
    assert "```" in md
    assert "curl https://example.com" in md


def test_article_markdown_includes_article_url_line():
    md = article_to_markdown(
        {
            "id": 99,
            "title": "Add YouTube",
            "html_url": "https://support.optisigns.com/hc/en-us/articles/99-Add-YouTube",
            "updated_at": "2026-01-01T00:00:00Z",
            "body": "<h3>Go to Apps</h3><p>Pick YouTube.</p>",
            "label_names": ["youtube"],
        }
    )
    assert md.splitlines()[0] == "# Add YouTube"
    assert "Article URL: https://support.optisigns.com/hc/en-us/articles/99-Add-YouTube" in md
    assert "Labels: youtube" in md
    assert "### Go to Apps" in md


def test_slug_from_html_url():
    slug = slug_for(
        {
            "id": 1,
            "html_url": "https://support.optisigns.com/hc/en-us/articles/554-Connect-SharePoint-News",
        }
    )
    assert slug == "554-Connect-SharePoint-News"


def test_hash_links_stay_relative():
    assert normalize_url("#WhatYoullNeed") == "#WhatYoullNeed"
