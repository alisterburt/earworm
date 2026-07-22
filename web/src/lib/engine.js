// Pitch-preserving multi-stem audio engine driving a Svelte transport store.
// One <audio> per present stem (they sum to the mix); enable/disable = mute;
// playbackRate with preservesPitch = time-stretch without pitch change.
import { writable, get } from "svelte/store";
import { createPitchShifter } from "./pitchshift.js";

export const transport = writable({
  playing: false,
  time: 0,
  duration: 0,
  rate: 1,
  loop: null, // { start, end } in seconds
  active: new Set(), // enabled stem names
});

export class Engine {
  constructor(song) {
    this.song = song;
    this.els = {};
    this.clock = null;
    this.raf = null;
    this.metro = { level: 0, idx: 0 }; // metronome: click volume 0..1, next-beat cursor
  }

  load() {
    const present = Object.entries(this.song.stems).filter(([, s]) => s.present);
    for (const [name, s] of present) {
      const el = new Audio(this.song._base + s.audio);
      el.preload = "auto";
      el.crossOrigin = "anonymous";
      el.preservesPitch = el.mozPreservesPitch = el.webkitPreservesPitch = true;
      this.els[name] = el;
    }
    this.clock = Object.values(this.els)[0] || null;
    // Mark which beats are downbeats (bar starts) so the metronome can accent them.
    const beats = this.song.beats || [], downs = this.song.downbeats || [];
    let di = 0;
    this._isDown = beats.map((b) => {
      while (di < downs.length && downs[di] < b - 0.02) di++;
      return di < downs.length && Math.abs(downs[di] - b) < 0.02;
    });
    this._buildGraph();
    transport.update((t) => ({
      ...t,
      duration: this.song.duration,
      active: new Set(Object.keys(this.els)),
    }));
    this._applyMute();
    this._loop();
  }

  // Route every stem through Web Audio: source -> per-stem gain (mute) -> bus.
  // The bus goes straight to the speakers, or via the pitch shifter when transposed.
  _buildGraph() {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return; // no Web Audio -> fall back to el.muted, no transpose
    this.ac = new AC();
    this.bus = this.ac.createGain();
    this.shifter = createPitchShifter(this.ac);
    this.shifter.output.connect(this.ac.destination);
    this.bus.connect(this.ac.destination); // bypass (no transpose) by default
    this.shifted = false;
    this.gains = {};
    for (const n in this.els) {
      const src = this.ac.createMediaElementSource(this.els[n]);
      const g = this.ac.createGain();
      src.connect(g).connect(this.bus);
      this.gains[n] = g;
    }
  }

  // Live pitch shift to match the display transpose (audio stays at tempo; the
  // shifter adds the warble). 0 semitones bypasses the shifter for clean audio.
  setTranspose(semis) {
    if (!this.ac || !this.shifter) return;
    if (!semis) {
      if (this.shifted) { this.bus.disconnect(); this.bus.connect(this.ac.destination); this.shifted = false; }
      return;
    }
    if (!this.shifted) { this.bus.disconnect(); this.bus.connect(this.shifter.input); this.shifted = true; }
    this.shifter.setSemitones(semis);
  }

  destroy() {
    cancelAnimationFrame(this.raf);
    for (const n in this.els) { this.els[n].pause(); this.els[n].src = ""; }
    this.els = {};
    try { this.ac?.close(); } catch {}
  }

  now() { return this.clock ? this.clock.currentTime : 0; }

  _applyMute() {
    const { active } = get(transport);
    for (const n in this.els) {
      if (this.gains?.[n]) this.gains[n].gain.value = active.has(n) ? 1 : 0;
      else this.els[n].muted = !active.has(n);
    }
  }

