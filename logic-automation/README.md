# earworm-logic

Automates Logic Pro processing of an mp3 by driving the macOS UI (AppleScript /
System Events). Standalone for now; intended to fold into the earworm pipeline later.

## Usage

```sh
./earworm-logic "<file>.mp3" [--artist "X"] [--song "Y"] [--save-open]
```

- The project name (`<Artist> - <Song>`) is derived from the mp3 filename via
  `claude -p` (cleans up messy YouTube-style names). Override with `--artist`/`--song`.
- Saves a folder-organized project to `~/Music/Logic/earworm/<Artist> - <Song>/`
  (override the base dir with `EARWORM_LOGIC_DIR`).

## What it does

1. Quits any running Logic (discards open project — pass `--save-open` to save instead).
2. Launches Logic, creates an Empty Project (one Software Instrument track).
3. Adds an audio track and imports the mp3.
4. If the "audio file contains tempo information" alert appears → **Don't Import**.
5. `Edit ▸ Tempo ▸ Apply Region Tempo to Project Tempo`.
6. Analyze Chords (`⌃⌥⌘2`), Analyze Key Signature (`⌃⌥⌘3`, answering **No** to the
   "chords follow key change?" prompt), Stem Splitter / Separate all Stems (`⌃⌥⌘4`).
7. `Save As` into the earworm dir, organized as a Folder with audio copied in.

## Requirements / caveats

- **Logic Pro 12** (developed against 12.2).
- The `⌃⌥⌘2/3/4` shortcuts are this user's custom Key Command assignments
  (Analyze Chords / Analyze Key Signature / Stem Splitter Preset 6). If key
  commands change, update `lib/automate.applescript`.
- The controlling terminal needs macOS **Accessibility** permission (System
  Settings ▸ Privacy & Security ▸ Accessibility) to send UI events.
- It drives the real UI: **keep hands off the keyboard/mouse while it runs**, and
  Logic must stay frontmost.

## Notes for future maintenance

Logic's modern dialogs are quirky for automation; lessons baked into the script:
- Custom-dialog buttons (e.g. New Tracks "Create") often fail `click`; pressing
  the default key (`return`) or `AXPress` is more reliable.
- The tempo alert's button is `Don’t Import` with a **curly apostrophe** — match
  by prefix (`name starts with "Don"`), not an exact string.
- The Save As dialog is a standalone window named `Save`, not a sheet; "Folder"
  organization and "copy Audio files" are already the defaults.
- The arrange area doesn't expose regions to Accessibility, so region operations
  are done via menu items / key commands rather than synthetic right-clicks.
