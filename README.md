# earworm

A music-learning app: point it at a **saved Logic Pro project** and earworm pulls
out the stems and Logic's own tempo/key/beat/chord analysis, transcribes each stem
to MIDI, and adds structure + motif analysis so you can **understand a song well
enough to arrange it for any instrument**. A Python pipeline produces the data; a
Vite + Svelte app (GitHub-Pages hostable) presents it as a single-screen workstation.

Logic's Stem Splitter and its chord/tempo/key detection are higher quality than
the open-source equivalents, and a saved project already contains all of it — so
earworm reads it straight off disk (the binary chord track is reverse-engineered;
see `src/earworm/logic.py`) rather than recomputing it.

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

You can build this project automatically from a bare audio file with
`earworm ingest` (see Usage), which drives the Logic Pro UI to import, analyze
(tempo/chords/key) and stem-split, then save it. Or prepare one by hand: save a
Logic project **as a folder** (with assets) and run Logic's Stem Splitter so the
stems land in `Audio Files/`. Either way, earworm reads:

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
ephemeral environment via `uvx` / `uv run --script`, so the main `earworm`
environment stays light. The LLM stages shell out to the local `claude` CLI (your
Claude Code login — no API key); Roman numerals are computed in the browser.

## Usage

```bash
# 0. (optional) ingest a song end-to-end: drive Logic Pro to build the project,
#    then run the full pipeline. macOS + Logic Pro only; needs Accessibility
#    permission for the terminal, and Logic must stay frontmost while it runs.
#    TARGET is either a local audio file...
uv run earworm ingest "/path/to/MGMT - Kids.mp3"
#    ...or a search query (top YouTube match is downloaded via yt-dlp):
uv run earworm ingest "mgmt kids"
#    name is parsed from the filename (claude -p); override with --artist/--song.
#    --build-only stops after saving the Logic project (skips downstream stages).

# 1. process an existing Logic project folder -> content assets (web/public/content/<id>/ + library.json)
uv run earworm process "/path/to/Artist - Title"

# 2. run the app
cd web && npm install && npm run dev          # http://localhost:5173
```

`ingest` saves the Logic project to `~/Music/Logic/earworm/<Artist> - <Song>`
(override base dir with `EARWORM_LOGIC_DIR`), overwriting any existing one, then
hands it to `process`. See `logic-automation/README.md` for the UI-automation
details. It accepts the same downstream flags as `process`.

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
Rebuild just the index with `uv run earworm library`.

## Song storage: Cloudflare R2 (CDN)

The local content dir is the working copy (dev always reads it); deployed apps
fetch songs from an R2 bucket instead of shipping ~0.5 GB of audio to GitHub
Pages. One-time setup:

1. Create an R2 bucket and enable public access (Settings → r2.dev subdomain,
   or attach a custom domain).
2. Create an S3 API token (R2 → Manage R2 API Tokens → Object Read & Write),
   then `cp .env.example .env` and fill in `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
   `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`.
3. Put the bucket's public URL in `web/.env.production` as `VITE_CONTENT_BASE`
   (production builds then read songs from the CDN and leave content out of
   `dist`; leave it empty to keep the old bundle-everything behaviour).

Then after processing songs:

```bash
uv run earworm sync             # mirror web/public/content -> the bucket
```

`sync` uploads only changed files (MD5 vs remote ETag), sets content types and
cache headers, and (re)applies bucket CORS — required because stems play
through `createMediaElementSource`, which silences cross-origin audio without
CORS. `--dry-run` previews; `--delete` removes remote files for songs deleted
locally.

## Deploy (GitHub Pages)

```bash
cd web && npm run deploy        # builds with base /earworm/ and pushes dist to the gh-pages branch
```
Needs a GitHub remote on the repo; the built `dist/` is served statically —
just the app when `VITE_CONTENT_BASE` is set, app + content + audio otherwise.
Hash routing means no 404 config is required. For a different repo name, set
`EARWORM_BASE=/<repo>/`.
