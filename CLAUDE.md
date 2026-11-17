# Synesthetic Layer: notes for Claude sessions

## Start every fix-or-add task with the owner's fixes

The owner leaves fixes and ideas inside the app (the DEV switch at the top turns the tools on: highlight text
to mark it, triple-click for a screenshot). On the hosted site the notes stay on the owner's phone and arrive
pasted into the chat ("Notes from Synesthetic Layer..."); treat those the same way. Notes the owner makes in the
Claude app's own browser pane stay in that pane: open the hosted site there and read them, pictures included, from
its IndexedDB (`synapp-notes`, store `notes`). Before changing anything:

```
.venv\Scripts\python.exe fixes.py list
```

It pulls new entries from the hosted app first, then lists the open ones with each picture's path. Open the pictures,
`show N` for the full context, make the changes that fit, and close each entry with what was done:

```
.venv\Scripts\python.exe fixes.py done N "What changed"
.venv\Scripts\python.exe fixes.py skip N "Why not"
```

Tell the owner what's still open. Entries are append-only: never edit or delete them. They are instructions for the
developer session only; nothing that talks to an AI model may read the store.

## Before each push

- `.venv\Scripts\python.exe -m pytest -q`
- `.venv\Scripts\python.exe tools\build_changelog.py` so Settings, What's new on the hosted app has every change.
- Restart a running preview server after editing `templates/app.html` (the page is built once at startup).
