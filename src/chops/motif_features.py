"""Deterministic motif extraction from the decoded chords + cleaned MIDI.

Motifs are computed straight from the analysis data (chord cycles, vocal/bass
degree sequences) so they ALWAYS match what's shown in the viewer — the LLM later
only names and describes them, never invents the notes. This mirrors the (perfect)
per-section motif logic in the frontend.

Each motif carries `tokens`: [{deg, note, pc}] so the UI can show either the
degree/roman form or the absolute note/chord form (Notes/Degrees toggle), coloured
by pitch class either way.
"""

from __future__ import annotations

import re

from . import roman
from . import sonofield as sf

_FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
_FLAT_MAJ, _FLAT_MIN = {5, 10, 3, 8, 1, 6}, {2, 7, 0, 5, 10, 3}


def _note_names(key: dict) -> list[str]:
    pc = sf.note_pc(key["tonic"])
    flats = pc in (_FLAT_MIN if key.get("mode") == "minor" else _FLAT_MAJ)
    return _FLAT_NAMES if flats else sf.NOTE_NAMES


def section_type(name: str) -> str:
    """'Verse 1' -> 'Verse'; collapses numbered repeats to a single type."""
    return re.sub(r"\s*\d+\s*$", "", name or "").strip() or (name or "Section")


def _section_chords(chords: list[dict], s: dict) -> list[str]:
    out: list[str] = []
    for c in chords:
        if c.get("label") in (None, "N"):
            continue
        mid = (c["start"] + c["end"]) / 2
        if s["start"] <= mid < s["end"]:
            if not out or out[-1] != c["label"]:
                out.append(c["label"])
    return out


def _cycle(seq: list) -> list:
    """Shortest repeating period covering seq (tolerates ~1-in-6 mismatches)."""
    n = len(seq)
    if n < 4:
        return seq
    for p in range(1, n // 2 + 1):
        miss = sum(1 for i in range(p, n) if seq[i] != seq[i % p])
        if miss / (n - p) <= 0.17:
            return seq[:p]
    return seq


def _harmonic_stems(analysis: dict) -> list[str]:
    order = ["piano", "guitar", "other", "bass"]
    return [n for n in order if analysis["stems"].get(n, {}).get("present")]


def _chord_tokens(labels: list[str], key: dict) -> list[dict]:
    """deg=roman, note=absolute chord, pc=root pitch class (for colour)."""
    toks = []
    for lbl in labels:
        rpc = roman._pc(lbl.partition("/")[0])
        toks.append({"deg": roman.to_roman(lbl, key["tonic"], key["mode"]), "note": lbl, "pc": rpc})
    return toks


def _phrase_tokens(notes: list[dict], tonic_pc: int, names: list[str], max_notes: int = 12) -> list[dict]:
    """deg=scale degree, note=note name, pc=pitch class; collapses immediate repeats."""
    out: list[dict] = []
    for n in sorted(notes, key=lambda n: n["s"]):
        pc = n["pitch"] % 12
        deg = sf.DEGREE_LABELS[(pc - tonic_pc) % 12]
        if out and out[-1]["deg"] == deg:
            continue
        out.append({"deg": deg, "note": names[pc], "pc": pc})
        if len(out) >= max_notes:
            break
    return out


def _motif(type_, tokens, where, bars, instruments) -> dict:
    return {"type": type_, "tokens": tokens,
            "degrees": " ".join(t["deg"] for t in tokens),
            "labels": " ".join(t["note"] for t in tokens),
            "where": where, "bars": bars, "instruments": instruments}


def progression_motifs(analysis: dict) -> list[dict]:
    chords = analysis.get("chords") or []
    sections = analysis.get("sections") or []
    key = analysis["key"]
    insts = _harmonic_stems(analysis)
    seen: dict[str, dict] = {}
    for s in sections:
        cyc = _cycle(_section_chords(chords, s))
        if len(cyc) < 2:
            continue
        rkey = " ".join(roman.to_roman(lbl, key["tonic"], key["mode"]) for lbl in cyc)
        seen.setdefault(rkey, {"cyc": cyc, "secs": []})["secs"].append(s)
    motifs = []
    for ent in seen.values():
        types = sorted({section_type(x["name"]) for x in ent["secs"]})
        bars = "; ".join(f"{x['name']} (bars {x.get('startBar','?')}-{x.get('endBar','?')})"
                         for x in ent["secs"][:4])
        motifs.append(_motif("progression", _chord_tokens(ent["cyc"], key), ", ".join(types), bars, insts))
    return motifs


def _melodic_motifs(analysis: dict, stem: str, kind: str, max_types: int) -> list[dict]:
    s_stem = analysis["stems"].get(stem, {})
    notes = s_stem.get("notes_clean") or s_stem.get("notes") or []
    if not notes:
        return []
    tonic_pc = sf.note_pc(analysis["key"]["tonic"])
    names = _note_names(analysis["key"])
    out, seen_types = [], set()
    for s in analysis.get("sections") or []:
        st = section_type(s["name"])
        if st in seen_types:
            continue
        seg = [n for n in notes if s["start"] <= n["s"] < s["end"]]
        toks = _phrase_tokens(seg, tonic_pc, names)
        if len(toks) >= 3:
            seen_types.add(st)
            bars = f"{s['name']} (bars {s.get('startBar','?')}-{s.get('endBar','?')})"
            out.append(_motif(kind, toks, st, bars, [stem]))
        if len(out) >= max_types:
            break
    return out


def melody_motifs(analysis: dict, melodic: list[str]) -> list[dict]:
    lead = "vocals" if "vocals" in melodic else (melodic[0] if melodic else None)
    return _melodic_motifs(analysis, lead, "melody", 4) if lead else []


def bass_motifs(analysis: dict) -> list[dict]:
    return _melodic_motifs(analysis, "bass", "bass", 2) if analysis["stems"].get("bass", {}).get("present") else []


def extract_motifs(analysis: dict, melodic: list[str]) -> list[dict]:
    return progression_motifs(analysis) + melody_motifs(analysis, melodic) + bass_motifs(analysis)
