"""`synesthetic serve`: a tiny upload page so a phone (or any browser) can convert a file.

Pick a file in the browser, get the styled page back. Binds to localhost unless told otherwise;
`--tailscale` binds to this machine's Tailscale address so only your own tailnet can reach it.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .annotate import load_lens
from .extract import SUPPORTED, UnsupportedFile, extract
from .render import render_document

MAX_BYTES = 60 * 1024 * 1024

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Synesthetic Layer</title>
<style>
:root{color-scheme:dark light}
body{margin:0;font:18px/1.6 system-ui,sans-serif;background:#14161b;color:#e6e8ec;display:grid;min-height:100vh;place-items:center}
@media (prefers-color-scheme:light){body{background:#fbfbf8;color:#1d2026}}
main{width:min(520px,92vw);padding:24px 0}
h1{font-family:Georgia,serif;font-size:1.7em;margin:.2em 0}
p{opacity:.8;margin:.3em 0 1em}
label.pick{display:block;border:2px dashed #8896;border-radius:14px;padding:34px 16px;text-align:center;cursor:pointer}
input[type=file]{display:none}
.opts{margin:14px 0}.opts label{display:block;margin:6px 0}
button{all:unset;display:block;text-align:center;background:#6cb4ff;color:#0b1220;font-weight:700;padding:14px;border-radius:12px;cursor:pointer;width:100%;box-sizing:border-box}
button[disabled]{opacity:.5}
#msg{margin-top:12px;min-height:1.4em;color:#ff8f8f}
</style></head><body><main>
<h1>Synesthetic Layer</h1>
<p>Choose a file ({exts}) and get it back with color, font and highlight styling.</p>
<label class="pick" id="pick"><span id="name">Tap to choose a file</span>
<input id="f" type="file" accept="{accept}"></label>
<div class="opts">
<label><input id="grammar" type="checkbox"> Grammar layer (nouns, verbs, ...)</label>
<label><input id="fast" type="checkbox"> Fast PDF (skip table detection)</label>
</div>
<button id="go" disabled>Convert</button><div id="msg"></div>
</main><script>
var f=document.getElementById('f'),go=document.getElementById('go'),msg=document.getElementById('msg');
f.onchange=function(){document.getElementById('name').textContent=f.files[0]?f.files[0].name:'Tap to choose a file';go.disabled=!f.files[0]};
go.onclick=async function(){
  var file=f.files[0];if(!file)return;go.disabled=true;msg.style.color='inherit';msg.textContent='Converting...';
  try{
    var q='name='+encodeURIComponent(file.name)+'&grammar='+(document.getElementById('grammar').checked?1:0)+'&fast='+(document.getElementById('fast').checked?1:0);
    var r=await fetch('/convert?'+q,{method:'POST',body:file});var t=await r.text();
    if(!r.ok){msg.style.color='#ff8f8f';msg.textContent=t;go.disabled=false;return}
    location.href=URL.createObjectURL(new Blob([t],{type:'text/html'}));
  }catch(e){msg.style.color='#ff8f8f';msg.textContent='Failed: '+e;go.disabled=false}
};
</script></body></html>"""


def make_handler(lens):
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
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if urlparse(self.path).path in ("/", "/index.html"):
                exts = ", ".join(sorted(SUPPORTED))
                page = PAGE.replace("{exts}", exts).replace("{accept}", ",".join(sorted(SUPPORTED)))
                self._send(200, page)
            else:
                self._send(404, "Not found", "text/plain; charset=utf-8")

        def do_POST(self):
            url = urlparse(self.path)
            if url.path != "/convert":
                return self._send(404, "Not found", "text/plain; charset=utf-8")
            q = parse_qs(url.query)
            name = Path((q.get("name") or ["upload"])[0]).name
            name = re.sub(r"[^\w .()\-]", "_", name) or "upload"
            if Path(name).suffix.lower() not in SUPPORTED:
                return self._send(400, f"Unsupported file type. Use: {', '.join(sorted(SUPPORTED))}",
                                  "text/plain; charset=utf-8")
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                n = 0
            if n <= 0 or n > MAX_BYTES:
                return self._send(413, "File is empty or larger than 60 MB.", "text/plain; charset=utf-8")
            body = self.rfile.read(n)
            tmp = Path(tempfile.mkdtemp(prefix="synesthetic_up_"))
            try:
                src = tmp / name
                src.write_bytes(body)
                from .extract import pdf as _pdf

                _pdf.FIND_TABLES = (q.get("fast") or ["0"])[0] != "1"
                doc = extract(src)
                html = render_document(doc, lens, grammar=(q.get("grammar") or ["0"])[0] == "1")
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
