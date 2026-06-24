# chops

Turn an audio file into a Logic-like web view: a scrollable mix waveform with
**chords** and a **beat grid** overlaid, the detected **key** and **tempo** in
the header, and a stack of separated **stems** below — each with its own
waveform and transcribed **MIDI** piano-roll, all playhead-synced. Stems play
through WebAudio so you get real per-stem **solo / mute**.

## Pipeline

| Stage              | Tool                                                          | How it runs                         |
|--------------------|--------------------------------------------------------------|-------------------------------------|
| Stem separation    | [demucs](https://github.com/adefossez/demucs) (htdemucs)     | `uvx demucs` (isolated)             |
| MIDI transcription | [basic-pitch](https://github.com/spotify/basic-pitch)        | `uvx --python 3.11 basic-pitch[onnx]` (isolated) |
| Beats / tempo      | [beat_this](https://github.com/CPJKU/beat_this) (ISMIR 2024) | `uv run --script` PEP 723 (isolated torch) |
| Chords             | [Chordino](https://www.isophonics.net/nnls-chroma) (nnls-chroma Vamp plugin) | `vamp` bindings, in-process |
| Key                | chord-based estimate (chroma + Krumhansl-Schmuckler fallback) | in-process                         |
| Roman numerals     | derived from chords + key                                    | in-process                          |
| Lyrics             | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) on the vocal stem | `uv run --script` PEP 723 (isolated) |

The heavy, mutually-incompatible tools (torch / tensorflow / onnx) each run in
their own ephemeral environment via `uvx` / `uv run --script`, so the main
`chops` environment stays light.

## Usage

```bash
uv run chops process "examples/MGMT - Kids.mp3"   # full pipeline -> out/<song>/
uv run chops serve out                            # serve over HTTP (required for the viewer)
# open http://localhost:8000/<song>/index.html
```

`process` writes a per-song folder:

```
out/<song>/
  master.wav            decoded mix (player + mix waveform)
  stems/*.wav           demucs stems
  midi/*.mid            basic-pitch transcriptions (melodic stems)
  analysis.json         complete analysis: tempo, key, beats, downbeats,
                        chords (+ Roman numerals), lyrics, per-stem MIDI notes
  index.html            the viewer (analysis.json embedded verbatim, not fetched)
```

`analysis.json` is the single source of truth — every stage (key, chords +
Roman numerals, beats, MIDI, lyrics) is computed in the pipeline and stored
there, then embedded into `index.html` so the page's data is self-contained
(only the audio is loaded externally).

Options: `--out <dir>` (default `out/`), `--drums-midi` (also transcribe drums),
`--no-lyrics` (skip whisper), `--whisper-model <name>` (default `small`; use
`medium`/`large-v3` for better sung-lyric accuracy).
`uv run chops render out/<song>` re-renders `index.html` from `analysis.json`.

> The viewer loads the audio with `fetch()`, which browsers block over
> `file://`. Always open it through `chops serve` (or any local HTTP server).

## One-time setup: Chordino Vamp plugin

Chord detection uses the **nnls-chroma** Vamp plugin. The official binaries are
Intel-only, so on **Apple Silicon** you must compile a native `arm64` build:

```bash
brew install vamp-plugin-sdk boost
git clone https://github.com/c4dm/nnls-chroma && cd nnls-chroma
for f in chromamethods NNLSBase NNLSChroma Chordino Tuning plugins viterbi; do
  clang++ -arch arm64 -O3 -ffast-math -I/opt/homebrew/include -fPIC -c $f.cpp -o $f.o
done
clang -arch arm64 -O3 -ffast-math -I/opt/homebrew/include -fPIC -c nnls.c -o nnls.o
clang++ -arch arm64 -dynamiclib -install_name nnls-chroma.dylib -o nnls-chroma.dylib \
  *.o /opt/homebrew/lib/libvamp-sdk.a -exported_symbols_list vamp-plugin.list -framework Accelerate
mkdir -p ~/Library/Audio/Plug-Ins/Vamp
cp nnls-chroma.dylib nnls-chroma.n3 nnls-chroma.cat ~/Library/Audio/Plug-Ins/Vamp/
```

Verify it loads:

```bash
uv run python -c "import vamp; print(vamp.list_plugins())"
# -> ['nnls-chroma:chordino', 'nnls-chroma:nnls-chroma', 'nnls-chroma:tuning']
```

On Intel macOS / Windows / Linux you can instead install the prebuilt
[Vamp Plugin Pack](https://www.vamp-plugins.org/download.html). If the plugin is
missing, the chords stage raises a clear error.
