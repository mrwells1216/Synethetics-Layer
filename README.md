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
| `--grammar` | grammar layer (nouns, verbs, adjectives, adverbs), offline: spaCy where it is installed, our own word library (`lenses/library.toml`) where it is not. Busy: off by default |
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
- **Synesthesize** adds the colors on top of a PDF, Word or Excel file and gives the same kind of file back (Keep the original layout, on by default). In PDFs the matched words are redrawn right where they were, in your colors, the category's font cues, ALL CAPS and sizes (and your Word Bank looks): each old word is covered with the color of the paper around it and the new one is set on top in a standard PDF font (Helvetica, Times or Courier, chosen to match), with its background behind it. A bigger word first narrows its letters to keep its place, so nothing else on the page moves. Turn off Change the letters to get light highlight notes on top instead, which any PDF app can hide. Word files have the matched words recolored in place, with fonts, bold, ALL CAPS and larger sizes. Excel files color number and date cells and the matched words in text cells; formulas stay, charts and pictures are not kept. Turn the switch off, or pick a .txt/.md/.doc file, and the text is pulled into a new colored page instead. **Choose what to color (Roller)** opens the file first (PDF: its real pages with the text laid over them; Word and Excel: their text) so you select the parts to color; the colors show while you drag, and only those parts are colored in the file (`layout_units` and `only` in `synesthetic/overlay.py`). Below: a quick how-to strip and your recent files as thumbnails, which open in a window you can zoom. **Try a sample** loads a 3-page made-up weekly S&P 500 market wrap as a PDF or Word file (built by `tools/build_samples.py` from `synesthetic/examples/market-wrap.md`; every number in it is invented).
- **Free Rain** is a text box that grows as you type, with lists, checklists, headings, bold, italic, and word spacing, line spacing and margins. Auto color colors as you go; Roller colors only what you select (the colors roll on while you drag). Save, download as a colored page, copy, or make a full page through the converter. Calm rain falls behind it (the Rain button, or Reduce motion, turns it off).
- **Editor** decides every look on real text. A passage (built-in examples, or your own pasted text, colored once and kept on the device) redraws live. Every content and grammar category has a switch (off everywhere) and a look: colors, weight (normal, bold, thin), italic, ALL CAPS, size, underline style and color. Selecting words in the passage offers a **custom look** for them. **Specialties** (Core plus named sets such as Analyst) lay changes over Core for one kind of reading; the active one is used for conversions. Color schemes, highlight style and size, and fonts live under Page. The **Word Bank** holds your own words and phrases, each with its own look or counted as a category ("treat *encounter* as a noun"); with its switch on, they are found in every document and win over the detector.
- **Saved** keeps documents in this browser: Saved, Recent (the last 40) and Deleted (removed for good after 30 days), as a list or thumbnails, with search, rename, keep, download, delete with undo, and restore.
- **Settings**: theme, color-blind safe colors, coloring the app's own text, reduce motion, which tab opens first, install, export and import of your settings (also usable with `--style` on the command line), storage, **What's new** and **Developer mode**.
  - **What's new** is the change log: every change that reached `main`, newest first, tagged Added, Changed, Fixed or Removed from its words, with a filter. Running here it reads `git log` live; the hosted app reads `synesthetic/static/changelog.json` (run `tools\build_changelog.py` before each push) and puts the deployed commit on top from Vercel's `VERCEL_GIT_COMMIT_SHA` / `_MESSAGE` (`synesthetic/changelog.py`).
  - **Developer mode** is a layer for fixing the app (`synesthetic/static/dev.js`). Highlight text and press Fix/idea; triple-click (triple-tap on a phone) for a screenshot frame you can move and resize, with a comment and Good / Not good / Fix/idea; the DEV button opens live requests, errors and warnings, your fixes, and the app's state. A screenshot is the page drawing itself (a clone through an SVG `foreignObject`, CSS settled against the live page, web fonts and images inlined, inner frames drawn too), so no screen-share prompt; if a browser can't draw it, the text and comment are saved without the picture. Entries are append-only and go to `python fixes.py list` for the next Claude session (see `CLAUDE.md`). Running here they land in `%LOCALAPPDATA%\SynestheticLayer\fixes` (or `$SYNESTHETIC_DATA`); hosted, in the private Vercel Blob store connected to the project, and only devices opened once with the dev link (`python fixes.py pair <site>` makes the key; the site needs it as `SYNESTHETIC_DEV_KEY`) can save or read them.

Warnings show in ALL CAPS and numbers a little larger by default (`case` and `scale` in `lenses/default.toml`); Editor changes this per category, and converted pages and Word files follow it.

**On a computer** pages spread into two columns. Drop a file anywhere or paste one, Ctrl/Cmd+Enter colors it, Ctrl/Cmd+S saves in Free Rain, Esc closes a window.

**Install it** on a phone (Safari: Share, then Add to Home Screen; Chrome: Add to Home screen) or a computer (Chrome or Edge: Install app in Settings, or Install in the address bar) and it opens in its own window with its own icon. Installed with Chrome or Edge on a computer, it also shows up under "Open with" for the supported files. The icons are drawn by `tools/make_icons.py` into `synesthetic/static/`.

The page lives in `synesthetic/templates/app.html`; its look is described in `docs/design-system.md`. Runtime dependencies are in `requirements.txt`.

## Claude chat replies

The mod lives in `chat-mod/synesthetic-chat/` (copy it into `~/.claude/dev-mods/<session id>/` to load it in a session) and draws assistant replies with the same lens: the content types, plus the grammar looks from our own word library (the meaning layer needs a model, so it is not in chat). It follows the looks set in the app's Editor: the app sends them to its store (`/api/style-put`; on the hosted site the device needs the dev link), and the mod reads them at session start from this computer's app folder (`style.json`) or the hosted site (`remote.json` holds its address and key), keeping the last ones seen for sessions offline. Options (style, theme, palette, grammar on or off, categories off) are in the mod's config and apply until the Editor's looks arrive. After editing `lenses/default.toml` or `lenses/library.toml`, run `.venv\Scripts\python.exe tools\export_lens.py` and `tools\parity.py` to refresh the mod and confirm it still matches.

## Layout

- `synesthetic/extract/`: one reader per format into a common document model
- `synesthetic/annotate.py`, `grammar.py`, `meaning.py`, `layers.py`: the three layers and how they combine
- `synesthetic/library.py` and `lenses/library.toml`: our own word library (small words, verbs, adjectives, adverbs, the owner's pinned words) and the tagger that reads it; `tools/library_check.py` measures it against spaCy
- `synesthetic/colorcheck.py`: contrast and color-blindness checks (tested)
- `lenses/default.toml`: the single source of categories, colors, cues
- `synesthetic/fixes.py` (and `fixes.py` at the top): developer-mode fixes store and CLI; `synesthetic/changelog.py`: the change log
- `tools/`: lens export for the mod, parity check, showcase, samples, icons, change log
- `tests/`: `.venv\Scripts\python.exe -m pytest -q`

## Known limits

- Scanned PDFs have no text; flagged, no OCR.
- Legacy `.doc` is read as plain text (no headings or tables) unless LibreOffice is installed. Not tested on a real `.doc`.
- The AI layer needs a working `claude` login; if it can't run, the page renders without it.
- Names are a rough heuristic and start switched off.
- The chat mod is untested inside the live app until it loads; it has not been seen on a phone.
