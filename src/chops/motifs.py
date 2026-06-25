"""Motifs to learn: deterministic extraction (degrees/chords/bars from the decoded
data) + an LLM pass that only NAMES and DESCRIBES them (never alters the notes)."""

from __future__ import annotations

from pathlib import Path

from . import motif_features
from .llm import ask_claude_json
from .utils import log

_TYPE_WORD = {"progression": "progression", "melody": "vocal hook", "bass": "bass line", "lick": "lick"}


def _fallback_name_desc(m: dict) -> tuple[str, str]:
    where = m.get("where") or "the song"
    if m["type"] == "progression":
        return f"{where} progression", f"{m['labels']} ({m['degrees']}) — the chord loop under {where}."
    word = _TYPE_WORD.get(m["type"], "motif")
    return f"{where} {word}", f"The {word} over {where}, in scale degrees {m['degrees']}."


def detect_motifs(analysis: dict, song_dir: Path) -> list[dict]:
    melodic = [
        n for n, s in analysis["stems"].items()
        if s.get("present") and (s.get("notes_clean") or s.get("notes"))
    ]
    motifs = motif_features.extract_motifs(analysis, melodic)
    if not motifs:
        return []
    for i, m in enumerate(motifs):
        m["id"] = i

    # LLM pass: name + describe + prioritise. Degrees/bars/instruments are fixed.
    catalog = "\n".join(
        f"- id {m['id']} [{m['type']}] degrees={m['degrees']!r}"
        + (f" chords={m['labels']!r}" if m.get("labels") else "")
        + f" where={m['where']!r} instruments={m['instruments']}"
        for m in motifs
    )
    prompt = (
        "You are helping someone LEARN this song to arrange it. Below are motifs already "
        "extracted from the actual chords/MIDI — the degrees and locations are CORRECT and "
        "MUST NOT be changed.\n\n"
        f"Key: {analysis['key']['name']}, {analysis['tempo']} BPM.\n\n"
        f"Motifs:\n{catalog}\n\n"
        "For each motif worth learning, return {\"id\": <id>, \"name\": \"short memorable name\", "
        "\"description\": \"1-2 sentences on what it is and why it matters for arranging\"}. "
        "Drop redundant/uninteresting ones. Order most important first. Return ONLY a JSON array."
    )
    enrich = {}
    res = ask_claude_json(prompt, timeout=180)
    if isinstance(res, list):
        for r in res:
            if isinstance(r, dict) and "id" in r:
                enrich[r["id"]] = r

    out = []
    order = [r["id"] for r in res if isinstance(r, dict) and r.get("id") in {m["id"] for m in motifs}] \
        if isinstance(res, list) else []
    order += [m["id"] for m in motifs if m["id"] not in order]  # append any the LLM dropped/missed
    by_id = {m["id"]: m for m in motifs}
    for mid in order:
        m = by_id[mid]
        e = enrich.get(mid)
        if isinstance(res, list) and not e:
            continue  # LLM deliberately dropped it
        name, desc = (e.get("name"), e.get("description")) if e else (None, None)
        if not name or not desc:
            name, desc = _fallback_name_desc(m)
        out.append({"type": m["type"], "name": name, "description": desc,
                    "tokens": m["tokens"], "degrees": m["degrees"], "labels": m["labels"],
                    "bars": m["bars"], "instruments": m["instruments"]})
    log(f"motifs: {len(out)} ({len(motifs)} extracted)")
    return out
