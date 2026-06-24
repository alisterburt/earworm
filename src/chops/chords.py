"""Chord detection via the Chordino (nnls-chroma) Vamp plugin.

We drive the plugin directly through the `vamp` bindings rather than the
`chord-extractor` wrapper, which is unmaintained and breaks on Python 3.13
(it imports the removed `pkg_resources`). The engine and results are identical.

Requires the nnls-chroma Vamp plugin to be installed (see README). On Apple
Silicon this means a locally compiled arm64 `nnls-chroma.dylib`.
"""

from __future__ import annotations

import librosa
import vamp

CHORDINO_KEY = "nnls-chroma:chordino"


def chordino_available() -> bool:
    return CHORDINO_KEY in vamp.list_plugins()


def detect_chords(audio_path: str, duration: float) -> list[dict]:
    """Return chord spans [{start, end, label}] covering the track.

    Chordino emits a chord *change* at each timestamp; we expand consecutive
    changes into spans, the last one running to the track duration. The "N"
    label means "no chord".
    """
    if not chordino_available():
        raise RuntimeError(
            "Chordino Vamp plugin not found. Install nnls-chroma (see README) "
            f"and ensure it loads: vamp.list_plugins() -> {vamp.list_plugins()}"
        )

    y, sr = librosa.load(audio_path, sr=None, mono=True)
    result = vamp.collect(y, sr, CHORDINO_KEY, output="simplechord")
    items = result["list"]

    spans: list[dict] = []
    for i, item in enumerate(items):
        start = float(item["timestamp"])
        end = float(items[i + 1]["timestamp"]) if i + 1 < len(items) else duration
        spans.append(
            {
                "start": round(start, 4),
                "end": round(end, 4),
                "label": item.get("label", "N"),
            }
        )
    return spans
