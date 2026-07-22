"""Read analysis straight out of a saved Logic Pro project folder.

A Logic project saved as a folder contains everything earworm used to compute itself,
but at Logic's (superior) quality:

    <project>/
        Audio Files/
            <name>_Bass.wav, _Drums.wav, _Guitar.wav, _Piano.wav, _Vocals.wav, _Other.wav
            <name>.mamd        # analysis sidecar (AIFF; holds the beat grid)
            <name>.mp3         # full mix
        <name>.logicx/
            Alternatives/000/
                MetaData.plist # tempo, key, time signature, sample rate
                ProjectData    # binary project; holds the chord track

This module is pure stdlib (plistlib/struct/zlib/json). The binary chord format was
reverse-engineered; see the `logic-project-extraction` memory for the field map.
"""

from __future__ import annotations

import json
import plistlib
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from .utils import NOTE_NAMES, log

# ---- chord record layout (64-byte packed records in ProjectData) -------------
_REC = 64
_Q_MAJOR, _Q_MINOR, _Q_SUS4 = 0x91, 0x89, 0xA1
# byte[4] is a bit-field for the added note: 6th (0x02), ♭7 (0x04), maj7 (0x08);
# 0x00 = plain triad.
_EXT_NONE, _EXT_6, _EXT_B7, _EXT_MAJ7 = 0x00, 0x02, 0x04, 0x08
# Chord suffix per (triad quality, extension). ♭7 reads as dom7 on major, m7 on
# minor; maj7 keeps the major-7th interval; 6th adds the major sixth.
_SUFFIX = {
    (_Q_MAJOR, _EXT_NONE): "", (_Q_MAJOR, _EXT_6): "6", (_Q_MAJOR, _EXT_B7): "7", (_Q_MAJOR, _EXT_MAJ7): "maj7",
    (_Q_MINOR, _EXT_NONE): "m", (_Q_MINOR, _EXT_6): "m6", (_Q_MINOR, _EXT_B7): "m7", (_Q_MINOR, _EXT_MAJ7): "m(maj7)",
    (_Q_SUS4, _EXT_NONE): "sus4", (_Q_SUS4, _EXT_B7): "7sus4",
}
_BASS_ROOT = 0x0F  # sentinel in byte[6] meaning "root position" (no slash bass)


@dataclass
class LogicProject:
    folder: Path
    name: str            # folder name, e.g. "Aviram - Drag Me Down"
    logicx: Path
    project_data: Path   # Alternatives/000/ProjectData
    metadata_plist: Path  # Alternatives/000/MetaData.plist
    audio_files: Path
    stems: dict[str, Path]  # canonical stem name -> wav path
    mamd: Path | None
    mix: Path | None     # full-mix mp3/m4a, used as the master


def find_project(folder: Path) -> LogicProject:
    """Locate the pieces of a Logic project folder. Raises if it isn't one."""
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise NotADirectoryError(f"not a folder: {folder}")

    logicx = next(iter(sorted(folder.glob("*.logicx"))), None)
    if logicx is None:
        raise FileNotFoundError(f"no .logicx bundle in {folder} — not a Logic project")
    alt = logicx / "Alternatives" / "000"
    project_data = alt / "ProjectData"
    metadata = alt / "MetaData.plist"
    for p in (project_data, metadata):
        if not p.exists():
            raise FileNotFoundError(f"missing {p.relative_to(folder)} in Logic project")

    audio_files = folder / "Audio Files"
    if not audio_files.is_dir():
        raise FileNotFoundError(f"no 'Audio Files' dir in {folder}")

    stems = read_stems(audio_files)
    mamd = next(iter(sorted(audio_files.glob("*.mamd"))), None)
    mix = next(iter(sorted(audio_files.glob("*.mp3"))), None) or \
        next(iter(sorted(audio_files.glob("*.m4a"))), None)

    return LogicProject(
        folder=folder, name=folder.name, logicx=logicx,
        project_data=project_data, metadata_plist=metadata,
        audio_files=audio_files, stems=stems, mamd=mamd, mix=mix,
    )


def read_stems(audio_files: Path) -> dict[str, Path]:
    """Map Logic's `<name>_<Stem>.wav` exports to canonical lowercase stem names."""
    known = {"bass", "drums", "guitar", "piano", "vocals", "other"}
    stems: dict[str, Path] = {}
    for wav in sorted(audio_files.glob("*.wav")):
        suffix = wav.stem.rsplit("_", 1)[-1].lower()
        if suffix in known:
            stems[suffix] = wav
    return stems


