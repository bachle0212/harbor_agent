from harbor.report import format_run_report


def test_format_scrape_only_pending_upload():
    text = format_run_report(
        {
            "fetched": 0,
            "files_written": 0,
            "incremental": True,
            "watermark": "2026-09-18T20:09:38Z",
            "added": 1,
            "updated": 0,
            "skipped": 408,
            "removed": 0,
            "added_slugs": ["360016174554-Amazon-Firestick"],
            "scrape_only": True,
            "files_on_disk": 409,
        }
    )
    assert "scrape   incremental  fetched=0  written=0" in text
    assert "delta    added=1  updated=0  skipped=408  removed=0" in text
    assert "pending upload: 360016174554-Amazon-Firestick" in text
    assert "done     files=409  scrape-only" in text
    assert "{" not in text


def test_format_remove():
    text = format_run_report(
        {
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "removed": 1,
            "removed_slugs": ["360016174554-Amazon-Firestick"],
            "files_on_disk": 408,
        }
    )
    assert "scrape" not in text
    assert "removed: 360016174554-Amazon-Firestick" in text
    assert "done     files=408" in text
