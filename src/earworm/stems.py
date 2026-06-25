"""Master preparation for the viewer (stems now come from the Logic project)."""

from __future__ import annotations

from pathlib import Path

import librosa
import soundfile as sf

from .utils import log


def prepare_master(audio_path: Path, song_dir: Path) -> Path:
    """Decode the full mix to a browser-friendly master.wav for the viewer."""
    master = song_dir / "master.wav"
    y, sr = librosa.load(str(audio_path), sr=None, mono=False)
    data = y.T if y.ndim > 1 else y  # soundfile wants (frames, channels)
    sf.write(str(master), data, sr)
    log(f"wrote {master.name} ({sr} Hz)")
    return master
