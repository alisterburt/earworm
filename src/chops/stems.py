"""Stem separation via demucs (htdemucs), run as an isolated uvx tool."""

from __future__ import annotations

import shutil
from pathlib import Path

import librosa
import soundfile as sf

from .utils import ensure_dir, log, run


def prepare_master(audio_path: Path, song_dir: Path) -> Path:
    """Decode the input to a browser-friendly master.wav for the viewer."""
    master = song_dir / "master.wav"
    y, sr = librosa.load(str(audio_path), sr=None, mono=False)
    data = y.T if y.ndim > 1 else y  # soundfile wants (frames, channels)
    sf.write(str(master), data, sr)
    log(f"wrote {master.name} ({sr} Hz)")
    return master


def separate(audio_path: Path, song_dir: Path) -> dict[str, str]:
    """Run demucs and collect the four stems into song_dir/stems/.

    Returns {stem_name: relative_wav_path}.
    """
    tmp = ensure_dir(song_dir / "_demucs")
    # htdemucs_6s adds guitar + piano to the usual vocals/drums/bass/other.
    # Recent torchaudio routes save() through torchcodec (needs a matching
    # ffmpeg); pin below that and add soundfile so demucs can write WAV stems.
    run(
        [
            "uvx", "--with", "torchaudio<2.8", "--with", "soundfile",
            "demucs", "-n", "htdemucs_6s", "-o", str(tmp), str(audio_path),
        ]
    )

    # demucs writes <tmp>/<model>/<track-name>/<stem>.wav
    model_dirs = [d for d in tmp.iterdir() if d.is_dir()]
    if not model_dirs:
        raise RuntimeError(f"demucs produced no output under {tmp}")
    track_dirs = [d for d in model_dirs[0].iterdir() if d.is_dir()]
    if not track_dirs:
        raise RuntimeError(f"demucs produced no track output under {model_dirs[0]}")
    track_dir = track_dirs[0]

    stems_dir = ensure_dir(song_dir / "stems")
    stems: dict[str, str] = {}
    for wav in sorted(track_dir.glob("*.wav")):
        dest = stems_dir / wav.name
        shutil.move(str(wav), str(dest))
        stems[wav.stem] = str(dest.relative_to(song_dir))

    shutil.rmtree(tmp, ignore_errors=True)
    log(f"separated stems: {', '.join(stems)}")
    return stems
