# Harbor KB

Help Center ingest: scrape → clean Markdown → Gemini File Search (API only).

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
copy .env.sample .env
```

Set `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey).

## Tests

No Gemini/Zendesk calls (scraper is mocked). From the repo root:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m pytest tests/test_convert.py
```

| File | Cases |
|---|---|
| `tests/test_convert.py` | Strip nav/scripts; keep ATX headings, `#` jumps, fenced code; `Article URL:` line; drop filename image alts and `data:` URIs |
| `tests/test_scraper.py` | Skip drafts/empty; paginate; fail below 30 articles on a full scrape; stop at `updated_at` watermark |
| `tests/test_catalog.py` | SHA-256 delta `added` / `updated` / `skipped`; persist Gemini store id + watermark; skip rewrite when Markdown is unchanged |
| `tests/test_ask.py` | Keep `Article URL:` cites, drop `Source:`; map Gemini file names / titles back to Help Center URLs |

## 0. Warm-up

Free Gemini key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

## 1. Scrape ⇒ Markdown

Public Zendesk Help Center API, published articles only. HTML cleaned (nav/ads/scripts removed); headings, relative `#` links, and code blocks kept. Each file is `<slug>.md` with an `Article URL:` line.

```powershell
.\.venv\Scripts\python main.py --scrape-only
```

Output: `data/articles/` (409 files, ≥30 required).

## 2. Assistant + vector store (API upload)

Create the assistant in [AI Studio](https://aistudio.google.com) with this system prompt:

> You are a customer-support assistant for the uploaded Help Center docs.
> • Tone: helpful, factual, concise.
> • Only answer using the uploaded docs.
> • Max 5 bullet points; else link to the doc.
> • Cite up to 3 "Article URL:" lines per reply.

Enable **File Search**. Upload is API-only (no UI drag-and-drop):

```powershell
.\.venv\Scripts\python main.py
.\.venv\Scripts\python -m harbor.ask "How do I add a YouTube video?"
.\.venv\Scripts\python -m harbor.console
```

Local desk: [http://127.0.0.1:8765](http://127.0.0.1:8765) (`--repl` for a terminal prompt).

Attach the printed store id (`fileSearchStores/...`). **Chunking:** Gemini `white_space_config`, **512 tokens / 256 overlap** (API max is 512). Logs print file count and estimated chunks (~4 chars/token).

**Screenshot:** ask *How do I add a YouTube video?* in AI Studio; save citations as `docs/assistant-youtube.png`.

![Assistant answering “How do I add a YouTube video?”](docs/assistant-youtube.png)

## 3. Daily job

`main.py` re-scrapes (stops at the last `updated_at` watermark unless `--full`), SHA-256 diffs, uploads only added/updated files, logs `added` / `updated` / `skipped`, then exits 0.

```bash
docker build -t harbor-kb .
docker run --rm -e API_KEY="$GEMINI_API_KEY" -e GEMINI_FILE_SEARCH_STORE=fileSearchStores/... harbor-kb
```

Schedule: `.github/workflows/daily.yml` (06:00 UTC + `workflow_dispatch`).

**Job logs:** [Actions — daily-sync](https://github.com/bachle0212/harbor_agent/actions/workflows/daily.yml) · last local artefact: [`logs/last-run.json`](logs/last-run.json)
