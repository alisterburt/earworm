#!/usr/bin/env python3
"""Add an exported .melody.json to the collection.

Usage:
    python add_melody.py path/to/kyle-i-found-you.melody.json

Copies the file into melodies/ (if it isn't already there) and updates
melodies/manifest.json. Then: git add -A && git commit && git push.
"""
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
MEL = ROOT / "melodies"
MANIFEST = MEL / "manifest.json"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    src = pathlib.Path(sys.argv[1]).expanduser().resolve()
    if not src.exists():
        print(f"error: {src} does not exist")
        return 1

    data = json.loads(src.read_text(encoding="utf-8"))
    # "earmarks-melody" is the app's pre-rename format marker; accept it forever
    if data.get("format") not in ("earworm-melody", "earmarks-melody"):
        print("error: not an earworm melody file (missing format marker)")
        return 1

    MEL.mkdir(exist_ok=True)
    dest = MEL / src.name
    if src != dest:
        shutil.copy2(src, dest)

    manifest = {"melodies": []}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest.setdefault("melodies", [])

    entry = {
        "file": src.name,
        "title": data.get("title", src.stem),
        "key": data.get("key", "C"),
        "notes": len(data.get("markers", [])),
    }
    manifest["melodies"] = [m for m in manifest["melodies"] if m.get("file") != src.name]
    manifest["melodies"].append(entry)
    manifest["melodies"].sort(key=lambda m: m["title"].lower())

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"added \u201c{entry['title']}\u201d ({entry['key']} major, {entry['notes']} notes)")
    print(f"collection now has {len(manifest['melodies'])} melodies \u2014 commit and push to publish")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