# ---- metadata ----------------------------------------------------------------
def read_metadata(plist_path: Path) -> dict:
    """tempo / key / time signature / sample rate from MetaData.plist."""
    with plist_path.open("rb") as fh:
        meta = plistlib.load(fh)
    tonic = str(meta.get("SongKey", "C"))
    mode = str(meta.get("SongGenderKey", "major")).lower()
    return {
        "tempo": round(float(meta.get("BeatsPerMinute", 120.0)), 3),
        "key": {
            "tonic": tonic,
            "mode": mode,
            "name": f"{tonic} {mode}",
            "confidence": 1.0,
            "source": "logic",
        },
        "time_signature": {
            "numerator": int(meta.get("SongSignatureNumerator", 4)),
            "denominator": int(meta.get("SongSignatureDenominator", 4)),
        },
        "sample_rate": int(meta.get("SampleRate", 44100)),
    }


# ---- beat grid (.mamd ResU chunk) --------------------------------------------
def _iff_chunks(data: bytes) -> dict[bytes, bytes]:
    """Parse an AIFF/IFF FORM container into {chunk_id: payload}."""
    if data[:4] != b"FORM":
        raise ValueError("not an IFF/AIFF container")
    chunks: dict[bytes, bytes] = {}
    pos = 12  # skip FORM + size + form-type
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        chunks[cid] = data[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)  # chunks are word-aligned
    return chunks


def read_beats(mamd_path: Path, numerator: int = 4) -> dict:
    """Beat grid from the `.mamd` sidecar.

    Logic's Smart Tempo result lives in the zlib-compressed `ResU` chunk as JSON:
    `initial.beats[]` are absolute beat times in seconds (non-uniform — the grid
    follows the performance). The first beat is the first downbeat.
    """
    chunks = _iff_chunks(mamd_path.read_bytes())
    if b"ResU" not in chunks:
        return {"beats": [], "downbeats": []}
    initial = json.loads(zlib.decompress(chunks[b"ResU"]))["initial"]
    beats = [round(float(b["t"]), 4) for b in initial.get("beats", [])]

    sig = (initial.get("time_signatures") or [{}])[0].get("signature")
    if sig and "/" in sig:
        numerator = int(sig.split("/")[0])
    downbeats = beats[::numerator] if beats else []
    return {"beats": beats, "downbeats": downbeats}


# ---- chord track (ProjectData) -----------------------------------------------
def _valid_chord_record(rec: bytes) -> bool:
    """Structural validity of a 64-byte chord record (quality-independent).

    Two record variants exist: most chords use byte[7]==0x02 / byte[16]==root+0x20,
    but some (seen on tonic/subdominant chords) use byte[7]==0x01 / byte[16]==root+0x10.
    Both are valid; the discriminating invariant is the low nibble of byte[16]
    equalling the root, plus the constant markers. byte[3] (quality) always has its
    top bit set, which rejects trailing garbage records.
    """
    return (
        len(rec) == _REC
        and rec[8] < 12               # root pitch class
        and rec[3] & 0x80             # quality byte (0x91 maj / 0x89 min / 0xa1 sus / ...)
        and rec[7] in (0x01, 0x02)    # constant marker (two variants)
        and rec[10] == 0xB2           # constant marker
        and rec[15] == 0x80           # constant marker
        and (rec[16] & 0x0F) == rec[8]        # low nibble == root
        and (rec[16] & 0xF0) in (0x10, 0x20)  # high nibble 0x10 or 0x20 variant
    )


def _chord_label(rec: bytes) -> str:
    root = NOTE_NAMES[rec[8]]
    suffix = _SUFFIX.get((rec[3], rec[4]))
    if suffix is None:  # unknown quality/extension — surface rather than mislabel
        suffix = f"?q{rec[3]:02x}x{rec[4]:02x}"
    label = root + suffix
    bass = rec[6]
    if bass != _BASS_ROOT and bass < 12:
        label += "/" + NOTE_NAMES[bass]
    return label


def _chord_record(rec: bytes) -> dict:
    """One chord record -> {start (s), label, root_pc, quality, bass}."""
    return {
        "start": round(int.from_bytes(rec[27:32], "little") / 1e9, 4),
        "label": _chord_label(rec),
        "root_pc": rec[8],
        "quality": {_Q_MAJOR: "major", _Q_MINOR: "minor", _Q_SUS4: "sus4"}.get(rec[3], "?"),
        "bass": rec[6] if (rec[6] != _BASS_ROOT and rec[6] < 12) else None,
    }


