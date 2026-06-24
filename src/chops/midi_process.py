"""Clean up noisy basic-pitch transcriptions.

Three passes, in order:
  1. volume gate  - drop notes sitting in (near-)silent parts of the stem, which
     is where basic-pitch tends to hallucinate. The floor is derived from the
     stem's own loudness distribution in its non-silent regions.
  2. pitch outliers - drop notes far outside the stem's pitch range (stray
     octave jumps), via an IQR fence.
  3. quantize     - snap note starts/ends to a 16th-note grid built from the
     detected beats (so it follows tempo changes).

The raw notes are always preserved by the caller; this returns a new list.
"""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np


def process_notes(
    notes: list[dict],
    stem_wav: Path,
    beats: list[float],
    *,
    master_ref_rms: float | None = None,
    gate_drop_db: float = 35.0,
    mix_drop_db: float = 45.0,
    outlier_iqr: float = 2.0,
    subdiv: int = 4,
) -> list[dict]:
    if not notes:
        return []
    y, sr = librosa.load(str(stem_wav), sr=None, mono=True)
    notes = _gate_by_volume(
        notes, y, sr, drop_db=gate_drop_db,
        master_ref_rms=master_ref_rms, mix_drop_db=mix_drop_db,
    )
    notes = _remove_pitch_outliers(notes, k=outlier_iqr)
    notes = _quantize(notes, beats, subdiv=subdiv)
    return notes


def _gate_by_volume(
    notes: list[dict],
    y: np.ndarray,
    sr: int,
    drop_db: float,
    master_ref_rms: float | None = None,
    mix_drop_db: float = 45.0,
) -> list[dict]:
    """Keep a note only if the stem has real energy during it.

    Two gates, both must pass:
      - stem-relative: peak loudness within `drop_db` of the stem's own 90th-pct
        non-silent level (catches silent gaps inside an otherwise-present stem).
      - mix-relative: the stem's absolute level must come within `mix_drop_db` of
        the mix's loud level. demucs stems share the master's amplitude scale, so
        a stem that's near-silent across the whole song (bleed) sits far below the
        mix and gets dropped wholesale. Skipped when `master_ref_rms` is None.
    """
    hop = 512
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    db_self = librosa.amplitude_to_db(rms, ref=np.max)  # 0 dB at the stem's loudest
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)

    active = db_self[db_self > -50.0]  # ignore true silence when estimating level
    if active.size == 0:
        return notes
    self_floor = float(np.percentile(active, 90)) - drop_db

    db_mix = None
    if master_ref_rms and master_ref_rms > 0:
        db_mix = librosa.amplitude_to_db(rms, ref=master_ref_rms)  # vs the mix's loud level

    kept = []
    for n in notes:
        i0 = int(np.searchsorted(times, n["s"]))
        i1 = max(i0 + 1, int(np.searchsorted(times, n["e"])))
        if float(db_self[i0:i1].max()) < self_floor:
            continue
        if db_mix is not None and float(db_mix[i0:i1].max()) < -mix_drop_db:
            continue
        kept.append(n)
    return kept


def _remove_pitch_outliers(notes: list[dict], k: float) -> list[dict]:
    """Drop notes whose pitch is an IQR-fence outlier (stray octave jumps)."""
    if len(notes) < 8:
        return notes
    pitches = np.array([n["pitch"] for n in notes])
    q1, q3 = np.percentile(pitches, [25, 75])
    iqr = q3 - q1
    if iqr < 1:  # too tight a range to call anything an outlier
        return notes
    lo, hi = q1 - k * iqr, q3 + k * iqr
    return [n for n in notes if lo <= n["pitch"] <= hi]


def _build_grid(beats: list[float], subdiv: int) -> np.ndarray:
    """16th-note grid: subdivide each beat interval `subdiv` ways."""
    grid: list[float] = []
    for i in range(len(beats) - 1):
        b0, b1 = beats[i], beats[i + 1]
        step = (b1 - b0) / subdiv
        grid.extend(b0 + k * step for k in range(subdiv))
    grid.append(beats[-1])
    return np.array(grid)


def _quantize(notes: list[dict], beats: list[float], subdiv: int) -> list[dict]:
    if len(beats) < 2:
        return notes
    grid = _build_grid(beats, subdiv)
    out = []
    for n in notes:
        s = float(grid[np.argmin(np.abs(grid - n["s"]))])
        e = float(grid[np.argmin(np.abs(grid - n["e"]))])
        if e <= s:  # collapsed to zero -> extend to the next grid point
            after = grid[grid > s]
            e = float(after[0]) if after.size else s + (n["e"] - n["s"])
        out.append({**n, "s": round(s, 4), "e": round(e, 4)})
    return out
