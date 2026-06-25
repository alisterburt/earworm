"""Transcode the analysis WAVs to compact AAC/m4a for the viewer.

WAV stems are ~70 MB each; the analysis stages need them, but the viewer only
needs something a browser can stream and decode. AAC/m4a is small, universally
supported (Chrome/Safari/Firefox) and imports cleanly into DAWs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import librosa
import numpy as np

from .utils import run

# Bitrates: a touch higher for the full mix you actually listen to.
MASTER_BITRATE = "192k"
STEM_BITRATE = "128k"


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def peaks_envelope(y: np.ndarray, n: int = 2000) -> list[float]:
    """Downsampled abs-max envelope (0..1) for fast waveform drawing."""
    if len(y) == 0:
        return []
    pad = (-len(y)) % n
    if pad:
        y = np.concatenate([y, np.zeros(pad, dtype=y.dtype)])
    env = np.abs(y.reshape(n, -1)).max(axis=1)
    peak = float(env.max()) or 1.0
    return [round(float(v / peak), 4) for v in env]


def stem_presence(
    wav: Path, master_ref_rms: float, mix_drop_db: float = 45.0, min_active_frac: float = 0.04
) -> tuple[bool, float, float]:
    """Is this stem actually audible in the mix? Returns (present, level_db, active_frac).

    A stem counts as present if it spends >= `min_active_frac` of the song within
    `mix_drop_db` of the mix's loud level. Near-silent bleed (e.g. Aviram piano)
    falls below this and is hidden by the UI.
    """
    y, _ = librosa.load(str(wav), sr=None, mono=True)
    rms = librosa.feature.rms(y=y)[0]
    ref = master_ref_rms if master_ref_rms and master_ref_rms > 0 else float(np.max(rms))
    db_mix = librosa.amplitude_to_db(rms, ref=ref)
    active_frac = float((db_mix > -mix_drop_db).mean())
    level = float(db_mix.max())
    return active_frac >= min_active_frac, round(level, 1), round(active_frac, 3)


def transcode(src_wav: Path, song_dir: Path, bitrate: str, keep_src: bool = False) -> str:
    """Transcode src_wav to a sibling .m4a; return its path relative to song_dir.

    Deletes the source WAV unless keep_src is set.
    """
    dst = src_wav.with_suffix(".m4a")
    run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(src_wav),
            "-c:a", "aac", "-b:a", bitrate, "-movflags", "+faststart", str(dst),
        ]
    )
    if not keep_src:
        src_wav.unlink(missing_ok=True)
    return str(dst.relative_to(song_dir))
