"""Beat/tempo ("smart tempo") detection via beat_this, run in an isolated env."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .utils import log, run

_RUNNER = Path(__file__).parent / "_beats_runner.py"


def detect_beats(audio_path: Path, work_json: Path) -> dict:
    """Run beat_this and return {tempo, beats[], downbeats[]}.

    Falls back to librosa's beat tracker if the isolated beat_this run fails
    (e.g. no network for the model download).
    """
    try:
        run(["uv", "run", "--script", str(_RUNNER), str(audio_path), str(work_json)])
        data = json.loads(work_json.read_text())
        beats = data["beats"]
        downbeats = data["downbeats"]
    except Exception as exc:  # noqa: BLE001 - any failure -> librosa fallback
        log(f"beat_this failed ({exc!r}); falling back to librosa beat tracking")
        beats, downbeats = _librosa_beats(audio_path)

    return {"tempo": _tempo_from_beats(beats), "beats": beats, "downbeats": downbeats}


def _tempo_from_beats(beats: list[float]) -> float:
    if len(beats) < 2:
        return 0.0
    median_period = float(np.median(np.diff(beats)))
    return round(60.0 / median_period, 2) if median_period > 0 else 0.0


def _librosa_beats(audio_path: Path) -> tuple[list[float], list[float]]:
    import librosa

    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    _, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    beats = librosa.frames_to_time(beat_frames, sr=sr).tolist()
    # No downbeat model in the fallback: approximate every 4th beat as a downbeat.
    downbeats = beats[::4]
    return [round(b, 4) for b in beats], [round(b, 4) for b in downbeats]
