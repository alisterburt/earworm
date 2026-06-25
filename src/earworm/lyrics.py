"""Lyric transcription + forced alignment of the vocal stem (isolated env)."""

from __future__ import annotations

import json
from pathlib import Path

from .utils import log, run

_RUNNER = Path(__file__).parent / "_lyrics_runner.py"

DEFAULT_MODEL = "large-v3"

# Whisper's stock end-of-audio hallucinations over trailing silence/reverb.
_HALLUCINATIONS = {
    "thank you.", "thank you", "thanks for watching.", "thanks for watching",
    "you", "you.", "bye.", "bye", "♪", ".",
}


def transcribe_lyrics(
    vocal_wav: Path,
    work_json: Path,
    model: str = DEFAULT_MODEL,
    onsets: list[float] | None = None,
) -> dict | None:
    """Transcribe + forced-align a vocal stem to {language, segments[]}.

    `onsets` are the vocal stem's MIDI note starts; when given, word timings are
    snapped onto nearby sung onsets for tightness. Returns None on failure so the
    pipeline can continue without lyrics.
    """
    try:
        run(["uv", "run", "--script", str(_RUNNER), str(vocal_wav), str(work_json), model])
        data = json.loads(work_json.read_text())
        drop_hallucinations(data)
        if onsets:
            snap_to_onsets(data, onsets)
        return data
    except Exception as exc:  # noqa: BLE001
        log(f"lyric transcription failed ({exc!r}); continuing without lyrics")
        return None


def drop_hallucinations(data: dict, tail_gap: float = 6.0) -> dict:
    """Remove whisper's trailing filler (e.g. 'Thank you.') hallucinated over the
    outro. Only drops a generic last segment isolated well after the real lyrics."""
    segs = (data or {}).get("segments", [])
    while len(segs) >= 2:
        last, prev = segs[-1], segs[-2]
        generic = last.get("text", "").strip().lower() in _HALLUCINATIONS
        isolated = last.get("start", 0) - prev.get("end", 0) > tail_gap
        if generic and isolated:
            segs.pop()
        else:
            break
    return data


def snap_to_onsets(data: dict, onsets: list[float], window: float = 0.12) -> dict:
    """Nudge word starts onto nearby sung-note onsets for musical tightness.

    `onsets` are vocal-stem MIDI note starts (when notes are actually sung). After
    forced alignment a word is usually within a beat of its note; snapping the
    start to the nearest onset inside `window` seconds locks lyric and melody
    together. Conservative + monotonic: only small shifts, never past the next
    word, and end is dragged along so durations stay positive.
    """
    if not onsets:
        return data
    onsets = sorted(onsets)
    import bisect

    prev_start = -1.0
    for seg in (data or {}).get("segments", []):
        for w in seg.get("words") or []:
            s = w.get("start")
            if s is None:
                continue
            i = bisect.bisect_left(onsets, s)
            cand = [onsets[j] for j in (i - 1, i) if 0 <= j < len(onsets)]
            near = min(cand, key=lambda o: abs(o - s), default=None)
            if near is not None and abs(near - s) <= window and near > prev_start:
                dur = max(0.08, (w.get("end") or s) - s)
                w["start"] = round(near, 3)
                w["end"] = round(near + dur, 3)
            prev_start = w["start"]
        ws = seg.get("words") or []
        if ws:
            seg["start"] = ws[0]["start"]
            seg["end"] = max(seg.get("end", 0), ws[-1]["end"])
    return data
