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
| `--keep` | keep the original look: write `file (colored).pdf/.docx/.xlsx` with the colors added on top, instead of an HTML page |

On the page: switch style, spacing (Normal/Roomy), theme and palette live; the legend turns each layer and category on or off. Choices are remembered per browser.

## Web app

The same upload page runs in two places:

- **On Vercel:** `api/index.py` plus `vercel.json`. Every push to `main` deploys. Uploads are capped at 4.4 MB (Vercel's request limit). Files are converted on the server and not stored. The AI layer is not offered there.
- **On this machine:** `.venv\Scripts\python.exe -m synesthetic serve` (add `--tailscale` to reach it from your phone over your Tailscale network). Up to 60 MB, nothing leaves the machine.

The app has six tabs, one under each color bar:

- **How it works** explains the idea in three steps and lists what gets a color, then shows famous writing (the Constitution, the Declaration of Independence, the Gettysburg Address, the Bill of Rights, the Emancipation Proclamation, Sonnet 18, Pride and Prejudice) and everyday samples already colored. Switches change the highlight style, color scheme, grammar layer, color-blind palette, theme and spacing on the page as you watch; the chips under it hide or show each category. The examples are pre-rendered with the grammar layer by `tools/build_showcase.py` into `synesthetic/static/showcase.json`; add one by dropping a `.md` file in `synesthetic/examples/`, listing it in `examples.toml` and running the tool.
- **Synesthesize** adds the colors on top of a PDF, Word or Excel file and gives the same kind of file back (Keep the original layout, on by default). PDFs get highlight notes over the matched words, so pages, fonts and pictures are untouched and any PDF app can hide them. Word files have the matched words recolored in place, with ALL CAPS and larger sizes where set. Excel files color number and date cells and the matched words in text cells; formulas stay, charts and pictures are not kept. Turn the switch off, or pick a .txt/.md/.doc file, and the text is pulled into a new colored page instead. **Choose what to color (Roller)** opens the file first (PDF: its real pages with the text laid over them; Word and Excel: their text) so you select the parts to color; the colors show while you drag, and only those parts are colored in the file (`layout_units` and `only` in `synesthetic/overlay.py`). Below: a quick how-to strip and your recent files as thumbnails, which open in a window you can zoom.
- **Free Rain** is a text box that grows as you type, with lists, checklists, headings, bold, italic, and word spacing, line spacing and margins. Auto color colors as you go; Roller colors only what you select (the colors roll on while you drag). Save, download as a colored page, copy, or make a full page through the converter. Calm rain falls behind it (the Rain button, or Reduce motion, turns it off).
- **Editor** sets color schemes (Standard, Pastel, Vivid, Warm, Cool, or your own), each category's colors, ALL CAPS and size, the highlight style and size, and fonts, with a live preview. The **Word Bank** holds your own words, each with its own look (font color, highlight, font, size, ALL CAPS, bold, italic, underline); with its switch on, they are found in every document and win over their category.
- **Saved** keeps documents in this browser: Saved, Recent (the last 40) and Deleted (removed for good after 30 days), as a list or thumbnails, with search, rename, keep, download, delete with undo, and restore.
- **Settings**: theme, color-blind safe colors, coloring the app's own text, reduce motion, which tab opens first, install, export and import of your settings (also usable with `--style` on the command line), and storage.

Warnings show in ALL CAPS and numbers a little larger by default (`case` and `scale` in `lenses/default.toml`); Editor changes this per category, and converted pages and Word files follow it.

**On a computer** pages spread into two columns. Drop a file anywhere or paste one, Ctrl/Cmd+Enter colors it, Ctrl/Cmd+S saves in Free Rain, Esc closes a window.

**Install it** on a phone (Safari: Share, then Add to Home Screen; Chrome: Add to Home screen) or a computer (Chrome or Edge: Install app in Settings, or Install in the address bar) and it opens in its own window with its own icon. Installed with Chrome or Edge on a computer, it also shows up under "Open with" for the supported files. The icons are drawn by `tools/make_icons.py` into `synesthetic/static/`.

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