  play(off) {
    const auto = off == null;
    if (auto) off = this.now();
    const { rate, loop } = get(transport);
    // starting playback outside a defined loop jumps to the loop start
    if (auto && loop && (off < loop.start || off >= loop.end)) off = loop.start;
    if (this.ac?.state === "suspended") this.ac.resume();
    this.metro.idx = this._beatIdxAt(off);
    this._applyMute();
    for (const n in this.els) {
      const el = this.els[n];
      el.playbackRate = rate; el.preservesPitch = true;
      el.currentTime = off;
      el.play().catch(() => {});
    }
    transport.update((t) => ({ ...t, playing: true }));
  }

  pause() {
    for (const n in this.els) this.els[n].pause();
    transport.update((t) => ({ ...t, playing: false }));
  }

  toggle() { get(transport).playing ? this.pause() : this.play(); }

  seek(time) {
    const { duration } = get(transport);
    time = Math.max(0, Math.min(time, duration));
    for (const n in this.els) this.els[n].currentTime = time;
    this.metro.idx = this._beatIdxAt(time);
    transport.update((t) => ({ ...t, time }));
  }

  // ---- metronome: clicks locked to the beat grid, scheduled via Web Audio ----
  setMetronome(level) {
    this.metro.level = Math.max(0, Math.min(1, level || 0));
    this.metro.idx = this._beatIdxAt(get(transport).time);
  }

  _beatIdxAt(t) {
    const beats = this.song.beats || [];
    let i = 0;
    while (i < beats.length && beats[i] < t - 0.04) i++;
    return i;
  }

  // schedule any upcoming beat clicks within a short lookahead window. Mapping
  // playhead-time -> Web Audio time keeps clicks sample-accurate and tempo-aware.
  _scheduleMetro(playhead, rate) {
    if (this.metro.level <= 0 || !this.ac) return;
    const beats = this.song.beats || [], acNow = this.ac.currentTime, lookahead = 0.15;
    while (this.metro.idx < beats.length && beats[this.metro.idx] <= playhead + lookahead * rate) {
      const b = beats[this.metro.idx];
      if (b >= playhead - 0.04) this._click(acNow + Math.max(0, (b - playhead) / rate), this._isDown?.[this.metro.idx]);
      this.metro.idx++;
    }
  }

  _click(when, accent) {
    const ac = this.ac;
    const osc = ac.createOscillator(), g = ac.createGain();
    osc.type = "square";
    osc.frequency.value = accent ? 2000 : 1500; // downbeat a touch higher
    const peak = this.metro.level * 0.4 * (accent ? 1 : 0.62);
    g.gain.setValueAtTime(0.0001, when);
    g.gain.exponentialRampToValueAtTime(peak, when + 0.001);
    g.gain.exponentialRampToValueAtTime(0.0001, when + 0.03);
    osc.connect(g).connect(ac.destination); // straight to speakers (no transpose/mute)
    osc.start(when);
    osc.stop(when + 0.04);
  }

  setRate(rate) {
    transport.update((t) => ({ ...t, rate }));
    for (const n in this.els) { this.els[n].playbackRate = rate; this.els[n].preservesPitch = true; }
  }

  setLoop(loop) { transport.update((t) => ({ ...t, loop })); }

  setActive(active) { transport.update((t) => ({ ...t, active: new Set(active) })); this._applyMute(); }

  toggleStem(name) {
    const active = new Set(get(transport).active);
    active.has(name) ? active.delete(name) : active.add(name);
    this.setActive(active);
  }

  allStems(on) {
    this.setActive(on ? Object.keys(this.els) : []);
  }

  _loop() {
    const t = get(transport);
    if (t.playing && this.clock) {
      const ref = this.clock.currentTime;
      // loop
      if (t.loop && ref >= t.loop.end) { this.seek(t.loop.start); }
      else {
        // drift correction
        for (const n in this.els) {
          const el = this.els[n];
          if (el !== this.clock && Math.abs(el.currentTime - ref) > 0.06) el.currentTime = ref;
        }
        if (ref >= t.duration) this.pause();
        this._scheduleMetro(ref, t.rate);
        transport.update((s) => ({ ...s, time: ref }));
      }
    }
    this.raf = requestAnimationFrame(() => this._loop());
  }
}
