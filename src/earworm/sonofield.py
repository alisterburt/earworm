"""Sonofield colour system (shared by cover art + piano-roll renders).

12 colours keyed to scale degree relative to the tonic, arranged by circle of
fifths. Sampled from the reference wheel. Index = semitones above the tonic.
"""

from __future__ import annotations

# semitone-from-tonic -> hex
PALETTE = [
    "#5547f5",  # 0   1
    "#bffd6d",  # 1   b2
    "#e34af7",  # 2   2
    "#8bfcb3",  # 3   b3
    "#e85360",  # 4   3
    "#71adf9",  # 5   4
    "#f8fe6d",  # 6   #4
    "#9b48f6",  # 7   5
    "#8efc6d",  # 8   b6
    "#e74da7",  # 9   6
    "#8ffcfe",  # 10  b7
    "#f3ac60",  # 11  7
]

DEGREE_LABELS = ["1", "b2", "2", "b3", "3", "4", "#4", "5", "b6", "6", "b7", "7"]
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

MAJOR_SCALE = {0, 2, 4, 5, 7, 9, 11}
MINOR_SCALE = {0, 2, 3, 5, 7, 8, 10}


def note_pc(name: str) -> int:
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[name[0].upper()]
    if len(name) > 1 and name[1] == "#":
        base += 1
    elif len(name) > 1 and name[1] == "b":
        base -= 1
    return base % 12


def pc_color(pc: int, tonic_pc: int) -> str:
    return PALETTE[(pc - tonic_pc) % 12]


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
