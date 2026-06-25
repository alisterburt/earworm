"""Thin wrapper around the local `claude -p` CLI for analysis stages."""

from __future__ import annotations

import json
import re
import subprocess

from .utils import log


def ask_claude(prompt: str, allow_read: bool = False, timeout: int = 240) -> str | None:
    """Run `claude -p` and return its raw stdout text (None on failure).

    Set allow_read=True to let the model use the Read tool (e.g. to view
    piano-roll images whose paths are embedded in the prompt).
    """
    cmd = ["claude", "-p", prompt]
    if allow_read:
        cmd += ["--allowedTools", "Read"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        log(f"claude -p failed: {exc!r}")
        return None
    if r.returncode != 0:
        log(f"claude -p exit {r.returncode}: {r.stderr[:200]}")
        return None
    return r.stdout.strip()


def ask_claude_json(prompt: str, allow_read: bool = False, timeout: int = 240):
    """Run claude and parse a JSON object/array from its reply."""
    out = ask_claude(prompt, allow_read=allow_read, timeout=timeout)
    if not out:
        return None
    return _extract_json(out)


def _extract_json(s: str):
    s = s.strip()
    s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
    s = re.sub(r"\n?```$", "", s).strip()
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        pass
    for open_c, close_c in (("[", "]"), ("{", "}")):
        i, j = s.find(open_c), s.rfind(close_c)
        if 0 <= i < j:
            try:
                return json.loads(s[i : j + 1])
            except Exception:  # noqa: BLE001
                continue
    log("could not parse JSON from claude output")
    return None
