"""End-to-end orchestration: audio -> stems -> MIDI -> analysis -> viewer."""

from __future__ import annotations

import json
from pathlib import Path

import librosa

from . import beats as beats_stage
from . import chords as chords_stage
from . import key as key_stage
from . import lyrics as lyrics_stage
from . import stems as stems_stage
from . import transcribe as transcribe_stage
from .render import render_song
from .roman import annotate_chords
from .utils import STEM_ORDER, ensure_dir, log

# Melodic stems worth transcribing; drums are pitch-less so basic-pitch is noisy.
MELODIC_STEMS = {"vocals", "piano", "guitar", "bass", "other"}


def process(
    audio_path: Path,
    out_root: Path,
    drums_midi: bool = False,
    lyrics: bool = True,
    whisper_model: str = lyrics_stage.DEFAULT_MODEL,
) -> Path:
    audio_path = audio_path.expanduser().resolve()
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    song_dir = ensure_dir(out_root / audio_path.stem)
    log(f"=== processing {audio_path.name} -> {song_dir} ===")

    # 1. Master + stems.
    master = stems_stage.prepare_master(audio_path, song_dir)
    stem_paths = stems_stage.separate(audio_path, song_dir)

    # Load the master mono once for the analysis stages.
    y, sr = librosa.load(str(master), sr=None, mono=True)
    duration = float(len(y) / sr)

    # 2. Harmonic + rhythmic analysis on the full mix.
    log("analyzing chords (Chordino / nnls-chroma)")
    chord_spans = chords_stage.detect_chords(str(master), duration)

    # Key: prefer the chord-based estimate (robust for functional music); fall
    # back to chroma/Krumhansl-Schmuckler when there are no usable chords.
    log("analyzing key (chord-based, chroma fallback)")
    key_info = key_stage.key_from_chords(chord_spans) or key_stage.detect_key(y, sr)

    # Roman-numeral labels, stored alongside the chords so analysis.json is complete.
    annotate_chords(chord_spans, key_info)

    log("analyzing beats/tempo (beat_this)")
    beats_work = song_dir / "_beats.json"
    beat_info = beats_stage.detect_beats(master, beats_work)
    beats_work.unlink(missing_ok=True)

    # 3. Per-stem MIDI transcription, emitted in display order (STEM_ORDER).
    ordered = [n for n in STEM_ORDER if n in stem_paths]
    ordered += [n for n in stem_paths if n not in ordered]  # any unexpected stems
    stems_out: dict[str, dict] = {}
    for name in ordered:
        rel_wav = stem_paths[name]
        entry: dict = {"wav": rel_wav}
        if name in MELODIC_STEMS or (name == "drums" and drums_midi):
            midi = transcribe_stage.transcribe_stem(song_dir / rel_wav, song_dir / "midi")
            if midi is not None:
                entry["midi"] = str(midi.relative_to(song_dir))
                entry["notes"] = transcribe_stage.parse_notes(midi)
        stems_out[name] = entry

    # 4. Lyrics: transcribe the (clean) vocal stem with whisper.
    lyrics_data = None
    if lyrics and "vocals" in stem_paths:
        log(f"transcribing lyrics (faster-whisper, model={whisper_model})")
        work = song_dir / "_lyrics.json"
        lyrics_data = lyrics_stage.transcribe_lyrics(
            song_dir / stem_paths["vocals"], work, model=whisper_model
        )
        work.unlink(missing_ok=True)

    # 5. Assemble manifest.
    manifest = {
        "name": audio_path.stem,
        "audio": master.name,
        "duration": round(duration, 3),
        "sample_rate": sr,
        "tempo": beat_info["tempo"],
        "key": key_info,
        "beats": beat_info["beats"],
        "downbeats": beat_info["downbeats"],
        "chords": chord_spans,
        "lyrics": lyrics_data,
        "stems": stems_out,
    }
    analysis_path = song_dir / "analysis.json"
    analysis_path.write_text(json.dumps(manifest, indent=2))
    log(f"wrote {analysis_path}")

    # 6. Render the viewer.
    render_song(song_dir)
    log(f"=== done: open {song_dir / 'index.html'} ===")
    return song_dir
