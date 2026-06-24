# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "beat_this @ git+https://github.com/CPJKU/beat_this",
#   "torch",
#   "torchaudio",
#   "soundfile",
#   "soxr",
#   "einops",
#   "rotary-embedding-torch",
#   "numpy",
# ]
# ///
"""Isolated runner for the beat_this beat/downbeat tracker (ISMIR 2024).

beat_this pulls in torch and conflicts with the main chops environment, so it
runs as a self-contained PEP 723 script in its own ephemeral uv env:

    uv run --script _beats_runner.py <audio> <out.json>

With dbn=False the tracker needs no madmom (only required for DBN postproc),
so this resolves cleanly on modern Python. Emits {"beats": [...], "downbeats":
[...]} as JSON.
"""

import json
import sys

from beat_this.inference import File2Beats


def main() -> None:
    audio_path, out_path = sys.argv[1], sys.argv[2]
    file2beats = File2Beats(checkpoint_path="final0", device="cpu", dbn=False)
    beats, downbeats = file2beats(audio_path)
    payload = {
        "beats": [float(b) for b in beats],
        "downbeats": [float(d) for d in downbeats],
    }
    with open(out_path, "w") as fh:
        json.dump(payload, fh)


if __name__ == "__main__":
    main()
