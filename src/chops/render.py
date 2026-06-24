"""Render the Logic-like HTML viewer from a song dir's analysis.json."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .utils import log

_TEMPLATES = Path(__file__).parent / "templates"


def render_song(song_dir: Path) -> Path:
    """Build a self-contained index.html by embedding analysis.json verbatim.

    All analysis (key, chords + Roman numerals, beats, MIDI notes, lyrics) is
    produced and stored by the pipeline, so this just inlines that complete
    JSON into the page — the viewer never fetches it.
    """
    analysis_path = song_dir / "analysis.json"
    if not analysis_path.exists():
        raise FileNotFoundError(analysis_path)
    data = json.loads(analysis_path.read_text())

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("index.html.j2")
    html = template.render(
        title=data["name"],
        # Injected verbatim into a <script> as a JS object literal.
        data_json=json.dumps(data),
    )
    out = song_dir / "index.html"
    out.write_text(html)
    log(f"wrote {out}")
    return out