def read_chords(project_data: Path, duration: float) -> list[dict]:
    """Decode the chord track. Positions are nanoseconds; chords sit on beats.

    Records appear at varying strides/gaps and even different sizes (64-byte in
    older projects, 48-byte for region "Analyze Chords"), so a fixed-stride walk
    from an anchor undercounts — it stops at the first empty grid slot. Instead we
    collect EVERY structurally-valid record (the validator is strict enough that
    non-chord data doesn't match), keep those within the song, order by position,
    and drop exact duplicates. Each chord's `end` is the next chord's start (last
    extends to `duration`).
    """
    data = project_data.read_bytes()
    raw: list[dict] = []
    seen: set = set()
    for off in range(len(data) - _REC):
        rec = data[off:off + _REC]
        if not _valid_chord_record(rec):
            continue
        c = _chord_record(rec)
        if not (0.0 <= c["start"] <= duration + 1.0):
            continue
        key = (round(c["start"], 3), c["label"])
        if key in seen:
            continue
        seen.add(key)
        raw.append(c)
    raw.sort(key=lambda c: c["start"])

    if not raw:
        log("no chord track found in ProjectData")
        return []
    for i, c in enumerate(raw):
        c["end"] = raw[i + 1]["start"] if i + 1 < len(raw) else round(duration, 4)
    log(f"decoded {len(raw)} chords from Logic project")
    return raw


# ---- key signature -----------------------------------------------------------
_FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
_FLAT_MAJOR_TONICS = {5, 10, 3, 8, 1, 6}   # F Bb Eb Ab Db Gb
_FLAT_MINOR_TONICS = {2, 7, 0, 5, 10, 3}   # Dm Gm Cm Fm Bbm Ebm


def _key_uses_flats(key: dict) -> bool:
    """Whether `key` is conventionally spelled with flats (Bb/Eb vs A#/D#)."""
    tonic_pc = NOTE_NAMES.index(key["tonic"]) if key["tonic"] in NOTE_NAMES else \
        (_FLAT_NAMES.index(key["tonic"]) if key["tonic"] in _FLAT_NAMES else 0)
    return tonic_pc in (_FLAT_MINOR_TONICS if key.get("mode") == "minor" else _FLAT_MAJOR_TONICS)


def respell_chords(chords: list[dict], keys: list[dict] | dict) -> list[dict]:
    """Rewrite each chord label with flats or sharps to match the key signature in
    effect *at that chord's time* (e.g. Bb/Eb rather than A#/D# in Bb major). Roots
    and bass come from pitch classes; the quality/extension suffix is preserved.

    `keys` is the cleaned key-region list (start/end in seconds); a single key dict
    is accepted too and treated as covering the whole song.
    """
    regions = keys if isinstance(keys, list) else [keys]

    def key_at(t: float) -> dict | None:
        for k in regions:
            if k.get("start", 0.0) <= t < k.get("end", float("inf")):
                return k
        return regions[-1] if regions else None

    for c in chords:
        key = key_at(c["start"])
        if not key or not _key_uses_flats(key):
            continue  # sharp-spelled key (or none): leave the sharp label as built
        root = c["root_pc"]
        suffix = c["label"][len(NOTE_NAMES[root]):]  # quality/ext (+ "/bass")
        bass = c.get("bass")
        if bass is not None:
            suffix = suffix.rsplit("/", 1)[0]
        c["label"] = _FLAT_NAMES[root] + suffix + (f"/{_FLAT_NAMES[bass]}" if bass is not None else "")
    return chords


# Logic's global Signature track stores key-signature events as 32-byte records:
#   [0:2] = 32 00 (marker) | [2:10] = position (LE u64 fixed-point: 2^28 per whole
#           note, so /2^26 = quarter-note beats from bar 1 — independent of meter)
#   [12]  = SignatureKey (fifths+7, +16 if minor; C=7 G=8 D=9 Bb=5 Em=24) | [23] = 88
# They form one contiguous, position-ordered run whose first event is at beat 0.
_BEAT_FIXED = 2 ** 26  # position units per quarter-note beat
_SHARP_NAMES = NOTE_NAMES


def _decode_sigkey(val: int) -> dict:
    minor = val >= 16
    fifths = (val - 16 if minor else val) - 7
    pc = ((fifths * 7) + (9 if minor else 0)) % 12
    name = (_FLAT_NAMES if fifths < 0 else _SHARP_NAMES)[pc]
    mode = "minor" if minor else "major"
    return {"tonic": name, "mode": mode, "name": f"{name} {mode}", "confidence": 1.0, "source": "logic"}


def _is_sig_record(rec: bytes) -> bool:
    return (len(rec) == 32 and rec[0:2] == b"\x32\x00" and rec[23] == 0x88
            and rec[24:32] == b"\x00" * 8 and rec[13] == 0 and rec[14] == 0
            and rec[16:23] == b"\x00" * 7 and 0 <= rec[12] <= 31)


