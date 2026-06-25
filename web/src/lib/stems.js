// Per-stem display metadata (icon + accent colour) for the UI.
export const STEM_META = {
  vocals: { icon: "🎤", color: "#ff6b9d" },
  piano:  { icon: "🎹", color: "#4cc9f0" },
  guitar: { icon: "🎸", color: "#f4a261" },
  drums:  { icon: "🥁", color: "#ffd166" },
  bass:   { icon: "🎵", color: "#06d6a0" },
  other:  { icon: "✨", color: "#9b8cff" },
};
export const stemMeta = (n) => STEM_META[n] || { icon: "•", color: "#9aa3b2" };

// present stems, in pipeline order
export const presentStems = (song) =>
  Object.entries(song.stems).filter(([, s]) => s.present).map(([n]) => n);

export const melodicStems = (song) =>
  presentStems(song).filter((n) => (song.stems[n].notes || []).length);
