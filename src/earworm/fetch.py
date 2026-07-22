"""Fetch audio for a search query via yt-dlp (run ephemerally through uvx)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .utils import log


def download_audio(query: str, dest_dir: Path) -> Path:
    """Download the top YouTube match for `query` as an mp3 into `dest_dir`.

    Runs `uvx yt-dlp` so yt-dlp lives in its own ephemeral environment. The file
    keeps yt-dlp's default (video-title) name; downstream name parsing (claude -p)
    cleans that into '<Artist> - <Song>'. Returns the path to the mp3.
    """
    log(f"searching YouTube for: {query!r}")
    subprocess.run(
        [
            "uvx", "yt-dlp",
            "--no-playlist",
            "--extract-audio",
            "--audio-format", "mp3",
            f"ytsearch1:{query}",
        ],
        cwd=dest_dir,
        check=True,
    )
    mp3s = sorted(dest_dir.glob("*.mp3"))
    if not mp3s:
        raise RuntimeError(f"yt-dlp produced no mp3 for query: {query!r}")
    log(f"downloaded {mp3s[0].name}")
    return mp3s[0]
