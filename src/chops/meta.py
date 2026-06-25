"""Song metadata + cover art: filename parsing, iTunes lookup, generated fallback."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import sonofield as sf
from .utils import log


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "-", s).strip("-") or "song"


def parse_artist_title(stem: str) -> tuple[str, str]:
    """'Artist - Title' -> (artist, title); otherwise ('', stem)."""
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return artist.strip(), title.strip()
    return "", stem.strip()


def _itunes_lookup(artist: str, title: str) -> dict | None:
    term = urllib.parse.quote(f"{artist} {title}".strip())
    url = f"https://itunes.apple.com/search?term={term}&entity=song&limit=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "chops/0.1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as exc:  # noqa: BLE001
        log(f"iTunes lookup failed: {exc!r}")
        return None
    results = data.get("results") or []
    if not results:
        return None
    r = results[0]
    art = r.get("artworkUrl100", "")
    # upscale the artwork URL
    art = art.replace("100x100bb", "1000x1000bb") if art else ""
    return {
        "artist": r.get("artistName", artist),
        "title": r.get("trackName", title),
        "album": r.get("collectionName", ""),
        "artwork": art,
    }


def _download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "chops/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as exc:  # noqa: BLE001
        log(f"cover download failed: {exc!r}")
        return False


def _generated_cover(dest: Path, title: str, artist: str, key: dict) -> None:
    """Fallback cover: Sonofield gradient from the song's key + text."""
    size = 1000
    tonic_pc = sf.note_pc(key.get("tonic", "C")) if key else 0
    c1 = sf.hex_to_rgb(sf.PALETTE[0])  # tonic colour (relative index 0)
    c2 = sf.hex_to_rgb(sf.pc_color((tonic_pc + 7) % 12, tonic_pc))  # the 5th
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        t = y / size
        for x in range(size):
            u = (x / size + t) / 2
            px[x, y] = (
                int(c1[0] * (1 - u) + c2[0] * u),
                int(c1[1] * (1 - u) + c2[1] * u),
                int(c1[2] * (1 - u) + c2[2] * u),
            )
    draw = ImageDraw.Draw(img)
    overlay = Image.new("RGBA", (size, size), (10, 12, 16, 90))
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))
    try:
        f_big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 70)
        f_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 44)
    except Exception:  # noqa: BLE001
        f_big = f_small = ImageFont.load_default()
    draw.text((60, size - 200), title, font=f_big, fill=(245, 247, 250))
    draw.text((60, size - 110), artist, font=f_small, fill=(200, 205, 215))
    img.save(dest, "JPEG", quality=90)


# Version qualifiers we ignore when matching a folder title to an iTunes result.
_QUALIFIERS = {"acoustic", "live", "remix", "version", "remaster", "remastered",
               "feat", "ft", "edit", "mix", "single", "demo", "session"}


def _norm_title(s: str) -> set[str]:
    toks = re.sub(r"[^\w\s]", " ", s.lower()).split()
    return {t for t in toks if t not in _QUALIFIERS}


def _good_match(title: str, info: dict) -> bool:
    """True when an iTunes hit is plausibly the same song (so its artwork/album
    are safe to borrow). Compares title tokens, ignoring version qualifiers."""
    it = info.get("title", "")
    t1, t2 = _norm_title(title), _norm_title(it)
    if not t1 or not t2:
        return False
    return len(t1 & t2) / len(t1) >= 0.5


def resolve_metadata(name: str, song_dir: Path, key: dict) -> dict:
    """Return {title, artist, album, cover} and write song_dir/cover.jpg.

    `name` is the Logic folder name ('Artist - Title') and is the source of truth
    for title/artist — iTunes is used only to borrow cover artwork + album when it
    clearly matches, so deliberate names like '(Acoustic)' are never overwritten.
    (Take the raw folder name, not Path.stem — names like 'Fred Again..' have dots
    that .stem would truncate.)
    """
    artist, title = parse_artist_title(name)
    info = _itunes_lookup(artist, title) or {}
    matched = _good_match(title, info)
    album = info.get("album", "") if matched else ""

    cover = song_dir / "cover.jpg"
    ok = matched and bool(info.get("artwork")) and _download(info["artwork"], cover)
    if not ok:
        log("using generated cover")
        _generated_cover(cover, title, artist, key)
    return {"title": title, "artist": artist, "album": album, "cover": cover.name}
