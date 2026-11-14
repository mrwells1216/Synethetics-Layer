import threading
import urllib.error
import urllib.request

import pytest

from synesthetic.annotate import load_lens
from synesthetic.serve import make_handler, make_server


@pytest.fixture()
def server():
    srv = make_server("127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def post(base, name, data, extra=""):
    req = urllib.request.Request(f"{base}/convert?name={name}{extra}", data=data, method="POST")
    return urllib.request.urlopen(req, timeout=30)


def test_upload_page(server):
    html = urllib.request.urlopen(server + "/", timeout=10).read().decode()
    assert "Synesthetic Layer" in html and ".pdf" in html


def test_convert_markdown(server):
    r = post(server, "note.md", b"# Title\n\nPay $1,250 by Aug 14, 2026.\n")
    html = r.read().decode()
    assert r.status == 200 and 'data-cat="number"' in html and 'data-cat="date"' in html


def test_rejects_unknown_type_and_empty(server):
    for name, data, code in (("a.exe", b"x", 400), ("a.md", b"", 413)):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(server, name, data)
        assert e.value.code == code


def test_cross_site_post_is_refused(server):
    req = urllib.request.Request(f"{server}/convert?name=a.md", data=b"# hi\n", method="POST",
                                 headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 403
    host = server.split("//", 1)[1]
    req = urllib.request.Request(f"{server}/convert?name=a.md", data=b"# hi\n", method="POST",
                                 headers={"Sec-Fetch-Site": "same-origin", "Origin": f"http://{host}"})
    assert urllib.request.urlopen(req, timeout=10).status == 200


def test_page_has_config_and_any_get_serves_it(server):
    import json
    import re

    for path in ("/", "/api/index"):
        html = urllib.request.urlopen(server + path, timeout=10).read().decode()
        cfg = json.loads(re.search(r'<script id="cfg" type="application/json">(.*?)</script>', html).group(1))
        assert ".pdf" in cfg["exts"] and cfg["maxBytes"] > 0 and cfg["hosted"] is False
        exs = cfg["examples"]
        assert len(exs) >= 5 and all(e["text"] and e["name"].endswith(".md") for e in exs)
        assert all(len(e["cats"]) >= 4 for e in exs)  # each example shows several colors


def test_name_from_header_and_any_post_path(server):
    req = urllib.request.Request(f"{server}/api/convert", data=b"# T\n\nPay $5 today.\n", method="POST",
                                 headers={"X-File-Name": "my%20notes.md"})
    html = urllib.request.urlopen(req, timeout=10).read().decode()
    assert "my notes.md" in html and 'data-cat="number"' in html


def test_style_header_is_applied(server):
    import json
    from urllib.parse import quote

    style = quote(json.dumps({"colors": {"date": {"dark": "#010203"}}, "heading": "young"}))
    req = urllib.request.Request(f"{server}/api/convert", data=b"Due Aug 14, 2026.\n", method="POST",
                                 headers={"X-File-Name": "a.md", "X-Style": style})
    html = urllib.request.urlopen(req, timeout=10).read().decode()
    assert "--c-date:#010203" in html and "family=Young+Serif" in html
    bad = urllib.request.Request(f"{server}/api/convert", data=b"x\n", method="POST",
                                 headers={"X-File-Name": "a.md", "X-Style": "%7Bnot json"})
    assert urllib.request.urlopen(bad, timeout=10).status == 200


def test_size_limit_is_per_server():
    srv = make_server("127.0.0.1", 0)
    srv.RequestHandlerClass = make_handler(load_lens(), max_bytes=10)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            post(f"http://127.0.0.1:{srv.server_address[1]}", "a.md", b"# more than ten bytes\n")
        assert e.value.code == 413
    finally:
        srv.shutdown()


def test_vercel_entry_point_imports():
    import importlib.util
    from http.server import BaseHTTPRequestHandler
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent / "api" / "index.py"
    spec = importlib.util.spec_from_file_location("vercel_index", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert issubclass(mod.handler, BaseHTTPRequestHandler)


def test_path_traversal_name_is_flattened(server):
    r = post(server, "..%2F..%2Fevil.md", b"# hi\n")
    assert r.status == 200
