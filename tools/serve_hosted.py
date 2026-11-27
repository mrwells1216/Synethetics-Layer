"""Run the app on this computer the way the hosted site runs it (hosted=True), to try the hosted-only
parts: the store notes and the Editor's looks going to the store. A stand-in store id is set so the page
reports a store; nothing reaches a real one.

    .venv\\Scripts\\python.exe tools\\serve_hosted.py [--port 8782]
"""
from __future__ import annotations

import argparse
import os
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("BLOB_STORE_ID", "store_local_test")

from synesthetic.annotate import load_lens  # noqa: E402
from synesthetic.serve import make_handler  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The app as hosted, on this computer.")
    ap.add_argument("--port", type=int, default=8782)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(load_lens(), hosted=True))
    print(f"Hosted mode at http://127.0.0.1:{args.port}/. Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
