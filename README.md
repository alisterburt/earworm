# chops

A music-learning app: point it at a **saved Logic Pro project** and chops pulls
out the stems and Logic's own tempo/key/beat/chord analysis, transcribes each stem
to MIDI, and adds structure + motif analysis so you can **understand a song well
enough to arrange it for any instrument**. A Python pipeline produces the data; a
Vite + Svelte app (GitHub-Pages hostable) presents it as a single-screen workstation.

Logic's Stem Splitter and its chord/tempo/key detection are higher quality than
the open-source equivalents, and a saved project already contains all of it — so
chops reads it straight off disk (the binary chord track is reverse-engineered;
see `src/chops/logic.py`) rather than recomputing it.

Everything is themed on the **Sonofield** colour system — 12 hues keyed to scale
degree relative to the tonic, arranged by circle of fifths. MIDI notes are
coloured by degree, chords by their root.

- **Library** — Apple-Music-style grid (real cover art via iTunes), sorted by added.
- **Song workstation** — one screen: header transport; section-coloured overview
  waveform with a section band-strip; a Logic-style scrolling window (fixed
  playhead, bars, dual roman/absolute chords, lyrics phrase-by-phrase, loop select,
  2–32 bar zoom) with piano-roll + labelled keyboard; and a side rail of stems
  (mute / solo / show-in-roll), sections (jump list) and motifs to learn.
- Pitch-preserving speed, absolute/relative naming toggle, raw/clean MIDI, lyric search.

The app is behind a lightweight (non-secure) client-side password gate. **Password: `bleepbloop`.**

## Input: a Logic project folder

Save a Logic project **as a folder** (with assets) and run Logic's Stem Splitter so
the stems land in `Audio Files/`. chops reads:

```
<Artist - Title>/                     # folder name → artist/title + cover lookup
  Audio Files/
    *_Bass.wav … _Vocals.wav          # Logic Stem Splitter output (6 stems)
    *.mamd                            # Smart Tempo beat grid
    *.mp3                             # full mix (master)
  *.logicx/Alternatives/000/
    MetaData.plist                    # tempo, key, time signature
    ProjectData                       # chord track (decoded by logic.py)
```

## Pipeline

| Stage              | Source                                                       | How it runs                         |
|--------------------|--------------------------------------------------------------|-------------------------------------|
| Stems              | Logic Stem Splitter WAVs                                      | copied from the project             |
| Tempo / key / sig  | Logic `MetaData.plist`                                        | in-process (`logic.py`)             |
| Beat grid          | Logic Smart Tempo (`.mamd` → `ResU` JSON)                    | in-process (`logic.py`)             |
| Chords             | Logic chord track (`ProjectData`, reverse-engineered)        | in-process (`logic.py`)             |
| MIDI transcription | [basic-pitch](https://github.com/spotify/basic-pitch)        | `uvx --python 3.11 basic-pitch[onnx]` (isolated) |
| MIDI cleanup       | volume-gate + pitch-outlier removal + 16th-note quantize     | in-process (raw kept alongside)     |
| Cover + metadata   | iTunes Search API (folder name `Artist - Title`), generated fallback | in-process |
| Lyrics             | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) transcription (VAD off) + [whisperx](https://github.com/m-bain/whisperX) wav2vec2 forced alignment, snapped to vocal-note onsets | `uv run --script` PEP 723 (isolated) |
| Sections           | local `claude -p` over bar-by-bar chords + lyrics            | in-process (LLM)                    |
| Motifs             | programmatic MIDI features + piano-roll images → `claude -p` | in-process (LLM)                    |

The heavy tools (tensorflow / onnx for basic-pitch, faster-whisper) each run in an
ephemeral environment via `uvx` / `uv run --script`, so the main `chops`
environment stays light. The LLM stages shell out to the local `claude` CLI (your
Claude Code login — no API key); Roman numerals are computed in the browser.

## Usage

```bash
# 1. process a Logic project folder -> content assets (web/public/content/<id>/ + library.json)
uv run chops process "/path/to/Artist - Title"

# 2. run the app
cd web && npm install && npm run dev          # http://localhost:5173
```

`process` writes per-song content the app reads:

```
web/public/content/
  library.json            songs sorted by added (id, title, artist, cover, key, tempo)
  <id>/
    master.m4a  stems/*.m4a        AAC (analysis WAVs transcoded + removed)
    midi/*.mid  midi/*.clean.mid   raw + cleaned (gated, de-spiked, quantized) MIDI
    cover.jpg
    analysis.json                  key, time signature, beats/downbeats, chords,
                                   lyrics, peaks, per-stem MIDI notes, sections, motifs
```

Analysis runs on lossless WAVs, then transcodes to AAC (~10× smaller). `process`
options: `--drums-midi`, `--no-lyrics`, `--whisper-model <base|small|medium|large-v3>`,
`--no-sections`, `--no-motifs`, `--keep-wav`, `--no-transcode`, `--out <dir>`.
Rebuild just the index with `uv run chops library`.

## Deploy (GitHub Pages)

```bash
cd web && npm run deploy        # builds with base /chops/ and pushes dist to the gh-pages branch
```
Needs a GitHub remote on the repo; the built `dist/` (app + content + audio) is
served statically. Hash routing means no 404 config is required. For a different
repo name, set `CHOPS_BASE=/<repo>/`.
