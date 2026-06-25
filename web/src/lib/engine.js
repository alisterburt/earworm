// Pitch-preserving multi-stem audio engine driving a Svelte transport store.
// One <audio> per present stem (they sum to the mix); enable/disable = mute;
// playbackRate with preservesPitch = time-stretch without pitch change.
import { writable, get } from "svelte/store";

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
    transport.update((t) => ({
      ...t,
      duration: this.song.duration,
      active: new Set(Object.keys(this.els)),
    }));
    this._applyMute();
    this._loop();
  }

  destroy() {
    cancelAnimationFrame(this.raf);
    for (const n in this.els) { this.els[n].pause(); this.els[n].src = ""; }
    this.els = {};
  }

  now() { return this.clock ? this.clock.currentTime : 0; }

  _applyMute() {
    const { active } = get(transport);
    for (const n in this.els) this.els[n].muted = !active.has(n);
  }

  play(off) {
    if (off == null) off = this.now();
    const { rate } = get(transport);
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
    transport.update((t) => ({ ...t, time }));
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
        transport.update((s) => ({ ...s, time: ref }));
      }
    }
    this.raf = requestAnimationFrame(() => this._loop());
  }
}
