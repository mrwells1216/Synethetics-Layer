"""`synesthetic serve`: a tiny upload page so a phone (or any browser) can convert a file.

Pick a file in the browser, get the styled page back. Binds to localhost unless told otherwise;
`--tailscale` binds to this machine's Tailscale address so only your own tailnet can reach it.
"""
from __future__ import annotations

import argparse
import hmac
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import changelog
from . import fixes as fixmod
from .annotate import load_lens
from .extract import SUPPORTED, UnsupportedFile, extract
from .overlay import OVERLAY_TYPES, OverlayError, layout_units, overlay, parse_only
from .render import FONT_CHOICES, HL_SIZES, STYLE_DEFAULTS, clean_style, render_document
from .thumb import thumbnail

MAX_BYTES = 60 * 1024 * 1024
APP_PAGE = Path(__file__).resolve().parent / "templates" / "app.html"
STATIC = Path(__file__).resolve().parent / "static"  # icons, drawn by tools/make_icons.py
ICONS = {"favicon.ico": "favicon-32.png", **{p: p for p in (
    "icon.svg", "favicon.svg", "favicon-32.png", "icon-192.png", "icon-512.png",
    "icon-maskable-512.png", "apple-touch-icon.png", "showcase.json", "dev.js")},
    # sample files to try in Synesthesize (tools/build_samples.py)
    "market-wrap.pdf": "samples/market-wrap.pdf", "market-wrap.docx": "samples/market-wrap.docx"}
