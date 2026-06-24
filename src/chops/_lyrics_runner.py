# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "faster-whisper",
# ]
# ///
"""Isolated runner for faster-whisper lyric transcription.

faster-whisper (CTranslate2) is fast on CPU and gives word-level timestamps,
which we use for karaoke-style highlighting. Runs in its own ephemeral uv env:

    uv run --script _lyrics_runner.py <vocal.wav> <out.json> <model>

Emits {"language": str, "segments": [{start, end, text, words: [...]}]}.
"""

import json
import sys

from faster_whisper import WhisperModel


def main() -> None:
    audio_path, out_path, model_name = sys.argv[1], sys.argv[2], sys.argv[3]
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        audio_path, word_timestamps=True, vad_filter=True
    )
    out_segments = []
    for seg in segments:
        words = [
            {"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word}
            for w in (seg.words or [])
        ]
        out_segments.append(
            {
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
                "words": words,
            }
        )
    payload = {"language": info.language, "segments": out_segments}
    with open(out_path, "w") as fh:
        json.dump(payload, fh)


if __name__ == "__main__":
    main()
