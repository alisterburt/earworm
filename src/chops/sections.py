"""Song-section detection via the local Claude CLI (chords + lyrics by bar)."""

from __future__ import annotations

from .llm import ask_claude_json
from .utils import log


def _ranges(bars: list[int]) -> str:
    """Compress [1,2,3,7,8] -> '1-3, 7-8'."""
    if not bars:
        return "none"
    out, start, prev = [], bars[0], bars[0]
    for b in bars[1:]:
        if b == prev + 1:
            prev = b
        else:
            out.append(f"{start}-{prev}" if start != prev else f"{start}")
            start = prev = b
    out.append(f"{start}-{prev}" if start != prev else f"{start}")
    return ", ".join(out)


def _bar_of(t: float, downbeats: list[float]) -> int:
    bar = 1
    for i, db in enumerate(downbeats):
        if t >= db:
            bar = i + 1
        else:
            break
    return bar


def detect_sections(analysis: dict) -> list[dict]:
    downbeats = analysis.get("downbeats") or []
    chords = analysis.get("chords") or []
    lyrics = analysis.get("lyrics")
    duration = analysis["duration"]
    nbars = len(downbeats)
    if nbars < 4:
        return []

    # one representative chord per bar
    bars = []
    for i, db in enumerate(downbeats):
        end = downbeats[i + 1] if i + 1 < len(downbeats) else duration
        labs = [c["label"] for c in chords if c["start"] < end and c["end"] > db and c["label"] != "N"]
        bars.append(labs[0] if labs else "-")
    bar_str = " ".join(f"{i+1}:{c}" for i, c in enumerate(bars))

    lyr_block = ""
    if lyrics and lyrics.get("segments"):
        lines = [f"bar{_bar_of(s['start'], downbeats)}: {s['text']}" for s in lyrics["segments"]]
        lyr_block = "\nLyrics by bar:\n" + "\n".join(lines)

    # per-bar stem activity from cleaned MIDI (which instruments are actually playing)
    melodic = [n for n, s in analysis.get("stems", {}).items()
               if s.get("present") and (s.get("notes_clean") or s.get("notes"))]
    act_block = ""
    for name in melodic:
        notes = analysis["stems"][name].get("notes_clean") or []
        active = sorted({_bar_of(n["s"], downbeats) for n in notes})
        act_block += f"\n{name} plays in bars: {_ranges(active)}"
    activity = ("\nInstrument activity (from transcribed MIDI):" + act_block) if act_block else ""

    prompt = (
        "You are a music structure analyst. Segment this song into its sections.\n"
        f"Key: {analysis['key']['name']}, tempo {analysis['tempo']} BPM, {nbars} bars.\n"
        f"Chord per bar: {bar_str}{lyr_block}{activity}\n\n"
        "Only call a section 'Instrumental' if NO vocals play in it — use the vocal "
        "activity and lyrics above to place verses/choruses where the voice is present.\n"
        "Return ONLY a JSON array. Each item: "
        '{"name": "Intro|Verse N|Pre-Chorus|Chorus|Bridge|Solo|Instrumental|Outro", '
        '"startBar": int, "endBar": int, "summary": "<=12 words", '
        '"pattern": "repeating chord pattern in roman numerals, e.g. I-V-vi-IV"}. '
        "Cover every bar in order with no gaps or overlaps; startBar of the first is 1, "
        f"endBar of the last is {nbars}."
    )
    secs = ask_claude_json(prompt)
    if not isinstance(secs, list):
        log("sections: no result")
        return []

    out = []
    for s in secs:
        try:
            sb = max(1, int(s["startBar"]))
            eb = min(nbars, int(s["endBar"]))
        except Exception:  # noqa: BLE001
            continue
        start = downbeats[sb - 1]
        end = downbeats[eb] if eb < len(downbeats) else duration
        out.append({
            "name": str(s.get("name", "")),
            "start": round(start, 3), "end": round(end, 3),
            "startBar": sb, "endBar": eb,
            "summary": str(s.get("summary", "")),
            "pattern": str(s.get("pattern", "")),
        })
    log(f"sections: {len(out)} found")
    return out