def _beat_to_sec(beat: float, beats: list[float], tempo: float) -> float:
    if beats and len(beats) > 1:
        i = int(beat)
        if i < len(beats) - 1:
            return beats[i] + (beat - i) * (beats[i + 1] - beats[i])
        step = beats[-1] - beats[-2]
        return beats[-1] + (beat - (len(beats) - 1)) * step
    return beat * 60.0 / (tempo or 120.0)


def read_key_regions(project_data: Path, beats: list[float], tempo: float, duration: float) -> list[dict]:
    """Decode Logic's key-signature track into ordered [{start, end, tonic, mode,
    name, source}] regions (start in seconds). Empty if no track is found."""
    data = project_data.read_bytes()
    cands = [o for o in range(len(data) - 32) if _is_sig_record(data[o:o + 32])]
    runs: list[list[int]] = []
    for o in cands:
        if runs and o == runs[-1][-1] + 32:
            runs[-1].append(o)
        else:
            runs.append([o])
    track = next((r for r in runs if int.from_bytes(data[r[0] + 2:r[0] + 10], "little") == 0), None)
    if not track:
        return []
    events = []
    for o in track:
        rec = data[o:o + 32]
        beat = int.from_bytes(rec[2:10], "little") / _BEAT_FIXED
        start = 0.0 if beat == 0 else round(_beat_to_sec(beat, beats, tempo), 4)
        events.append({"start": start, **_decode_sigkey(rec[12])})
    for i, e in enumerate(events):
        e["end"] = events[i + 1]["start"] if i + 1 < len(events) else round(duration, 4)
    return events


def clean_key_regions(regions: list[dict], min_dur: float = 20.0,
                      mod_dur: float = 45.0) -> tuple[dict, list[dict]]:
    """Tidy raw key regions and return (dominant_key, cleaned_regions).

    Logic's region key-analysis is noisy: a song firmly in one key often flickers
    to its V/IV for a few seconds. The tonic is the key the song keeps RETURNING to
    (most segments) — not necessarily the longest by total duration (a I↔V flicker
    can leave V marginally ahead). So we:

      1. merge consecutive same-key regions;
      2. take `home` = the key with the most segments (ties -> longest total);
      3. absorb every *departure* from `home` shorter than `mod_dur` into its larger
         neighbour (brief flickers collapse back toward home — e.g. a G-major song
         the analyser keeps flipping to D);
      4. absorb any residual region shorter than `min_dur` (leftover noise);
      5. report `home` as the dominant/default key.

    A genuinely single-key song collapses to one region; a real multi-key song keeps
    its sustained (>mod_dur) sections.
    """
    if not regions:
        return None, []

    def merge_same(rs):
        out = []
        for r in rs:
            if out and out[-1]["name"] == r["name"]:
                out[-1]["end"] = r["end"]
            else:
                out.append(dict(r))
        return out

    dur = lambda r: r["end"] - r["start"]

    def absorb(merged, predicate):
        # repeatedly fold the shortest region matching `predicate` into its larger
        # neighbour, then re-merge equal neighbours
        while len(merged) > 1:
            cand = [i for i in range(len(merged)) if predicate(merged[i])]
            if not cand:
                break
            i = min(cand, key=lambda k: dur(merged[k]))
            if i == 0:
                nb = 1
            elif i == len(merged) - 1:
                nb = i - 1
            else:
                nb = i - 1 if dur(merged[i - 1]) >= dur(merged[i + 1]) else i + 1
            merged[nb]["start"] = min(merged[nb]["start"], merged[i]["start"])
            merged[nb]["end"] = max(merged[nb]["end"], merged[i]["end"])
            merged.pop(i)
            merged[:] = merge_same(merged)
        return merged

    merged = merge_same(regions)

    # home = the key the song keeps returning to: most segments, ties -> longest total
    counts: dict[str, int] = {}
    totals: dict[str, float] = {}
    for r in merged:
        counts[r["name"]] = counts.get(r["name"], 0) + 1
        totals[r["name"]] = totals.get(r["name"], 0.0) + dur(r)
    home_name = max(counts, key=lambda n: (counts[n], totals[n]))
    home_src = next(r for r in merged if r["name"] == home_name)

    # collapse short departures from home (tonicizations), then residual noise
    absorb(merged, lambda r: r["name"] != home_name and dur(r) < mod_dur)
    absorb(merged, lambda r: dur(r) < min_dur)

    dominant = {k: home_src[k] for k in ("tonic", "mode", "name", "confidence", "source") if k in home_src}
    return dominant, merged
