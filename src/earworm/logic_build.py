"""Build a Logic Pro project from an audio file by driving the Logic UI (macOS only).

This is the front of the pipeline: it takes a bare mp3, opens Logic Pro, and
produces a saved, folder-organized project (stems + chord/key/tempo analysis)
that `pipeline.process()` then reads back. The actual UI choreography lives in
`logic-automation/lib/automate.applescript`; this module just orchestrates the
reset/launch around it and derives the project name.

UI automation caveats (see logic-automation/README.md): Logic must stay frontmost
and you must keep hands off the keyboard/mouse while it runs, and the controlling
terminal needs macOS Accessibility permission.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from .llm import ask_claude
from .utils import log

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTOMATE = REPO_ROOT / "logic-automation" / "lib" / "automate.applescript"
DEFAULT_SAVE_DIR = Path.home() / "Music" / "Logic" / "earworm"

_NAME_PROMPT = """Extract the artist and song title from this audio filename.
Strip junk: (Official Video), [Lyrics], bracketed IDs, file extensions, and
featured-artist clutter unless part of the real title.

Reply with a single line in exactly this form (and nothing else matters — any
preamble is ignored, only this line is read):
NAME: <Artist> - <Song>

Example -> NAME: MGMT - Kids

Filename: {filename}"""


def clean_name(filename: str) -> str:
    """Derive a clean '<Artist> - <Song>' from a (possibly messy) filename via claude -p.

    We make claude emit a `NAME: ...` marker line and parse that, so leading
    commentary doesn't get mistaken for the answer. Falls back to the filename stem.
    """
    out = ask_claude(_NAME_PROMPT.format(filename=filename), timeout=60) or ""
    name = ""
    for line in out.splitlines():
        line = line.strip()
        if line.upper().startswith("NAME:"):
            name = line[len("NAME:"):].strip().strip("\"'")
            break
    name = name or Path(filename).stem
    return name.translate(str.maketrans("/:", "--"))  # filesystem-safe


def _logic_running() -> bool:
    return subprocess.run(["pgrep", "-x", "Logic Pro"], capture_output=True).returncode == 0


def _reset_logic(discard_open: bool) -> None:
    """Quit any running Logic so we start from a clean slate."""
    if not _logic_running():
        return
    log("quitting running Logic Pro")
    saving = "no" if discard_open else "yes"
    subprocess.run(
        ["osascript", "-e", f'tell application "Logic Pro" to quit saving {saving}'],
        capture_output=True,
    )
    for _ in range(20):
        if not _logic_running():
            break
        time.sleep(0.5)
    if _logic_running():
        log("force-killing stuck Logic")
        subprocess.run(["pkill", "-9", "Logic Pro"], capture_output=True)
        time.sleep(1)


def _launch_logic() -> None:
    log("launching Logic Pro")
    subprocess.run(["open", "-a", "Logic Pro"], check=True)
    for _ in range(60):
        if _logic_running():
            return
        time.sleep(0.5)
    raise RuntimeError("Logic Pro did not launch")


def build_project(
    audio: Path,
    name: str | None = None,
    save_dir: Path = DEFAULT_SAVE_DIR,
    discard_open: bool = True,
    timeout: int = 1800,
) -> Path:
    """Drive Logic to import `audio` and save a processed project; return its folder.

    `name` defaults to a claude-cleaned '<Artist> - <Song>' from the filename.
    `discard_open=False` saves (rather than discards) any project already open.
    """
    audio = audio.expanduser().resolve()
    if not audio.is_file():
        raise FileNotFoundError(audio)
    if not AUTOMATE.is_file():
        raise FileNotFoundError(f"automation script missing: {AUTOMATE}")

    name = name or clean_name(audio.name)
    save_dir = save_dir.expanduser()
    save_dir.mkdir(parents=True, exist_ok=True)

    log(f"=== building Logic project '{name}' from {audio.name} ===")
    _reset_logic(discard_open)

    # Overwrite cleanly: remove any existing project folder *before* saving, so
    # Logic writes a fresh one. (Letting Logic's Save-As "Replace" handle it
    # leaves numbered-duplicate stems, e.g. _Bass_1.wav, in Audio Files.) Logic
    # is quit at this point, so the folder isn't locked.
    proj = save_dir / name
    if proj.exists():
        log(f"removing existing project folder {proj}")
        shutil.rmtree(proj)

    _launch_logic()
    time.sleep(3)  # let the project chooser / UI settle
    log("driving Logic UI — keep hands off the keyboard/mouse, Logic must stay frontmost")
    subprocess.run(
        ["osascript", str(AUTOMATE), str(audio), name, str(save_dir)],
        check=True,
        timeout=timeout,
    )

    if not (proj / f"{name}.logicx").exists():
        raise RuntimeError(f"expected Logic project not found at {proj}")
    log(f"=== built {proj} ===")
    return proj
