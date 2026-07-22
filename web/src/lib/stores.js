import { writable } from "svelte/store";

// Global UI prefs
export const relativeMode = writable(true); // Sonofield degree names by default
export const zoomBars = writable(4); // local-window zoom (2..32 bars)
export const selectedStem = writable(null); // stem shown in the piano roll
export const cleanMidi = writable(true); // show cleaned vs raw MIDI
export const transpose = writable(0); // display-only transpose in semitones (-6..+6)
