# Synesthetic Layer

Turns .txt, .md, .docx, .doc, .pdf and .xlsx files into a self-contained HTML page with a color, font and highlight layer, and does the same for Claude's chat replies through a mod. Detection is automatic: no markers, no emoji. Runs locally.

Read `reports/Color styling for reading and retention.md` first: it says what the research supports (sparse, accurate emphasis; personalized colors) and what it doesn't (dense multi-category coloring as a memory aid).

## Convert files

```
.venv\Scripts\python.exe -m synesthetic "path\to\file.pdf"            # -> synesthetic-out\file.pdf.html
.venv\Scripts\python.exe -m synesthetic "path\to\folder" -o out       # whole folder + out\index.html
```

| Option | What it does |
|---|---|
| `--mode a\|b\|c\|d` | colored text, highlight chips, combined (default), underline only (text stays neutral) |
| `--theme`, `--palette cb` | dark / light / auto; color-blind-safe palette |
| `--grammar` | grammar layer (nouns, verbs, adjectives, adverbs), offline, spaCy. Busy: off by default |
| `--ai` | meaning layer: Claude marks key terms, definitions, actions, cautions, examples. Sends text to Claude through your `claude` login. Cached. `--ai-model`, `--ai-max-calls` |
| `--fast` / `--tables` | skip / force PDF table detection (on for one file, off for folders) |
| `--lens my.toml` | your own categories, colors and patterns |

On the page: switch style, spacing (Normal/Roomy), theme and palette live; the legend turns each layer and category on or off. Choices are remembered per browser.

## Web app

The same upload page runs in two places:

- **On Vercel:** `api/index.py` plus `vercel.json`. Every push to `main` deploys. Pick a file or paste text, get the styled page, then save or open it. Uploads are capped at 4.4 MB (Vercel's request limit). Files are converted on the server and not stored. The AI layer is not offered there.
- **On this machine:** `.venv\Scripts\python.exe -m synesthetic serve` (add `--tailscale` to reach it from your phone over your Tailscale network). Up to 60 MB, nothing leaves the machine.

**Customize** sets each category's color (dark and light theme), body and heading fonts, text size, highlight style and theme, with a live preview. The defaults come from the lens; Reset puts them back. Settings are saved in the browser and baked into every page you convert. Export saves them as a file, which you can import on another device or pass to the command line with `--style synesthetic-style.json`.

**Try an example** on the home page converts a made-up document for a common use (study notes, a lease, care instructions, a work email, a recipe, a budget, a trip itinerary) with your settings. The samples are in `synesthetic/examples/`; add one by dropping a `.md` file there and listing it in `examples.toml`.

The page lives in `synesthetic/templates/app.html`; its look is described in `docs/design-system.md`. Runtime dependencies are in `requirements.txt`.

## Claude chat replies

The mod lives in `chat-mod/synesthetic-chat/` (copy it into `~/.claude/dev-mods/<session id>/` to load it in a session) and draws assistant replies with the same lens (content types only; grammar and meaning need models). Options (style, theme, palette, categories off) are in the mod's config. After editing `lenses/default.toml`, run `.venv\Scripts\python.exe tools\export_lens.py` and `tools\parity.py` to refresh the mod and confirm it still matches.

## Layout

- `synesthetic/extract/`: one reader per format into a common document model
- `synesthetic/annotate.py`, `grammar.py`, `meaning.py`, `layers.py`: the three layers and how they combine
- `synesthetic/colorcheck.py`: contrast and color-blindness checks (tested)
- `lenses/default.toml`: the single source of categories, colors, cues
- `tools/`: lens export for the mod, parity check
- `tests/`: `.venv\Scripts\python.exe -m pytest -q`

## Known limits

- Scanned PDFs have no text; flagged, no OCR.
- Legacy `.doc` is read as plain text (no headings or tables) unless LibreOffice is installed. Not tested on a real `.doc`.
- The AI layer needs a working `claude` login; if it can't run, the page renders without it.
- Names are a rough heuristic and start switched off.
- The chat mod is untested inside the live app until it loads; it has not been seen on a phone.