CTYPES = {".png": "image/png", ".svg": "image/svg+xml", ".json": "application/json", ".pdf": "application/pdf",
          ".js": "text/javascript; charset=utf-8",
          ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
SAMPLES = [{"file": "market-wrap.pdf", "label": "Weekly market wrap", "kind": "PDF, 3 pages"},
           {"file": "market-wrap.docx", "label": "Weekly market wrap", "kind": "Word"}]
MIME = {".txt": "text/plain", ".md": "text/markdown", ".markdown": "text/markdown", ".pdf": "application/pdf",
        ".doc": "application/msword", **OVERLAY_TYPES,
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _version(path: Path) -> str:
    """A short fingerprint of a file, so browsers fetch it again after it changes."""
    import hashlib

    return hashlib.sha1(path.read_bytes()).hexdigest()[:10] if path.is_file() else ""


def manifest(exts) -> dict:
    """Lets phones add the app to the home screen and desktop browsers install it as an app
    (its own window, and on desktop Chrome/Edge an "Open with" entry for the supported files)."""
    accept: dict[str, list[str]] = {}
    for e in sorted(exts):
        accept.setdefault(MIME.get(e, "application/octet-stream"), []).append(e)
    return {
        "name": "Synesthetic Layer", "short_name": "Synesthetic", "id": "/", "start_url": "/",
        "description": "Your documents, re-lettered in color.",
        "display": "standalone", "background_color": "#0e1014", "theme_color": "#0e1014",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
        ],
        "file_handlers": [{"action": "/", "accept": accept}],
        "launch_handler": {"client_mode": "focus-existing"},
    }


def grammar_installed() -> bool:
    """Cheap check (no model load) so the page can offer the grammar option."""
    return all(importlib.util.find_spec(m) is not None for m in ("spacy", "en_core_web_sm"))


def app_page(lens, max_bytes: int, hosted: bool) -> str:
    cfg = {
        "exts": sorted(SUPPORTED), "keepExts": sorted(OVERLAY_TYPES), "maxBytes": max_bytes, "grammar": grammar_installed(), "hosted": hosted,
        "showcase": (STATIC / "showcase.json").is_file(), "showcaseV": _version(STATIC / "showcase.json"),
        "samples": [x for x in SAMPLES if (STATIC / ICONS[x["file"]]).is_file()], "hlCss": HL_SIZES,
        "categories": [
            {"name": c.name, "label": c.label, "layer": c.layer, "example": c.example,
             "dark": c.colors["dark"], "light": c.colors["light"], "off": c.default_off,
             "cbDark": c.colors["cb_dark"], "cbLight": c.colors["cb_light"], "case": c.case, "scale": c.scale,
             "bold": c.weight >= 600, "thin": 0 < c.weight <= 300, "italic": c.font == "italic", "underline": c.underline,
             # content patterns, so the page can color its own text the same way (JS regex syntax
             # matches; tools/parity.py checks the same patterns for the chat mod)
             "priority": c.priority, "patterns": [p.pattern for p in c.patterns] if c.layer == "content" else [],
             "flags": "".join(f for f, bit in (("i", re.I), ("m", re.M), ("s", re.S))
                              if c.patterns and c.patterns[0].flags & bit)}
            for c in lens.categories
        ],
        "fonts": [{"key": k, "label": v[0], "stack": v[1], "google": v[2]} for k, v in FONT_CHOICES.items()],
        "defaults": STYLE_DEFAULTS,
        # developer mode: where fixes go, and the build they were made on
        "build": changelog.head()[:7], "repo": changelog.REPO_URL,
        "dev": {"store": ("blob" if fixmod.blob_ready() else "none") if hosted else "local",
                "keyed": bool(os.environ.get(DEV_KEY_ENV, "").strip())},
    }
    page = APP_PAGE.read_text(encoding="utf-8").replace("{{DEVJS}}", _version(STATIC / "dev.js"))
    return page.replace("{{CONFIG}}", json.dumps(cfg).replace("</", "<\\/"))


DEV_KEY_ENV = "SYNESTHETIC_DEV_KEY"


def _dev_store(hosted: bool, cache: dict):
    if "store" not in cache:
        if hosted:
            if not fixmod.blob_ready():
                raise fixmod.FixError("Fix storage isn't connected to this site yet.")
            cache["store"] = fixmod.BlobStore()
        else:
            cache["store"] = fixmod.LocalStore()
    return cache["store"]


def make_handler(lens, max_bytes: int = MAX_BYTES, hosted: bool = False):
    """One page (any GET) and one action (any POST converts the body), so it works the same
    behind Vercel's rewrites as on this machine."""
    page = app_page(lens, max_bytes, hosted)
    manifest_json = json.dumps(manifest(SUPPORTED))
    log_cache = changelog.Cached()
    dev_cache: dict = {}

    class Handler(BaseHTTPRequestHandler):
        server_version = "Synesthetic"

        def log_message(self, fmt, *args):  # quiet: file names are private
            pass

        def _send(self, code: int, body: str | bytes, ctype="text/html; charset=utf-8", extra=None):
            data = body.encode("utf-8") if isinstance(body, str) else body
            extra = {"Cache-Control": "no-store", **(extra or {})}
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            for k, v in extra.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            # behind Vercel every path is rewritten to /api/index; the original one comes as ?_p=
            leaf = ((parse_qs(url.query).get("_p") or [""])[0] or url.path).rsplit("/", 1)[-1]
            if leaf in ICONS and (STATIC / ICONS[leaf]).is_file():
                f = STATIC / ICONS[leaf]
                age = 3600 if f.suffix == ".json" else 86400
                return self._send(200, f.read_bytes(), CTYPES[f.suffix], {"Cache-Control": f"public, max-age={age}"})
            if leaf == "manifest.webmanifest":
                return self._send(200, manifest_json, "application/manifest+json")
            if leaf == "changelog.json":
                return self._send(200, log_cache.get(), "application/json")
            if leaf == "robots.txt":
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
            if n > max_bytes:
                # read (and drop) what was sent first: refusing mid-upload makes browsers show a reset
                # connection instead of this message
                left = min(n, 512 * 1024 * 1024)
                while left > 0:
                    chunk = self.rfile.read(min(left, 1 << 20))
                    if not chunk:
                        break
                    left -= len(chunk)
            if n <= 0 or n > max_bytes:
                return self._send(413, f"File is empty or larger than {max_bytes / 1048576:.1f} MB.",
                                  "text/plain; charset=utf-8")
            # read the body before any refusal: replying first makes browsers drop the connection
            # (reset) instead of showing the error message
            body = self.rfile.read(n)
            if not self._same_origin():
                return self._send(403, "Cross-site upload refused.", "text/plain; charset=utf-8")
            q = parse_qs(url.query)
            route = ((q.get("_p") or [""])[0] or url.path).rstrip("/").rsplit("/", 1)[-1]
            if route.startswith("fix-"):
                return self._fix(route, body)
            # the page sends the name in a header so it stays out of URLs and request logs
            name = unquote(self.headers.get("X-File-Name", "")) or (q.get("name") or ["upload"])[0]
            name = Path(name.replace("\\", "/")).name
            name = re.sub(r"[^\w .()\-]", "_", name) or "upload"
            if Path(name).suffix.lower() not in SUPPORTED:
                return self._send(400, f"Unsupported file type. Use: {', '.join(sorted(SUPPORTED))}",
                                  "text/plain; charset=utf-8")
            try:  # the page's saved colors and fonts; render_document keeps only valid values
                style = json.loads(unquote(self.headers.get("X-Style", "")) or "null")
            except ValueError:
                style = None
            grammar = (q.get("grammar") or ["0"])[0] == "1"
            palette = clean_style(style, lens).get("palette", "default")
            if route == "thumb":  # a picture of a colored file, for the Recent and Saved lists
                try:
                    pic = thumbnail(name, body, lens, style=style, palette=palette)
                except OverlayError as e:
                    return self._send(400, str(e), "text/plain; charset=utf-8")
                except Exception as e:
                    return self._send(500, f"Could not draw this file: {e}", "text/plain; charset=utf-8")
                return self._send(200, pic, "image/jpeg")
            if route == "units":  # the roller's view of a file: its pages and text, numbered
                try:
                    data = json.dumps(layout_units(name, body), separators=(",", ":"))
                except OverlayError as e:
                    return self._send(400, str(e), "text/plain; charset=utf-8")
                except Exception as e:
                    return self._send(500, f"Could not read this file: {e}", "text/plain; charset=utf-8")
                return self._send(200, data, "application/json")
            if (q.get("keep") or ["0"])[0] == "1" and Path(name).suffix.lower() in OVERLAY_TYPES:
                # keep the original look: the same kind of file back, with the colors on top
                only = parse_only(unquote(self.headers.get("X-Only", "")))
                try:
                    ov = overlay(name, body, lens, style=style, palette=palette, grammar=grammar, only=only,
                                 log=lambda *a, **k: None)
                except OverlayError as e:
                    return self._send(400, str(e), "text/plain; charset=utf-8")
                except Exception as e:
                    return self._send(500, f"Could not color this file: {e}", "text/plain; charset=utf-8")
                if len(ov.data) > max_bytes:
                    return self._send(413, "The colored copy is too large to send back here.",
                                      "text/plain; charset=utf-8")
                info = quote(json.dumps({"name": ov.name, "count": sum(ov.counts.values()), "notes": ov.notes,
                                         "cats": [c for c, _n in ov.counts.most_common() if lens.get(c)]}))
                return self._send(200, ov.data, ov.mime, {"X-Overlay": info})
            tmp = Path(tempfile.mkdtemp(prefix="synesthetic_up_"))
            try:
                src = tmp / name
                src.write_bytes(body)
                doc = extract(src, find_tables=(q.get("fast") or ["0"])[0] != "1")
                html = render_document(doc, lens, grammar=grammar, style=style)
                self._send(200, html)
            except UnsupportedFile as e:
                self._send(400, str(e), "text/plain; charset=utf-8")
            except Exception as e:  # report, don't crash the server
                self._send(500, f"Could not convert this file: {e}", "text/plain; charset=utf-8")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

        def _fix(self, route: str, body: bytes):
            """Developer mode: fixes and ideas for the next Claude session. Same-origin (checked above), a
            custom header, and the dev key when one is set; the hosted app refuses all of it without a key."""
            text = "text/plain; charset=utf-8"
            if self.headers.get("X-App") != "1":
                return self._send(403, "Missing the app's header.", text)
            key = os.environ.get(DEV_KEY_ENV, "").strip()  # a pasted key can carry a stray space or newline
            if key:
                if not hmac.compare_digest(self.headers.get("X-Dev-Key", "").strip().encode(), key.encode()):
                    return self._send(403, "This device isn't linked for developer mode. Open your dev link on it.",
                                      text)
            elif hosted:
                return self._send(403, "Developer mode isn't set up on this site yet.", text)
            oidc = self.headers.get("x-vercel-oidc-token")
            if oidc:  # Vercel's per-request credential for the connected Blob store
                os.environ["VERCEL_OIDC_TOKEN"] = oidc
            try:
                data = json.loads(body or b"{}")
            except ValueError:
                return self._send(400, "Send JSON.", text)
            if not isinstance(data, dict):
                return self._send(400, "Send a JSON object.", text)
            ok = lambda d: self._send(200, json.dumps({"ok": True, **d}), "application/json")  # noqa: E731
            try:
                store = _dev_store(hosted, dev_cache)
                if route == "fix-check":
                    return ok({"store": "blob" if hosted else "local"})
                if route == "fix-add":
                    entry, png = fixmod.clean_entry(data)
                    return ok({"id": store.add(entry, png)})
                if route == "fix-list":
                    return ok({"entries": store.public()})
                if route == "fix-image":
                    ref = str(data.get("ref", ""))
                    png = store.image(int(ref)) if not hosted and ref.isdigit() else (
                        store.image(ref) if hosted else None)
                    return self._send(200, png, "image/png") if png else self._send(404, "No picture.", text)
                if route == "fix-review":
                    ref = str(data.get("ref", ""))
                    rec = store.close(int(ref) if not hosted and ref.isdigit() else ref, data.get("status"),
                                      data.get("review"))
                    return ok({"status": rec["status"]})
                if route == "fix-export":
                    if not hosted:
                        return ok({"entries": []})  # the CLI reads the local store directly
                    return ok({"entries": store.entries(limit=500)})
            except fixmod.FixError as e:
                return self._send(400, str(e), text)
            except Exception as e:  # storage trouble: say so, plainly
                return self._send(502, f"Fix storage failed: {type(e).__name__}: {e}"[:300], text)
            return self._send(404, "Unknown developer route.", text)

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
