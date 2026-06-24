"""Lyric transcription of the vocal stem via faster-whisper (isolated env)."""

from __future__ import annotations

import json
from pathlib import Path

from .utils import log, run

_RUNNER = Path(__file__).parent / "_lyrics_runner.py"

DEFAULT_MODEL = "small"


def transcribe_lyrics(vocal_wav: Path, work_json: Path, model: str = DEFAULT_MODEL) -> dict | None:
    """Transcribe a vocal stem to {language, segments[]} with word timestamps.

    Returns None on failure (e.g. no network for the model download) so the
    pipeline can continue without lyrics.
    """
    try:
        run(["uv", "run", "--script", str(_RUNNER), str(vocal_wav), str(work_json), model])
        return json.loads(work_json.read_text())
    except Exception as exc:  # noqa: BLE001
        log(f"lyric transcription failed ({exc!r}); continuing without lyrics")
        return None
