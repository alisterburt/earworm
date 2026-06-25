"""End-to-end orchestration: Logic project -> MIDI/analysis -> content assets.

Input is a saved Logic Pro project folder. Stems, tempo, key, time signature, the
beat grid and the chord track are read straight from the project (see `logic.py`);
chops only adds what Logic doesn't give us: per-stem MIDI (basic-pitch), lyrics
(whisper) and section/motif analysis (Claude).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import librosa
import numpy as np

from . import audio as audio_stage
from . import library as library_stage
from . import logic as logic_stage
from . import lyrics as lyrics_stage
from . import meta as meta_stage
from . import midi_process
from . import motifs as motifs_stage
from . import sections as sections_stage
from . import stems as stems_stage
from . import transcribe as transcribe_stage
from .utils import STEM_ORDER, ensure_dir, log

# Melodic stems worth transcribing; drums are pitch-less so basic-pitch is noisy.
MELODIC_STEMS = {"vocals", "piano", "guitar", "bass", "other"}

DEFAULT_CONTENT = Path("web/public/content")


def process(
    project_folder: Path,
    out_root: Path = DEFAULT_CONTENT,
    drums_midi: bool = False,
    lyrics: bool = True,
    whisper_model: str = lyrics_stage.DEFAULT_MODEL,
    transcode: bool = True,
    keep_wav: bool = False,
    sections: bool = True,
    motifs: bool = True,
) -> Path:
    proj = logic_stage.find_project(project_folder)
    song_id = meta_stage.slugify(proj.name)
    song_dir = ensure_dir(out_root / song_id)
    log(f"=== processing Logic project {proj.name} -> {song_dir} ===")

    # 1. Read everything Logic already computed.
    meta_info = logic_stage.read_metadata(proj.metadata_plist)
    key_info = meta_info["key"]
    beat_info = logic_stage.read_beats(proj.mamd, meta_info["time_signature"]["numerator"]) \
        if proj.mamd else {"beats": [], "downbeats": []}

    # 2. Master (full mix) + copy Logic's stems verbatim.
    if proj.mix is None:
        raise FileNotFoundError(f"no full-mix mp3/m4a in {proj.audio_files}")
    master = stems_stage.prepare_master(proj.mix, song_dir)
    stems_dir = ensure_dir(song_dir / "stems")
    stem_paths: dict[str, str] = {}
    for name, src in proj.stems.items():
        dest = stems_dir / f"{name}.wav"
        shutil.copy2(src, dest)
        stem_paths[name] = str(dest.relative_to(song_dir))
    log(f"copied stems: {', '.join(stem_paths)}")

    # Load the master mono once for the analysis stages.
    y, sr = librosa.load(str(master), sr=None, mono=True)
    duration = float(len(y) / sr)
    master_ref_rms = float(np.percentile(librosa.feature.rms(y=y)[0], 95))
    peaks = audio_stage.peaks_envelope(y)

    chord_spans = logic_stage.read_chords(proj.project_data, duration)
    # Key from Logic's signature track (handles mid-song key changes), cleaned into
    # regions >20s / the dominant key. Falls back to MetaData's initial key.
    raw_regions = logic_stage.read_key_regions(proj.project_data, beat_info["beats"], meta_info["tempo"], duration)
    if not raw_regions:
        raw_regions = [{"start": 0.0, "end": round(duration, 4), **key_info}]
    key_info, regions = logic_stage.clean_key_regions(raw_regions)
    logic_stage.respell_chords(chord_spans, key_info)  # flats/sharps to match the key
    log(f"key: {key_info['name']} | {len(regions)} region(s): {[r['name'] for r in regions]}")

    # 3. Metadata + cover art (iTunes lookup keyed off the folder name).
    log("resolving metadata + cover art")
    meta = meta_stage.resolve_metadata(proj.name, song_dir, key_info)

    # 4. Per-stem: presence, MIDI transcription + cleanup (display order).
    ordered = [n for n in STEM_ORDER if n in stem_paths]
    ordered += [n for n in stem_paths if n not in ordered]
    stems_out: dict[str, dict] = {}
    for name in ordered:
        rel_wav = stem_paths[name]
        present, level, active = audio_stage.stem_presence(song_dir / rel_wav, master_ref_rms)
        entry: dict = {"present": present, "level": level, "active_frac": active}
        if name in MELODIC_STEMS or (name == "drums" and drums_midi):
            midi = transcribe_stage.transcribe_stem(song_dir / rel_wav, song_dir / "midi")
            if midi is not None:
                raw = transcribe_stage.parse_notes(midi)
                entry["midi"] = str(midi.relative_to(song_dir))
                entry["notes"] = raw
                clean = midi_process.process_notes(
                    raw, song_dir / rel_wav, beat_info["beats"], master_ref_rms=master_ref_rms,
                    monophonic=name in {"vocals", "bass"},
                    pitch_range=midi_process.PITCH_RANGES.get(name),
                )
                entry["notes_clean"] = clean
                clean_mid = song_dir / "midi" / f"{name}.clean.mid"
                transcribe_stage.notes_to_midi(clean, clean_mid)
                entry["midi_clean"] = str(clean_mid.relative_to(song_dir))
        stems_out[name] = entry
        log(f"  stem {name}: present={present} level={level}dB")

    # 5. Lyrics from the vocal stem (transcribe + forced-align + onset-snap).
    lyrics_data = None
    if lyrics and "vocals" in stem_paths:
        log(f"transcribing + aligning lyrics (whisper {whisper_model} + wav2vec2)")
        work = song_dir / "_lyrics.json"
        vnotes = stems_out.get("vocals", {}).get("notes_clean") or \
            stems_out.get("vocals", {}).get("notes") or []
        onsets = [n["s"] for n in vnotes]
        lyrics_data = lyrics_stage.transcribe_lyrics(
            song_dir / stem_paths["vocals"], work, model=whisper_model, onsets=onsets
        )
        work.unlink(missing_ok=True)

    # 6. Transcode WAVs -> m4a (analysis above ran on the WAVs).
    if transcode and audio_stage.ffmpeg_available():
        log("transcoding audio to AAC/m4a")
        audio_rel = audio_stage.transcode(master, song_dir, audio_stage.MASTER_BITRATE, keep_wav)
        for name in ordered:
            stems_out[name]["audio"] = audio_stage.transcode(
                song_dir / stem_paths[name], song_dir, audio_stage.STEM_BITRATE, keep_wav
            )
    else:
        audio_rel = master.name
        for name in ordered:
            stems_out[name]["audio"] = stem_paths[name]

    # 7. Manifest. Preserve the original "added" timestamp across re-processing.
    prior = song_dir / "analysis.json"
    added = json.loads(prior.read_text()).get("added") if prior.exists() else None
    manifest = {
        "id": song_id,
        "name": proj.name,
        "title": meta["title"],
        "artist": meta["artist"],
        "album": meta["album"],
        "cover": meta["cover"],
        "added": added or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "logic",
        "audio": audio_rel,
        "duration": round(duration, 3),
        "sample_rate": sr,
        "tempo": meta_info["tempo"],
        "time_signature": meta_info["time_signature"],
        "key": key_info,
        "keys": regions,
        "beats": beat_info["beats"],
        "downbeats": beat_info["downbeats"],
        "peaks": peaks,
        "chords": chord_spans,
        "lyrics": lyrics_data,
        "stems": stems_out,
    }

    # 7b. LLM analysis (sections, then motifs which can use the sections).
    if sections:
        log("detecting sections (claude)")
        manifest["sections"] = sections_stage.detect_sections(manifest)
    if motifs:
        log("detecting motifs (claude, features + piano-roll images)")
        manifest["motifs"] = motifs_stage.detect_motifs(manifest, song_dir)

    (song_dir / "analysis.json").write_text(json.dumps(manifest, indent=2))
    log(f"wrote {song_dir / 'analysis.json'}")

    # 8. Refresh the library index.
    library_stage.build_library(out_root)
    log(f"=== done: {song_id} ===")
    return song_dir
