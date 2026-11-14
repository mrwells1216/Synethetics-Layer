"""Command line: synesthetic <file|folder> [-o OUT]."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .annotate import load_lens
from .extract import SUPPORTED, UnsupportedFile, extract
from .render import render_document, render_index


def _convert(src: Path, dest: Path, lens, args) -> str:
    doc = extract(src)
    dest.parent.mkdir(parents=True, exist_ok=True)
    ai = {"model": args.ai_model, "max_calls": args.ai_max_calls} if args.ai else None
    dest.write_text(
        render_document(doc, lens, mode=args.mode, theme=args.theme, palette=args.palette,
                        grammar=args.grammar, ai=ai),
        encoding="utf-8",
    )
    return "ok" if not doc.notes else "ok (" + "; ".join(doc.notes) + ")"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "serve":
        from .serve import main as serve_main

        return serve_main(argv[1:])
    ap = argparse.ArgumentParser(prog="synesthetic", description="Render documents as color-coded HTML.")
    ap.add_argument("path", help="A file or a folder")
    ap.add_argument("-o", "--out", help="Output folder (default: ./synesthetic-out next to the input)")
    ap.add_argument("--lens", help="Path to a lens .toml (default: lenses/default.toml)")
    ap.add_argument("--mode", choices=["a", "b", "c", "d"], default="c",
                    help="a=colored text, b=highlights, c=combined, d=underline only (text stays neutral)")
    ap.add_argument("--theme", choices=["dark", "light", "auto"], default="auto")
    ap.add_argument("--palette", choices=["default", "cb"], default="default")
    ap.add_argument("--grammar", action="store_true", help="Add the grammar layer (nouns, verbs, adjectives, adverbs); offline")
    ap.add_argument("--ai", action="store_true", help="Add the meaning layer: Claude marks key terms, definitions, actions, cautions, examples. Sends text to Claude.")
    ap.add_argument("--ai-model", default="haiku", help="Model alias for the meaning layer (default: haiku)")
    ap.add_argument("--ai-max-calls", type=int, default=30, help="Cap on model calls per file (default: 30)")
    ap.add_argument("--fast", action="store_true", help="Skip PDF table detection (about 30x faster on big PDFs)")
    ap.add_argument("--tables", action="store_true", help="Force PDF table detection (default: on for one file, off for folders)")
    args = ap.parse_args(argv)
    from .extract import pdf as _pdf

    if args.fast:
        _pdf.FIND_TABLES = False
    elif args.tables:
        _pdf.FIND_TABLES = True
    else:
        _pdf.FIND_TABLES = Path(args.path).is_file()

    src = Path(args.path).resolve()
    if not src.exists():
        print(f"Not found: {src}", file=sys.stderr)
        return 2
    lens = load_lens(args.lens)

    if src.is_file():
        out_dir = Path(args.out).resolve() if args.out else src.parent / "synesthetic-out"
        dest = out_dir / (src.name + ".html")
        try:
            status = _convert(src, dest, lens, args)
        except UnsupportedFile as e:
            print(f"Skipped: {e}", file=sys.stderr)
            return 1
        print(f"{status}: {dest}")
        return 0

    out_dir = Path(args.out).resolve() if args.out else src / "synesthetic-out"
    entries = []
    ok = failed = 0
    for f in sorted(src.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in SUPPORTED:
            continue
        if out_dir in f.parents:
            continue
        rel = f.relative_to(src)
        dest = out_dir / (str(rel) + ".html")
        try:
            status = _convert(f, dest, lens, args)
            ok += 1
            entries.append({"href": dest.relative_to(out_dir).as_posix(), "name": rel.as_posix(), "kind": f.suffix.lower(), "status": status})
        except Exception as e:  # keep going on bad files
            failed += 1
            entries.append({"href": "", "name": rel.as_posix(), "kind": f.suffix.lower(), "status": f"failed: {e}"})
            print(f"Failed {rel}: {e}", file=sys.stderr)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(render_index(entries, src.name), encoding="utf-8")
    print(f"{ok} converted, {failed} failed. Index: {out_dir / 'index.html'}")
    return 0 if ok or not failed else 1


if __name__ == "__main__":
    sys.exit(main())
