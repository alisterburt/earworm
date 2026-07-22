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
let drone = null; // { midi, master, oscs }
const mfreq = (m) => 440 * Math.pow(2, (m - 69) / 12);

function buildDrone(midi, t) {
  const master = ctx.createGain(); master.gain.value = 0;
  // a touch brighter so the sawtooth overtones (the tanpura "jvari" buzz) come through
  const lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 2200;
  lp.connect(master); master.connect(ctx.destination);
  // classic tanpura string course: Pa (lower fifth) · Sa · Sa · Sa (lower octave)
  const specs = [
    { m: midi - 5, type: "sawtooth", g: 0.30, det: -3 }, // Pa — perfect fifth below
    { m: midi, type: "sawtooth", g: 0.42, det: 0 },      // Sa
    { m: midi, type: "triangle", g: 0.30, det: 4 },      // Sa (detuned for shimmer)
    { m: midi - 12, type: "sine", g: 0.55, det: 0 },     // Sa, octave below
    { m: midi + 12, type: "sine", g: 0.12, det: 0 },     // soft upper octave
  ];
  const oscs = specs.map((s) => {
    const o = ctx.createOscillator(); o.type = s.type; o.frequency.value = mfreq(s.m); o.detune.value = s.det;
    const g = ctx.createGain(); g.gain.value = s.g; o.connect(g).connect(lp); o.start(t);
    return o;
  });
  return { midi, master, oscs };
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
}
