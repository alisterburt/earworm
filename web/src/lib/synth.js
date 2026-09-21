// Tiny WebAudio synth so piano keys make a sound when clicked.
let ctx;
export function playNote(midi, dur = 0.6) {
  ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === "suspended") ctx.resume();
  const freq = 440 * Math.pow(2, (midi - 69) / 12);
  const t = ctx.currentTime;
  const osc = ctx.createOscillator();
  const osc2 = ctx.createOscillator();
  const g = ctx.createGain();
  const lp = ctx.createBiquadFilter();
  lp.type = "lowpass"; lp.frequency.value = 4000;
  osc.type = "triangle"; osc.frequency.value = freq;
  osc2.type = "sine"; osc2.frequency.value = freq * 2; // a little shimmer
  const g2 = ctx.createGain(); g2.gain.value = 0.25; osc2.connect(g2).connect(lp);
  osc.connect(lp); lp.connect(g); g.connect(ctx.destination);
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(0.32, t + 0.008);
  g.gain.exponentialRampToValueAtTime(0.0008, t + dur);
  osc.start(t); osc2.start(t); osc.stop(t + dur + 0.05); osc2.stop(t + dur + 0.05);
}

// ---- sustained tonic drone (root + octaves), level 0..1; 0 = off ----
let drone = null; // { midi, master, lp, oscs }
const mfreq = (m) => 440 * Math.pow(2, (m - 69) / 12);

// saw-like wave with 1/n² harmonic rolloff — keeps the overtone series, loses the buzz
let softWave = null;
function getSoftWave() {
  if (!softWave) {
    const real = new Float32Array(25), imag = new Float32Array(25);
    for (let n = 1; n < 25; n++) imag[n] = 1 / (n * n);
    softWave = ctx.createPeriodicWave(real, imag);
  }
  return softWave;
}

function buildDrone(midi, t) {
  const master = ctx.createGain(); master.gain.value = 0;
  const lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 1400;
  lp.connect(master); master.connect(ctx.destination);
  // classic tanpura string course: Pa (lower fifth) · Sa · Sa · Sa (lower octave)
  const specs = [
    { m: midi - 5, soft: true, g: 0.30, det: -2 },   // Pa — perfect fifth below
    { m: midi, soft: true, g: 0.42, det: 0 },        // Sa
    { m: midi, type: "triangle", g: 0.30, det: 2 },  // Sa (detuned for shimmer)
    { m: midi - 12, type: "sine", g: 0.55, det: 0 }, // Sa, octave below
    { m: midi + 12, type: "sine", g: 0.12, det: 0 }, // soft upper octave
  ];
  const oscs = specs.map((s) => {
    const o = ctx.createOscillator();
    if (s.soft) o.setPeriodicWave(getSoftWave()); else o.type = s.type;
    o.frequency.value = mfreq(s.m); o.detune.value = s.det;
    const g = ctx.createGain(); g.gain.value = s.g; o.connect(g).connect(lp); o.start(t);
    return o;
  });
  // very slow cutoff wobble so the held tone breathes instead of sitting organ-static
  const lfo = ctx.createOscillator(); lfo.frequency.value = 0.09;
  const lfoAmt = ctx.createGain(); lfoAmt.gain.value = 90;
  lfo.connect(lfoAmt).connect(lp.frequency); lfo.start(t);
  oscs.push(lfo);
  return { midi, master, lp, oscs };
}

function killDrone(d, t) {
  d.master.gain.cancelScheduledValues(t);
  d.master.gain.setTargetAtTime(0, t, 0.06);
  setTimeout(() => d.oscs.forEach((o) => { try { o.stop(); } catch {} }), 400);
}

export function setDrone(midi, level) {
  ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === "suspended") ctx.resume();
  const t = ctx.currentTime;
  level = Math.max(0, Math.min(1, level));
  if (level <= 0) { if (drone) { killDrone(drone, t); drone = null; } return; }
  if (!drone || drone.midi !== midi) { if (drone) killDrone(drone, t); drone = buildDrone(midi, t); }
  drone.master.gain.setTargetAtTime(level * 0.32, t, 0.08); // 50% on the dial = the old full level
  drone.lp.frequency.setTargetAtTime(900 + level * 1600, t, 0.1); // quieter = darker
}
