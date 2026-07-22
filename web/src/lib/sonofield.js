// Sonofield colour + music-theory helpers (Roman numerals computed on the fly).

export const PALETTE = [
  "#5547f5", "#bffd6d", "#e34af7", "#8bfcb3", "#e85360", "#71adf9",
  "#f8fe6d", "#9b48f6", "#8efc6d", "#e74da7", "#8ffcfe", "#f3ac60",
];
export const DEGREE_LABELS = ["1","b2","2","b3","3","4","#4","5","b6","6","b7","7"];
export const NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
// circle-of-fifths order of semitone offsets (for the wheel layout)
export const FIFTHS = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5];

const LETTER_PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const MAJOR = new Set([0, 2, 4, 5, 7, 9, 11]);
const MINOR = new Set([0, 2, 3, 5, 7, 8, 10]);

export function notePc(name) {
  if (!name) return null;
  let pc = LETTER_PC[name[0].toUpperCase()];
  if (pc == null) return null;
  if (name[1] === "#") pc += 1;
  else if (name[1] === "b") pc -= 1;
  return ((pc % 12) + 12) % 12;
}

export const pcColor = (pc, tonicPc) => PALETTE[(((pc - tonicPc) % 12) + 12) % 12];
export const degreeLabel = (pc, tonicPc) => DEGREE_LABELS[(((pc - tonicPc) % 12) + 12) % 12];
export const noteName = (pc) => NOTE_NAMES[((pc % 12) + 12) % 12];

export function keyScalePcs(tonicPc, mode) {
  const scale = mode === "minor" ? MINOR : MAJOR;
  return new Set([...scale].map((d) => (tonicPc + d) % 12));
}

// The key region {tonic, mode, ...} in effect at time `t`, from an ordered list
// of regions (each with start/end in seconds). Clamps to the first/last region
// outside the covered span. Falls back to `fallback` (e.g. song.key) when there
// are no regions. Lets the UI honour mid-song key changes.
export function keyAt(keys, t, fallback = null) {
  if (keys && keys.length) {
    for (const k of keys) if (t >= k.start && t < k.end) return k;
    return t < keys[0].start ? keys[0] : keys[keys.length - 1];
  }
  return fallback;
}

