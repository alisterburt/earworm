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
