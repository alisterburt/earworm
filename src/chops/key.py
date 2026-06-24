"""Key-signature detection via librosa chroma + Krumhansl-Schmuckler profiles."""

from __future__ import annotations

import librosa
import numpy as np

from .utils import NOTE_NAMES

# Krumhansl-Schmuckler key profiles (relative weights of each pitch class).
KS_MAJOR = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
KS_MINOR = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)


_MAJOR_SCALE = {0, 2, 4, 5, 7, 9, 11}
_MINOR_SCALE = {0, 2, 3, 5, 7, 8, 10}  # natural minor


def key_from_chords(chords: list[dict]) -> dict | None:
    """Estimate key from the chord progression (more reliable than chroma for
    functional pop/rock). Scores each of 24 keys by how much chord-duration sits
    on diatonic roots, with a bonus for the tonic chord to break the
    major/relative-minor tie. Returns None if there are no usable chords.
    """
    from .roman import _pc  # local import to avoid a cycle

    parsed: list[tuple[int, float]] = []
    for c in chords:
        label = c.get("label", "N")
        if label in ("N", "NC", "X"):
            continue
        root = _pc(label.split("/")[0])
        if root is None:
            continue
        parsed.append((root, float(c["end"]) - float(c["start"])))
    total = sum(w for _, w in parsed)
    if total <= 0:
        return None

    best = None
    for tonic in range(12):
        for mode, scale in (("major", _MAJOR_SCALE), ("minor", _MINOR_SCALE)):
            score = 0.0
            for root, w in parsed:
                deg = (root - tonic) % 12
                if deg in scale:
                    score += w
                if deg == 0:
                    score += w * 0.5  # tonic-chord bonus
            frac = score / total
            if best is None or frac > best[0]:
                best = (frac, tonic, mode)

    frac, tonic, mode = best
    name = NOTE_NAMES[tonic]
    return {"tonic": name, "mode": mode, "name": f"{name} {mode}",
            "confidence": round(frac, 4), "source": "chords"}


def detect_key(y: np.ndarray, sr: int) -> dict:
    """Return the best-matching key as {tonic, mode, name, confidence}.

    Correlates the track's mean chroma vector against all 24 rotations of the
    major/minor KS profiles and picks the highest correlation. Confidence is the
    margin between the best and second-best candidate (0..1-ish).
    """
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    profile = chroma.mean(axis=1)
    profile = profile - profile.mean()

    maj = KS_MAJOR - KS_MAJOR.mean()
    minor = KS_MINOR - KS_MINOR.mean()

    scores: list[tuple[float, str, int]] = []
    for tonic in range(12):
        scores.append((float(np.corrcoef(np.roll(maj, tonic), profile)[0, 1]), "major", tonic))
        scores.append((float(np.corrcoef(np.roll(minor, tonic), profile)[0, 1]), "minor", tonic))

    scores.sort(reverse=True)
    best_score, mode, tonic = scores[0]
    second = scores[1][0]
    tonic_name = NOTE_NAMES[tonic]
    confidence = round(max(0.0, best_score - second), 4)
    return {
        "tonic": tonic_name,
        "mode": mode,
        "name": f"{tonic_name} {mode}",
        "confidence": confidence,
    }
