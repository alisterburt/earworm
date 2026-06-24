"""Transcode the analysis WAVs to compact AAC/m4a for the viewer.

WAV stems are ~70 MB each; the analysis stages need them, but the viewer only
needs something a browser can stream and decode. AAC/m4a is small, universally
supported (Chrome/Safari/Firefox) and imports cleanly into DAWs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .utils import run

# Bitrates: a touch higher for the full mix you actually listen to.
MASTER_BITRATE = "192k"
STEM_BITRATE = "128k"


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


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
