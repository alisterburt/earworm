"""Convert absolute chord labels (Chordino) to Roman numerals in a given key.

This is a pragmatic functional analysis, not a full theory engine: it parses the
chord root + quality, finds the scale degree relative to the key tonic, and
renders an uppercase/lowercase numeral with the usual quality marks. Anything it
can't parse falls back to the literal label.
"""

from __future__ import annotations

import re

_LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# Scale-degree numerals per mode (uppercase base; case set from chord quality).
_MAJOR = {0: "I", 1: "♭II", 2: "II", 3: "♭III", 4: "III", 5: "IV",
          6: "♯IV", 7: "V", 8: "♭VI", 9: "VI", 10: "♭VII", 11: "VII"}
_MINOR = {0: "I", 1: "♭II", 2: "II", 3: "III", 4: "♯III", 5: "IV",
          6: "♯IV", 7: "V", 8: "VI", 9: "♯VI", 10: "VII", 11: "♯VII"}

_ROOT_RE = re.compile(r"^([A-G])([#b]?)(.*)$")


def _pc(note: str) -> int | None:
    m = _ROOT_RE.match(note)
    if not m:
        return None
    pc = _LETTER_PC[m.group(1)]
    if m.group(2) == "#":
        pc += 1
    elif m.group(2) == "b":
        pc -= 1
    return pc % 12


def _quality_and_ext(rest: str) -> tuple[str, str]:
    """Return (quality, extension) where quality in {maj,min,dim,aug}."""
    r = rest
    if "dim" in r or "°" in r or r.startswith("o"):
        quality = "dim"
    elif "aug" in r or "+" in r:
        quality = "aug"
    elif r.startswith("maj") or r.startswith("M"):
        quality = "maj"
    elif r.startswith("m") or r.startswith("-"):
        quality = "min"
    else:
        quality = "maj"
    ext = ""
    for tok in ("maj7", "sus4", "sus2", "9", "7", "6"):
        if tok in r:
            ext = tok
            break
    return quality, ext


def to_roman(label: str, tonic: str, mode: str) -> str:
    """Roman numeral for `label` in the key (tonic, mode). Falls back to label."""
    if not label or label in ("N", "NC", "X"):
        return label

    root_part, _, bass_part = label.partition("/")
    m = _ROOT_RE.match(root_part)
    tonic_pc = _pc(tonic)
    if m is None or tonic_pc is None:
        return label
    root_pc = _pc(root_part)
    if root_pc is None:
        return label

    degree = (root_pc - tonic_pc) % 12
    table = _MAJOR if mode == "major" else _MINOR
    numeral = table[degree]
    quality, ext = _quality_and_ext(m.group(3))

    if quality in ("min", "dim"):
        numeral = numeral.lower()
    if quality == "dim":
        numeral += "°"
    elif quality == "aug":
        numeral += "+"
    numeral += ext

    # Slash chord: append the bass note's scale degree (uppercase numeral).
    if bass_part:
        bass_pc = _pc(bass_part)
        if bass_pc is not None:
            numeral += "/" + table[(bass_pc - tonic_pc) % 12]
    return numeral


def annotate_chords(chords: list[dict], key: dict) -> None:
    """Add a 'roman' field to each chord span in place."""
    tonic, mode = key.get("tonic", "C"), key.get("mode", "major")
    for c in chords:
        c["roman"] = to_roman(c.get("label", "N"), tonic, mode)
