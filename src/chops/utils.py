"""Shared helpers for the chops pipeline."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Display order for stems below the mix (htdemucs_6s sources). "other" is the
# residual catch-all and goes last; any stem the model didn't produce is skipped.
STEM_ORDER = ["vocals", "piano", "guitar", "drums", "bass", "other"]


def log(msg: str) -> None:
    """Print a stage message to stderr so it never pollutes captured stdout."""
    print(f"[chops] {msg}", file=sys.stderr, flush=True)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess, echoing the command. Raises on non-zero exit."""
    log("$ " + " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=True, **kwargs)


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p
