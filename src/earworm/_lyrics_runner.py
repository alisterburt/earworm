# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = [
#   "faster-whisper",
#   "whisperx",
# ]
# ///
"""Isolated runner for lyric transcription + forced alignment.

Two stages in one ephemeral uv env:
  1. faster-whisper transcribes the vocal stem to text. VAD and previous-text
     conditioning are OFF — on sung vocals the VAD drops whole choruses and the
     conditioning makes whisper drift / collapse at the end.
  2. whisperx's wav2vec2 forced alignment anchors every word to the audio (its
     attention-based word timestamps don't sit on the sung notes). We use only
     whisperx's alignment (no pyannote VAD), so no HuggingFace token is needed.

    uv run --script _lyrics_runner.py <vocal.wav> <out.json> <model>

Emits {"language": str, "segments": [{start, end, text, words: [{start,end,word}]}]}.
"""

import json
import sys

import whisperx
from faster_whisper import WhisperModel


def main() -> None:
    audio_path, out_path, model_name = sys.argv[1], sys.argv[2], sys.argv[3]

    # 1. Transcribe (words + coarse segment bounds).
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        audio_path,
        vad_filter=False,
        condition_on_previous_text=False,
        temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        beam_size=5,
        no_speech_threshold=0.6,
    )
    lang = info.language
    segs = [
        {"start": s.start, "end": s.end, "text": s.text.strip()}
        for s in segments
        if s.text.strip()
    ]

    # 2. Forced-align to the audio for accurate per-word timing.
    audio = whisperx.load_audio(audio_path)
    align_model, metadata = whisperx.load_align_model(language_code=lang, device="cpu")
    aligned = whisperx.align(segs, align_model, metadata, audio, "cpu", return_char_alignments=False)

    out_segments = []
    for s in aligned["segments"]:
        words = [
            {"start": round(w["start"], 3), "end": round(w["end"], 3), "word": w["word"]}
            for w in s.get("words", [])
            if w.get("start") is not None and w.get("end") is not None
        ]
        text = s.get("text", "").strip()
        if not words and not text:
            continue
        start = words[0]["start"] if words else round(s["start"], 3)
        end = words[-1]["end"] if words else round(s["end"], 3)
        out_segments.append({"start": start, "end": end, "text": text, "words": words})

    payload = {"language": lang, "segments": out_segments}
    with open(out_path, "w") as fh:
        json.dump(payload, fh)


if __name__ == "__main__":
    main()
