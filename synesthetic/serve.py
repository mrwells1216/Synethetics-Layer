"""`synesthetic serve`: a tiny upload page so a phone (or any browser) can convert a file.

Pick a file in the browser, get the styled page back. Binds to localhost unless told otherwise;
`--tailscale` binds to this machine's Tailscale address so only your own tailnet can reach it.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .annotate import load_lens
from .extract import SUPPORTED, UnsupportedFile, extract
from .render import FONT_CHOICES, STYLE_DEFAULTS, render_document

MAX_BYTES = 60 * 1024 * 1024
APP_PAGE = Path(__file__).resolve().parent / "templates" / "app.html"
EXAMPLES = Path(__file__).resolve().parent / "examples"


def grammar_installed() -> bool:
    """Cheap check (no model load) so the page can offer the grammar option."""
    return all(importlib.util.find_spec(m) is not None for m in ("spacy", "en_core_web_sm"))


def load_examples(lens) -> list[dict]:
    """The sample documents under "Try an example", each with the content colors it shows."""
    meta = tomllib.loads((EXAMPLES / "examples.toml").read_text(encoding="utf-8"))["example"]
    shown = [c.name for c in lens.categories if c.layer == "content" and not c.default_off]
    out = []
    for ex in meta:
        path = EXAMPLES / ex["file"]
        html = render_document(extract(path), lens, log=lambda *a, **k: None)
        found = set(re.findall(r'data-cat="([\w-]+)"', html.split("<main>", 1)[-1]))
        out.append({"title": ex["title"], "blurb": ex["blurb"], "grammar": bool(ex.get("grammar")),
                    "name": ex["title"] + ".md", "text": path.read_text(encoding="utf-8"),
                    "cats": [c for c in shown if c in found]})
    return out


def app_page(lens, max_bytes: int, hosted: bool) -> str:
    cfg = {
        "exts": sorted(SUPPORTED), "maxBytes": max_bytes, "grammar": grammar_installed(), "hosted": hosted,
        "examples": load_examples(lens),
        "categories": [
            {"name": c.name, "label": c.label, "layer": c.layer, "example": c.example,
             "dark": c.colors["dark"], "light": c.colors["light"], "off": c.default_off}
            for c in lens.categories
        ],
        "fonts": [{"key": k, "label": v[0], "stack": v[1], "google": v[2]} for k, v in FONT_CHOICES.items()],
        "defaults": STYLE_DEFAULTS,
    }
    return APP_PAGE.read_text(encoding="utf-8").replace("{{CONFIG}}", json.dumps(cfg).replace("</", "<\\/"))


def make_handler(lens, max_bytes: int = MAX_BYTES, hosted: bool = False):
    """One page (any GET) and one action (any POST converts the body), so it works the same
    behind Vercel's rewrites as on this machine."""
    page = app_page(lens, max_bytes, hosted)

    class Handler(BaseHTTPRequestHandler):
        server_version = "Synesthetic"

        def log_message(self, fmt, *args):  # quiet: file names are private
            pass

        def _send(self, code: int, body: str, ctype="text/html; charset=utf-8"):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if urlparse(self.path).path.endswith(("/favicon.ico", "/robots.txt")):
                return self._send(404, "Not found", "text/plain; charset=utf-8")
            self._send(200, page)

        def _same_origin(self) -> bool:
            """Only the upload page itself may post: a web page in the same browser must not be able
            to feed this converter files (browsers send Sec-Fetch-Site / Origin on cross-site posts)."""
            site = self.headers.get("Sec-Fetch-Site")
            if site is not None:
                return site in ("same-origin", "none")
            origin = self.headers.get("Origin")
            if origin is None:
                return True  # curl, tests and old browsers: no cross-site signal at all
            host = self.headers.get("Host", "")
            return origin.lower() in (f"http://{host}".lower(), f"https://{host}".lower())

        def do_POST(self):
            url = urlparse(self.path)
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                n = 0
            if n <= 0 or n > max_bytes:
                return self._send(413, f"File is empty or larger than {max_bytes / 1048576:.1f} MB.",
                                  "text/plain; charset=utf-8")
            # read the body before any refusal: replying first makes browsers drop the connection
            # (reset) instead of showing the error message
            body = self.rfile.read(n)
            if not self._same_origin():
                return self._send(403, "Cross-site upload refused.", "text/plain; charset=utf-8")
            q = parse_qs(url.query)
            # the page sends the name in a header so it stays out of URLs and request logs
            name = unquote(self.headers.get("X-File-Name", "")) or (q.get("name") or ["upload"])[0]
            name = Path(name.replace("\\", "/")).name
            name = re.sub(r"[^\w .()\-]", "_", name) or "upload"
            if Path(name).suffix.lower() not in SUPPORTED:
                return self._send(400, f"Unsupported file type. Use: {', '.join(sorted(SUPPORTED))}",
                                  "text/plain; charset=utf-8")
            tmp = Path(tempfile.mkdtemp(prefix="synesthetic_up_"))
            try:
                src = tmp / name
                src.write_bytes(body)
                doc = extract(src, find_tables=(q.get("fast") or ["0"])[0] != "1")
                try:  # the page's saved colors and fonts; render_document keeps only valid values
                    style = json.loads(unquote(self.headers.get("X-Style", "")) or "null")
                except ValueError:
                    style = None
                html = render_document(doc, lens, grammar=(q.get("grammar") or ["0"])[0] == "1", style=style)
                self._send(200, html)
            except UnsupportedFile as e:
                self._send(400, str(e), "text/plain; charset=utf-8")
            except Exception as e:  # report, don't crash the server
                self._send(500, f"Could not convert this file: {e}", "text/plain; charset=utf-8")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

    return Handler


def tailscale_ip() -> str | None:
    exe = shutil.which("tailscale")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=10).stdout.split()
        return out[0] if out else None
    except Exception:
        return None


def make_server(host: str, port: int, lens=None) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(lens or load_lens()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="synesthetic serve", description="Upload page for phones and browsers.")
    ap.add_argument("--host", default="127.0.0.1", help="Address to listen on (default: 127.0.0.1, this machine only)")
    ap.add_argument("--tailscale", action="store_true", help="Listen only on this machine's Tailscale address")
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--lens")
    args = ap.parse_args(argv)
    host = args.host
    if args.tailscale:
        host = tailscale_ip()
        if not host:
            print("Tailscale address not found. Is Tailscale running?", file=sys.stderr)
            return 2
    try:
        srv = make_server(host, args.port, load_lens(args.lens))
    except OSError as e:
        print(f"Could not listen on {host}:{args.port}: {e}", file=sys.stderr)
        return 2
    print(f"Open http://{host}:{args.port}/ on your phone. Ctrl+C to stop.")
    if host not in ("127.0.0.1", "localhost"):
        print("Reachable by other devices on that network. Anyone who can reach it can upload files.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
