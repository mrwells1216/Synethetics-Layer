# Design system

The app's look is made from the reader's own category colors, so customizing the colors re-themes the app itself.

## Signature elements

- **Wordmark:** "Synesthetic" in the heading font, each letter in a category color (warning, quote, date, link, id, number, reference: a rainbow order). "LAYER" sits under it in spaced small caps.
- **Spectrum strip:** one bar per category under the header; tapping it opens Customize.
- **Paper preview:** the drop zone shows a sheet whose lines are already colored, so it explains what the tool does.
- **Spectrum button:** Convert is a gradient of the same colors; its text color is whichever of near-black or white has the better worst-case contrast across the gradient.
- **Self-colored text:** the app's own instructions, labels and messages run through the lens's content patterns in the browser (a port of `annotate.py`), in the chosen highlight style. Copy names real examples ("dates like Aug 14") so it shows. A switch turns it off (`synapp.uitext`).
- **Aura:** two faint radial glows (quote and number colors at about 11 %) behind everything.

## Tokens

| Token | Dark | Light |
|---|---|---|
| `--bg` | `#0e1014` | `#f6f3ec` (warm paper) |
| `--surface` / `--raised` | `#15181e` / `#1c2028` | `#fdfbf6` / `#ece8de` |
| `--fg` / `--muted` | `#eceef2` / `#8d95a3` | `#1b1d22` / `#5f6672` |
| `--line` | `#272c36` | `#dcd6c9` |
| `--doc-bg` | `#14161b` | `#fbfbf8` (matches converted pages) |
| `--c-<category>`, `--on-<category>` | from the lens or the user | from the lens or the user |
| `--font-body` / `--font-head` | Atkinson Hyperlegible / Fraunces by default | same |

Radii: 10, 14, 22 px. Pills are fully rounded. Motion is a single ease (`cubic-bezier(.2,.7,.2,1)`), off under reduced motion.

## Customization rules

- Every category has a dark-theme and a light-theme color. Changes apply to the standard palette only; the color-blind palette stays as designed.
- A color under 3:1 contrast with the page background gets a "Hard to read" note, but it is still allowed. The reader's own associations come first.
- Fonts come from a fixed list (`FONT_CHOICES` in `synesthetic/render.py`). Web fonts load from Google Fonts only when chosen; every stack falls back to a system font.
- Settings are stored in the browser (`synapp.style`). Highlight style and theme share `syn.mode` and `syn.theme` with converted pages, so a change in either place shows in both.
- The server accepts the style in an `X-Style` header and keeps only valid values: hex colors for known categories, listed font keys, size 80 to 150 %, known mode and theme. Export writes the same JSON, which the command line reads with `--style`.
