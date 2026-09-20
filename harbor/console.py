"""Local playground to ask the File Search store."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from harbor.ask import ask, split_reply
from harbor.catalog import Catalog
from harbor.config import ARTICLES_DIR, GEMINI_MODEL, api_key, vector_store_id

STATIC = Path(__file__).resolve().parent / "static"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def status_payload() -> dict[str, object]:
    catalog = Catalog.load()
    store = vector_store_id() or catalog.vector_store_id or ""
    if catalog.articles:
        articles = len(catalog.articles)
    elif ARTICLES_DIR.exists():
        articles = len(list(ARTICLES_DIR.glob("*.md")))
    else:
        articles = 0
    return {
        "store": store,
        "model": GEMINI_MODEL,
        "articles": articles,
        "has_key": bool(api_key()),
    }


class ConsoleHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        print("%s - %s" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict[str, object]) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            html = (STATIC / "console.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
            return
        if path == "/api/status":
            self._json(200, status_payload())
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/ask":
            self._json(404, {"error": "Not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "Body must be JSON"})
            return
        question = str(payload.get("question") or "").strip()
        if not question:
            self._json(400, {"error": "Ask a question first"})
            return
        if not api_key():
            self._json(503, {"error": "Missing GEMINI_API_KEY"})
            return
        try:
            reply = ask(question)
        except Exception as exc:  # noqa: BLE001 — surface Gemini errors in the desk
            self._json(502, {"error": str(exc)})
            return
        split = split_reply(reply)
        self._json(200, {"text": split["text"], "citations": split["citations"], "raw": reply})


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    httpd = ThreadingHTTPServer((host, port), ConsoleHandler)
    print(f"Harbor desk: http://{host}:{port}", flush=True)
    httpd.serve_forever()


def repl() -> int:
    if not api_key():
        print("Missing GEMINI_API_KEY (or GOOGLE_API_KEY / API_KEY).")
        return 1
    print("Ask OptiBot from the uploaded docs. Empty line exits.")
    while True:
        try:
            question = input("ask> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            return 0
        print(ask(question))
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local desk / REPL for File Search.")
    parser.add_argument("--repl", action="store_true", help="Terminal prompt instead of the browser desk.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    if args.repl:
        return repl()
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
