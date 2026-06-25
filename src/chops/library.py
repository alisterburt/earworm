"""Build the library index (library.json) from processed song dirs."""

from __future__ import annotations

import json
from pathlib import Path

from .utils import log


def build_library(content_dir: Path) -> Path:
    """Scan content_dir/*/analysis.json and write content_dir/library.json.

    Entries are sorted by `added` (most recent first).
    """
    entries = []
    for analysis in sorted(content_dir.glob("*/analysis.json")):
        d = json.loads(analysis.read_text())
        song_id = analysis.parent.name
        entries.append(
            {
                "id": song_id,
                "title": d.get("title", d.get("name", song_id)),
                "artist": d.get("artist", ""),
                "cover": f"{song_id}/cover.jpg",
                "added": d.get("added", ""),
                "duration": d.get("duration", 0),
                "key": d.get("key", {}).get("name", ""),
                "tempo": d.get("tempo", 0),
            }
        )
    entries.sort(key=lambda e: e["added"], reverse=True)
    out = content_dir / "library.json"
    out.write_text(json.dumps(entries, indent=2))
    log(f"wrote {out} ({len(entries)} songs)")
    return out
