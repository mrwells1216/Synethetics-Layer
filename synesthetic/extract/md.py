"""Markdown extractor (markdown-it-py)."""
from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt

from ..model import Block, Cell, Document, read_text


def _inline(token) -> tuple[str, list[tuple[int, int, str]]]:
    """Flatten an inline token to (text, emphasis spans)."""
    text = ""
    emph: list[tuple[int, int, str]] = []
    stack: list[tuple[str, int]] = []
    for ch in token.children or []:
        t = ch.type
        if t == "text":
            text += ch.content
        elif t in ("softbreak", "hardbreak"):
            text += " "
        elif t == "code_inline":
            start = len(text)
            text += ch.content
            emph.append((start, len(text), "code"))
        elif t == "strong_open":
            stack.append(("b", len(text)))
        elif t == "em_open":
            stack.append(("i", len(text)))
        elif t in ("strong_close", "em_close"):
            if stack:
                st, start = stack.pop()
                if len(text) > start:
                    emph.append((start, len(text), st))
        elif t == "image":
            text += ch.content
        # links keep their label via the text tokens; html_inline is dropped
    return text, emph


def extract(path) -> Document:
    path = Path(path)
    src = read_text(path)
    # strip YAML front matter
    if src.startswith("---\n"):
        end = src.find("\n---", 4)
        if end != -1:
            src = src[end + 4 :].lstrip("\n")
    md = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    tokens = md.parse(src)
    doc = Document(source=str(path), title=path.stem)

    list_stack: list[list] = []  # [ordered?, counter]
    pending_item: str | None = None
    quote_depth = 0
    i = 0
    n = len(tokens)
    while i < n:
        tk = tokens[i]
        t = tk.type
        if t == "heading_open":
            text, emph = _inline(tokens[i + 1])
            lvl = int(tk.tag[1])
            doc.blocks.append(Block("heading", text, level=lvl, emph=emph))
            if not doc.title or doc.title == path.stem:
                if lvl == 1:
                    doc.title = text
            i += 3
            continue
        if t in ("bullet_list_open", "ordered_list_open"):
            start = int(tk.attrGet("start") or 1) if t == "ordered_list_open" else 0
            list_stack.append([t == "ordered_list_open", start])
        elif t in ("bullet_list_close", "ordered_list_close"):
            if list_stack:
                list_stack.pop()
        elif t == "list_item_open":
            if list_stack:
                ordered, counter = list_stack[-1]
                if ordered:
                    pending_item = f"{counter}."
                    list_stack[-1][1] = counter + 1
                else:
                    pending_item = "•"
        elif t == "blockquote_open":
            quote_depth += 1
        elif t == "blockquote_close":
            quote_depth = max(0, quote_depth - 1)
        elif t == "paragraph_open":
            text, emph = _inline(tokens[i + 1])
            if pending_item is not None:
                doc.blocks.append(
                    Block("item", text, level=max(len(list_stack) - 1, 0), marker=pending_item, emph=emph)
                )
                pending_item = None
            elif quote_depth:
                doc.blocks.append(Block("quote", text, emph=emph))
            elif list_stack:
                doc.blocks.append(Block("para", text, level=len(list_stack), emph=emph))
            else:
                doc.blocks.append(Block("para", text, emph=emph))
            i += 3
            continue
        elif t in ("fence", "code_block"):
            doc.blocks.append(Block("code", tk.content.rstrip("\n")))
        elif t == "hr":
            doc.blocks.append(Block("rule"))
        elif t == "table_open":
            rows: list[list[Cell]] = []
            header_rows = 0
            j = i + 1
            in_head = False
            cur: list[Cell] = []
            while j < n and tokens[j].type != "table_close":
                tj = tokens[j]
                if tj.type == "thead_open":
                    in_head = True
                elif tj.type == "thead_close":
                    in_head = False
                elif tj.type == "tr_open":
                    cur = []
                elif tj.type in ("th_open", "td_open"):
                    text, _ = _inline(tokens[j + 1])
                    cur.append(Cell(text))
                elif tj.type == "tr_close":
                    rows.append(cur)
                    if in_head:
                        header_rows += 1
                j += 1
            doc.blocks.append(Block("table", rows=rows, header_rows=header_rows))
            i = j + 1
            continue
        i += 1

    if not doc.blocks:
        doc.notes.append("The file has no text.")
    return doc