// ---- chord label parsing + Roman numerals ----
const ROOT_RE = /^([A-G])([#b]?)(.*)$/;
const MAJ_NUM = { 0:"I",1:"♭II",2:"II",3:"♭III",4:"III",5:"IV",6:"♯IV",7:"V",8:"♭VI",9:"VI",10:"♭VII",11:"VII" };
const MIN_NUM = { 0:"I",1:"♭II",2:"II",3:"III",4:"♯III",5:"IV",6:"♯IV",7:"V",8:"VI",9:"♯VI",10:"VII",11:"♯VII" };

export function chordRootPc(label) {
  if (!label || label === "N" || label === "NC") return null;
  return notePc(label.split("/")[0]);
}

// colour of the chord sounding at time t (by its root), or null
export function chordColorAt(chords, t, tonicPc) {
  for (const c of chords) {
    if (c.label === "N") continue;
    if (t >= c.start && t < c.end) {
      const r = chordRootPc(c.label);
      return r == null ? null : pcColor(r, tonicPc);
    }
  }
  return null;
}

// colour for a [start,end) span: the chord active at start, else the first chord inside
export function spanColor(chords, start, end, tonicPc) {
  const at = chordColorAt(chords, start, tonicPc);
  if (at) return at;
  for (const c of chords) {
    if (c.label !== "N" && c.start >= start && c.start < end) {
      const r = chordRootPc(c.label);
      if (r != null) return pcColor(r, tonicPc);
    }
  }
  return null;
}

function qualityExt(rest) {
  let quality;
  if (rest.includes("dim") || rest.includes("°") || rest.startsWith("o")) quality = "dim";
  else if (rest.includes("aug") || rest.includes("+")) quality = "aug";
  else if (rest.startsWith("maj") || rest.startsWith("M")) quality = "maj";
  else if (rest.startsWith("m") || rest.startsWith("-")) quality = "min";
  else quality = "maj";
  let ext = "";
  for (const tok of ["maj7", "sus4", "sus2", "9", "7", "6"]) {
    if (rest.includes(tok)) { ext = tok; break; }
  }
  return { quality, ext };
}

// roman numeral for a chord label, in key (tonicPc, mode). Falls back to label.
export function chordRoman(label, tonicPc, mode) {
  if (!label || label === "N" || label === "NC") return label;
  const [rootPart, , bassPart] = label.split(/(\/)/);
  const m = ROOT_RE.exec(rootPart);
  const rootPc = chordRootPc(rootPart);
  if (!m || rootPc == null || tonicPc == null) return label;
  const table = mode === "minor" ? MIN_NUM : MAJ_NUM;
  let num = table[(((rootPc - tonicPc) % 12) + 12) % 12];
  const { quality, ext } = qualityExt(m[3]);
  if (quality === "min" || quality === "dim") num = num.toLowerCase();
  if (quality === "dim") num += "°";
  else if (quality === "aug") num += "+";
  num += ext;
  if (bassPart) {
    const bpc = notePc(label.split("/")[1]);
    if (bpc != null) num += "/" + table[(((bpc - tonicPc) % 12) + 12) % 12];
  }
  return num;
}

// semitone-above-tonic for a roman-numeral or degree token (for colouring)
export function tokenSemitone(tok) {
  if (!tok) return null;
  let m = /^([#b♭♯]?)([ivIV]+)/.exec(tok.trim());
  if (m) {
    const map = { i: 0, ii: 1, iii: 2, iv: 3, v: 4, vi: 5, vii: 6 };
    const deg = map[m[2].toLowerCase()];
    if (deg == null) return null;
    let semi = [0, 2, 4, 5, 7, 9, 11][deg];
    if (m[1] === "#" || m[1] === "♯") semi++;
    if (m[1] === "b" || m[1] === "♭") semi--;
    return ((semi % 12) + 12) % 12;
  }
  m = /^([#b♭♯]?)([1-7])/.exec(tok.trim()); // arabic degree like b3, 5
  if (m) {
    let semi = [0, 2, 4, 5, 7, 9, 11][+m[2] - 1];
    if (m[1] === "#" || m[1] === "♯") semi++;
    if (m[1] === "b" || m[1] === "♭") semi--;
    return ((semi % 12) + 12) % 12;
  }
  return null;
}
export const tokenizeDegrees = (s) => (s || "").split(/[\s\-–—→,|]+/).filter(Boolean);

// display name for a chord respecting the global absolute/relative mode
export function chordName(label, tonicPc, mode, relative) {
  if (!label || label === "N" || label === "NC") return relative ? "" : label;
  return relative ? chordRoman(label, tonicPc, mode) : label;
}

// ---- display-only transpose (audio is unchanged) ----
const SHARP_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
const FLAT_NAMES  = ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","B"];
const FLAT_MAJOR_PCS = new Set([5, 10, 3, 8, 1, 6]); // F Bb Eb Ab Db Gb

// spell a pitch class with sharps or flats
export const spellPc = (pc, flats) => (flats ? FLAT_NAMES : SHARP_NAMES)[(((pc % 12) + 12) % 12)];

// whether a key (given its tonic pc + mode) is conventionally spelled with flats
export function keyUsesFlats(tonicPc, mode) {
  const relMajor = mode === "minor" ? tonicPc + 3 : tonicPc;
  return FLAT_MAJOR_PCS.has((((relMajor % 12) + 12) % 12));
}

// transpose every root/bass letter in a chord (or bare note) label by `semis`,
// respelling with sharps/flats. Suffixes (m, maj7, sus4, …) are left untouched.
export function transposeLabel(label, semis, flats) {
  if (!label || !semis || label === "N" || label === "NC") return label;
  return label.replace(/([A-G])([#b]?)/g, (_, letter, acc) =>
    spellPc(notePc(letter + acc) + semis, flats));
}

// transposed "<Tonic> <mode>" key name
export function transposeKeyName(tonic, mode, semis) {
  const pc = notePc(tonic) + semis;
  return spellPc(pc, keyUsesFlats(pc, mode)) + (mode === "minor" ? " minor" : " major");
}
