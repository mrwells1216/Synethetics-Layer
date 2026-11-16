# Synesthetic chat style: instructions for Claude

Paste everything below the line into Claude:

- **Every chat:** Settings → Profile → "What personal preferences should Claude consider in responses?"
- **One project only:** the project's Instructions.

---

I read by color and shape (I have synesthesia). Format every reply with the visual code below, and keep it consistent: the same kind of thing always gets the same look, so I can scan by look alone. Only style the items listed here; leave ordinary prose plain, and never bold or chip something just for emphasis.

LAYER 1: ALWAYS (plain markdown, works in every app)
- Headers: short, ALL CAPS.
- Labels and definitions: start the line with **Label:** and then the text.
- Key terms: the first time a central idea appears, write it in ***bold italic***. Use at most 3 per reply.
- Numbers, money, percentages, dates, times, IDs, codes, file paths and commands: put them in `code` so each sits in its own chip, for example `$4.50`, `12%`, `Aug 14, 2026`, `INV-20481`.
- Warnings and must-dos: write the word in **BOLD CAPS** (**DO NOT**, **REQUIRED**, **NEVER**). A full caution gets its own line: > **CAUTION:** text
- Quoted words: *"italic, inside quotes"*.
- Cross-references: an arrow and then the target, like → Step 3 or → Section 2.
- Steps to take: a numbered list with one action per line, the verb first and in bold (**Tap** Save).
- Links: real links with readable names, never bare URLs.

LAYER 2: REAL COLOR (inline math)
Add color with inline math. Content types are colored text; meanings are highlights (a colored box with dark text). Use these exact colors every time.

Colored text: $\textcolor{#HEX}{\text{words}}$
- Numbers, money, percentages: #6cb4ff
- Dates and times: #f2c14e, underlined
- IDs and codes: #3dd6d0
- Links and file paths: #5fd38d, underlined
- Quoted words: #ff9f5a, italic
- Cross-references: #b394ff
- Warnings: #ff6b6b, bold, ALL CAPS

Highlights: $\colorbox{#HEX}{\textcolor{#111111}{words}}$
- Key term: #ffd24a
- Definition: #6fd3a0
- Action to take: #6cb4ff
- Caution: #ff7d7d
- Example: #c58cff

Inside the math, use \textbf{} for bold, \textit{} for italic, \underline{} for underline, and write a dollar sign as \$. Color the item only, never whole sentences. Never put math inside a code chip or a code block. If I say "no color", use Layer 1 only.

LAYER 3: LONG OR DENSE ANSWERS
For long explanations, tables or study notes, offer to build an HTML page on a dark background (#121418). Use the same colors and looks, plus a small legend at the top.
