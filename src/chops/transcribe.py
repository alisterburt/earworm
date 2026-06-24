"""MIDI transcription per stem via basic-pitch, run as an isolated uv tool."""

from __future__ import annotations

from pathlib import Path

import pretty_midi

from .utils import ensure_dir, log, run


def transcribe_stem(stem_wav: Path, midi_dir: Path) -> Path | None:
    """Transcribe one stem to MIDI with basic-pitch.

    basic-pitch writes ``<name>_basic_pitch.mid`` into the output directory; we
    rename it to ``<stem>.mid``. Returns the midi path, or None on failure.
    """
    ensure_dir(midi_dir)
    # basic-pitch has no Python 3.13 / TensorFlow wheels, so pin the isolated env
    # to 3.11 and use the ONNX backend (arm64 wheels). resampy still imports the
    # removed pkg_resources, so pull in setuptools<81 which still ships it.
    try:
        run(
            [
                "uvx", "--python", "3.11",
                "--from", "basic-pitch[onnx]",
                "--with", "setuptools<81",
                "basic-pitch", str(midi_dir), str(stem_wav), "--save-midi",
            ]
        )
    except Exception as exc:  # noqa: BLE001
        log(f"basic-pitch failed for {stem_wav.name}: {exc!r}")
        return None

    produced = midi_dir / f"{stem_wav.stem}_basic_pitch.mid"
    if not produced.exists():
        log(f"basic-pitch produced no midi for {stem_wav.name}")
        return None

    final = midi_dir / f"{stem_wav.stem}.mid"
    produced.replace(final)
    return final


def notes_to_midi(notes: list[dict], path: Path) -> None:
    """Write a flat note list back out as a single-instrument MIDI file."""
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    for n in notes:
        inst.notes.append(
            pretty_midi.Note(
                velocity=int(n["vel"]), pitch=int(n["pitch"]),
                start=float(n["s"]), end=float(n["e"]),
            )
        )
    pm.instruments.append(inst)
    pm.write(str(path))


def parse_notes(midi_path: Path) -> list[dict]:
    """Flatten a MIDI file to a list of {s, e, pitch, vel} notes."""
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    notes: list[dict] = []
    for instrument in pm.instruments:
        for n in instrument.notes:
            notes.append(
                {
                    "s": round(float(n.start), 4),
                    "e": round(float(n.end), 4),
                    "pitch": int(n.pitch),
                    "vel": int(n.velocity),
                }
            )
    notes.sort(key=lambda n: n["s"])
    return notes
