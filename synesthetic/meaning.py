"""Meaning layer: a language model marks key terms, definitions, actions, cautions, examples.

Opt-in only. The passage text is sent to Claude through the local `claude` CLI (your own login,
no API key handling here). Results are cached on disk so a passage is only ever sent once.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .annotate import Lens, Span

PROMPT_VERSION = "v1"
CACHE_PATH = Path(__file__).resolve().parent.parent / ".synesthetic-cache" / "meaning.json"
MIN_CHARS = 40
MAX_BATCH_CHARS = 6000
MAX_BATCH_ITEMS = 30


class AIUnavailable(Exception):
    pass


def _prompt(passages: list[tuple[int, str]], cats) -> str:
    cat_lines = "\n".join(f'- "{c.name}": {c.description}' for c in cats)
    body = "\n\n".join(f"[{i}] {t}" for i, t in passages)
    return (
        "You mark up passages for a reading aid. For each numbered passage, pick the few short phrases "
        "(copied EXACTLY from the passage, at most 8 words each) that belong to one of these categories:\n"
        f"{cat_lines}\n\n"
        "Rules: be selective, usually 0 to 3 phrases per passage and none if nothing stands out; never overlap "
        "phrases; copy text exactly including punctuation inside the phrase; do not mark whole sentences.\n"
        'Reply with ONLY a JSON array, no prose, like [{"i": 0, "phrase": "exact text", "cat": "keyterm"}].\n\n'
        f"PASSAGES:\n{body}\n"
    )


def _run_claude(prompt: str, model: str) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise AIUnavailable("The `claude` command was not found on PATH.")
    cwd = tempfile.mkdtemp(prefix="synesthetic_ai_")  # empty folder: no project context is loaded
    cmd = [exe, "-p", "--model", model, "--tools", "", "--no-session-persistence",
           "--disable-slash-commands", "--output-format", "json"]
    res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                         cwd=cwd, timeout=240)
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and data.get("is_error"):
        msg = str(data.get("result", "unknown error"))
        if "authenticate" in msg.lower() or "oauth" in msg.lower():
            msg += " Sign in again by running `claude` in a terminal and using /login."
        raise AIUnavailable(msg)
    if res.returncode != 0:
        raise AIUnavailable(f"claude exited with {res.returncode}: {res.stderr.strip()[:200]}")
    return data.get("result", "") if isinstance(data, dict) else res.stdout


def _parse(reply: str) -> list[dict]:
    m = re.search(r"\[.*\]", reply, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict) and {"i", "phrase", "cat"} <= d.keys()]


def _key(text: str) -> str:
    return hashlib.sha1((PROMPT_VERSION + "\0" + text).encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def _spans(text: str, items: list[dict], valid: set[str]) -> list[Span]:
    spans: list[Span] = []
    taken = bytearray(len(text))
    for d in items:
        phrase, cat = str(d["phrase"]), str(d["cat"])
        if cat not in valid or not phrase.strip():
            continue
        s = text.find(phrase)
        if s < 0:
            continue  # the model changed the text: ignore rather than guess
        e = s + len(phrase)
        if any(taken[s:e]):
            continue
        taken[s:e] = b"\x01" * (e - s)
        spans.append(Span(s, e, cat, "meaning"))
    spans.sort(key=lambda sp: sp.start)
    return spans


def plan(texts: list[str]) -> tuple[list[str], list[list[str]]]:
    """Return (all eligible passages, batches still needing a model call)."""
    cache = _load_cache()
    elig = [t for t in dict.fromkeys(texts) if len(t) >= MIN_CHARS]
    todo = [t for t in elig if _key(t) not in cache]
    batches: list[list[str]] = []
    cur: list[str] = []
    size = 0
    for t in todo:
        if cur and (size + len(t) > MAX_BATCH_CHARS or len(cur) >= MAX_BATCH_ITEMS):
            batches.append(cur)
            cur, size = [], 0
        cur.append(t)
        size += len(t)
    if cur:
        batches.append(cur)
    return elig, batches


def tag_texts(texts: list[str], lens: Lens, *, model: str = "haiku", max_calls: int = 30,
              workers: int = 3, log=print) -> dict[str, list[Span]]:
    cats = [c for c in lens.categories if c.layer == "meaning"]
    if not cats:
        return {}
    valid = {c.name for c in cats}
    elig, batches = plan(texts)
    cache = _load_cache()
    if len(batches) > max_calls:
        log(f"AI layer: {len(batches)} model calls needed; doing the first {max_calls} (raise --ai-max-calls for more).")
        batches = batches[:max_calls]
    if batches:
        log(f"AI layer: {sum(len(b) for b in batches)} passages in {len(batches)} call(s) to Claude ({model}).")

    def work(batch: list[str]):
        passages = list(enumerate(batch))
        reply = _run_claude(_prompt(passages, cats), model)
        by_i: dict[int, list[dict]] = {i: [] for i, _ in passages}
        for d in _parse(reply):
            try:
                by_i[int(d["i"])].append({"phrase": d["phrase"], "cat": d["cat"]})
            except (KeyError, ValueError, TypeError):
                continue
        return batch, by_i

    if batches:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for batch, by_i in ex.map(work, batches):
                for i, t in enumerate(batch):
                    cache[_key(t)] = by_i.get(i, [])
        _save_cache(cache)

    out: dict[str, list[Span]] = {}
    for t in elig:
        items = cache.get(_key(t))
        if items:
            out[t] = _spans(t, items, valid)
    return out
