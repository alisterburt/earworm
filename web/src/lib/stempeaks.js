// Lazily decode each stem to a peak envelope for the overview hover reveal.
// Decoding happens at a low sample rate (fast + low memory) and the result is
// cached per song, so the cost is paid once on the first hover.
import { presentStems } from "./stems.js";

const cache = new Map(); // song.id -> Promise<{name, peaks: Float32Array}[]>

export function loadStemPeaks(song, bins = 2000) {
  if (cache.has(song.id)) return cache.get(song.id);
  const p = decodeAll(song, bins).catch((e) => { cache.delete(song.id); throw e; });
  cache.set(song.id, p);
  return p;
}

async function decodeAll(song, bins) {
  const AC = window.AudioContext || window.webkitAudioContext;
  // 8 kHz is plenty for an amplitude envelope; decodeAudioData resamples to it.
  const ac = new AC({ sampleRate: 8000 });
  const stems = [];
  for (const name of presentStems(song)) {
    try {
      const ab = await fetch(song._base + song.stems[name].audio).then((r) => r.arrayBuffer());
      const audio = await ac.decodeAudioData(ab);
      stems.push({ name, peaks: reduce(audio, bins) });
    } catch {
      stems.push({ name, peaks: new Float32Array(bins) });
    }
  }
  try { ac.close(); } catch {}
  // Normalise across all stems so relative loudness is preserved but everything
  // stays visible (the loudest stem fills its lane).
  let gmax = 0;
  for (const s of stems) for (const v of s.peaks) if (v > gmax) gmax = v;
  if (gmax > 0) for (const s of stems) for (let i = 0; i < s.peaks.length; i++) s.peaks[i] /= gmax;
  return stems;
}

function reduce(audio, bins) {
  const n = audio.length, ch = audio.getChannelData(0);
  const out = new Float32Array(bins), step = n / bins;
  for (let i = 0; i < bins; i++) {
    let mx = 0;
    const a = (i * step) | 0, b = Math.min(n, ((i + 1) * step) | 0);
    for (let j = a; j < b; j++) { const v = ch[j] < 0 ? -ch[j] : ch[j]; if (v > mx) mx = v; }
    out[i] = mx;
  }
  return out;
}
