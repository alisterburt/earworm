<script>
  import { onMount, onDestroy } from "svelte";
  import { loadSong } from "../lib/content.js";
  import { navigate } from "../lib/router.js";
  import { Engine, transport } from "../lib/engine.js";
  import { selectedStem, transpose } from "../lib/stores.js";
  import { melodicStems } from "../lib/stems.js";
  import { notePc, pcColor, transposeKeyName, keyAt } from "../lib/sonofield.js";
  import { setDrone } from "../lib/synth.js";
  import OverviewWaveform from "../components/OverviewWaveform.svelte";
  import SectionView from "../components/SectionView.svelte";
  import SideRail from "../components/SideRail.svelte";
  import SectionControls from "../components/SectionControls.svelte";
  import LyricSearch from "../components/LyricSearch.svelte";

  let { id } = $props();
  let song = $state(null);
  let error = $state(null);
  let engine = $state(null);

  onMount(async () => {
    try {
      song = await loadSong(id);
      selectedStem.set(melodicStems(song)[0] || null);
      engine = new Engine(song); engine.load();
    } catch (e) { error = e.message; }
  });
  onDestroy(() => { engine?.destroy(); setDrone(0, 0); });
  function onKey(e) {
    // ignore Space while typing in a field (e.g. lyric search)
    const el = e.target;
    if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)) return;
    if (e.code === "Space" && engine) { e.preventDefault(); engine.toggle(); }
  }

  const fmt = (t) => `${(t / 60) | 0}:${String((t | 0) % 60).padStart(2, "0")}`;
  // Key shown in the header tracks the playhead, so it follows mid-song key changes.
  let curKey = $derived(song ? (keyAt(song.keys?.length ? song.keys : null, $transport.time, song.key) || song.key) : null);
  let keyColor = $derived(curKey ? pcColor(notePc(curKey.tonic || "C"), notePc(curKey.tonic || "C")) : "#fff");
  let keyName = $derived(curKey ? ($transpose ? transposeKeyName(curKey.tonic, curKey.mode, $transpose) : curKey.name) : "");

  // Drag the BPM pill vertically to scrub playback speed (pitch-preserving via the
  // engine); double-click resets to the original tempo. Rate clamped 0.25×–1.5×.
  const RATE_MIN = 0.25, RATE_MAX = 1.5, RATE_SENS = 0.005;
  let bpmDrag = null;
  function bpmDown(e) {
    if (!engine) return;
    e.preventDefault();
    bpmDrag = { y: e.clientY, rate: $transport.rate };
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function bpmMove(e) {
    if (!bpmDrag) return;
    const r = bpmDrag.rate + (bpmDrag.y - e.clientY) * RATE_SENS;
    engine.setRate(Math.max(RATE_MIN, Math.min(RATE_MAX, r)));
  }
  function bpmUp(e) {
    if (!bpmDrag) return;
    bpmDrag = null;
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  }
  // Scroll wheel / two-finger swipe over the pill nudges speed too (up = faster).
  function bpmWheel(e) {
    if (!engine) return;
    e.preventDefault();
    const r = $transport.rate + e.deltaY * 0.0008;
    engine.setRate(Math.max(RATE_MIN, Math.min(RATE_MAX, r)));
  }

  // Same drag / scroll / double-click-reset gesture on the key pill, transposing
  // the display ±6 semitones (audio unchanged).
  const TR_MIN = -6, TR_MAX = 6, TR_PX = 22; // px of drag per semitone
  const clampTr = (t) => Math.max(TR_MIN, Math.min(TR_MAX, t));
  let keyDrag = null, keyAcc = 0;
  function keyDown(e) {
    e.preventDefault();
    keyDrag = { y: e.clientY, t: $transpose };
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function keyMove(e) {
    if (!keyDrag) return;
    transpose.set(clampTr(keyDrag.t + Math.round((keyDrag.y - e.clientY) / TR_PX)));
  }
  function keyUp(e) {
    if (!keyDrag) return;
    keyDrag = null;
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  }
  function keyWheel(e) {
    e.preventDefault();
    keyAcc += e.deltaY;
    while (Math.abs(keyAcc) >= 40) {
      const dir = keyAcc > 0 ? 1 : -1;
      keyAcc -= dir * 40;
      transpose.update((t) => clampTr(t + dir));
    }
  }

  // Tonic drone — off by default; same drag / scroll / double-click-reset gesture.
  // Sounds the recording's actual tonic (audio isn't transposed), low octave.
  const DR_SENS = 1 / 140; // drag px per full level
  const clampLv = (v) => Math.max(0, Math.min(1, v));
  let droneLevel = $state(0), droneDrag = null;
  function setLevel(v) { droneLevel = clampLv(v); }

  // Keep the audio transpose and the tonic drone in sync with the controls. The
  // drone follows the transpose AND the playhead's key (curKey), so it always
  // sounds the tonic of what you hear — including across mid-song key changes.
  $effect(() => { if (song && engine) engine.setTranspose($transpose); });
  $effect(() => { if (song) setDrone(48 + notePc(curKey?.tonic || "C") + $transpose, droneLevel); });
  function drDown(e) { e.preventDefault(); droneDrag = { y: e.clientY, v: droneLevel }; e.currentTarget.setPointerCapture(e.pointerId); }
  function drMove(e) { if (droneDrag) setLevel(droneDrag.v + (droneDrag.y - e.clientY) * DR_SENS); }
  function drUp(e) { if (!droneDrag) return; droneDrag = null; e.currentTarget.releasePointerCapture?.(e.pointerId); }
  function drWheel(e) { e.preventDefault(); setLevel(droneLevel + e.deltaY * 0.0015); }

  // Metronome — clicks locked to the beat grid (downbeats accented). Click is a
  // plain on/off toggle (defaults to full volume); drag/scroll fine-tunes volume.
  const DEFAULT_METRO = 1;
  let metroLevel = $state(0), metroDrag = null;
  const setMetro = (v) => (metroLevel = clampLv(v));
  $effect(() => { if (engine) engine.setMetronome(metroLevel); });
  function meDown(e) { e.preventDefault(); metroDrag = { y: e.clientY, v: metroLevel, moved: false }; e.currentTarget.setPointerCapture(e.pointerId); }
  function meMove(e) { if (!metroDrag) return; if (Math.abs(e.clientY - metroDrag.y) > 2) metroDrag.moved = true; setMetro(metroDrag.v + (metroDrag.y - e.clientY) * DR_SENS); }
  function meUp(e) { if (!metroDrag) return; if (!metroDrag.moved) setMetro(metroLevel > 0 ? 0 : DEFAULT_METRO); metroDrag = null; e.currentTarget.releasePointerCapture?.(e.pointerId); }
  function meWheel(e) { e.preventDefault(); setMetro(metroLevel + e.deltaY * 0.0015); }
</script>

<svelte:window onkeydown={onKey} />

{#if error}
  <div class="fallback"><button class="back" onclick={() => navigate("/")}>‹ Library</button><p>{error}</p></div>
{:else if !song}
  <div class="fallback"><p>loading…</p></div>
{:else}
  <div class="app">
    <header>
      <button class="back" onclick={() => navigate("/")}>‹</button>
      <div class="id">
        <span class="title">{song.title}</span>
        <span class="artist">{song.artist}</span>
      </div>
      <span class="key" class:adjusted={$transpose !== 0}
        onpointerdown={keyDown} onpointermove={keyMove} onpointerup={keyUp} onwheel={keyWheel}
        ondblclick={() => transpose.set(0)} role="slider" tabindex="-1"
        aria-label="transpose display" aria-valuenow={$transpose}
        title="drag or scroll to transpose · double-click to reset">
        <span class="dot" style="--c:{keyColor}"></span>{keyName}{#if $transpose !== 0}<small>{$transpose > 0 ? `+${$transpose}` : $transpose}</small>{/if}
      </span>
      <span class="bpm" class:adjusted={$transport.rate !== 1} class:dragging={bpmDrag}
        onpointerdown={bpmDown} onpointermove={bpmMove} onpointerup={bpmUp} onwheel={bpmWheel}
        ondblclick={() => engine?.setRate(1)} role="slider" tabindex="-1"
        aria-label="playback tempo" aria-valuenow={Math.round(song.tempo * $transport.rate)}
        title="drag or scroll to change speed · double-click to reset">
        {Math.round(song.tempo * $transport.rate)} <small>bpm{#if $transport.rate !== 1} · {Math.round($transport.rate * 100)}%{/if}</small>
      </span>
      {#if song.time_signature}<span class="sig">{song.time_signature.numerator}/{song.time_signature.denominator}</span>{/if}
      <span class="drone" class:adjusted={droneLevel > 0}
        onpointerdown={drDown} onpointermove={drMove} onpointerup={drUp} onwheel={drWheel}
        ondblclick={() => setLevel(0)} role="slider" tabindex="-1"
        aria-label="tonic drone" aria-valuenow={Math.round(droneLevel * 100)}
        title="tonic drone · drag or scroll to set · double-click for off">
        drone{#if droneLevel > 0} <small>{Math.round(droneLevel * 100)}%</small>{/if}
      </span>
      <span class="metro" class:adjusted={metroLevel > 0}
        onpointerdown={meDown} onpointermove={meMove} onpointerup={meUp} onwheel={meWheel}
        ondblclick={() => setMetro(0)} role="slider" tabindex="-1"
        aria-label="metronome" aria-valuenow={Math.round(metroLevel * 100)}
        title="metronome (clicks the beat grid) · click to toggle · drag or scroll for volume">
        <svg class="micon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M9 3h6l3 18H6z" />
          <path d="M12 19 14.6 7" />
          <circle cx="13.7" cy="10.8" r="1.15" fill="currentColor" stroke="none" />
        </svg>{#if metroLevel > 0} <small>{Math.round(metroLevel * 100)}%</small>{/if}
      </span>

      <div class="spacer"></div>

      {#if song.lyrics?.segments?.length}<LyricSearch {song} {engine} />{/if}

      <div class="transport">
        <span class="time">{fmt($transport.time)} <span class="sep">/</span> {fmt(song.duration)}</span>
        <button class="play" class:on={$transport.playing} onclick={() => engine.toggle()}
          aria-label={$transport.playing ? "pause" : "play"}>
          {#if $transport.playing}❚❚{:else}▶{/if}
        </button>
      </div>
    </header>

    <div class="overview"><OverviewWaveform {song} {engine} /></div>

    <main>
      <div class="roll"><SectionView {song} {engine} /></div>
      <SideRail {song} {engine} />
    </main>

    <footer><SectionControls {song} /></footer>
  </div>
{/if}

<style>
  .app { height: 100vh; display: grid; grid-template-rows: auto auto 1fr auto;
    gap: var(--s-3); padding: var(--s-3) var(--s-4); }

  header { display: flex; align-items: center; gap: var(--s-3); min-width: 0; }
  .back { width: 30px; height: 30px; padding: 0; display: grid; place-items: center;
    border-radius: var(--r-sm); font-size: 17px; color: var(--text-dim); flex: none; }
  .id { display: flex; align-items: baseline; gap: var(--s-2); min-width: 0; }
  .title { font-weight: 700; white-space: nowrap; }
  .artist { color: var(--text-dim); font-size: var(--t-sm); white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; }
  .key, .bpm, .sig, .drone, .metro { display: inline-flex; align-items: center; gap: 5px; flex: none;
    color: var(--text-dim); font-size: var(--t-sm); padding: 4px 9px;
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-pill); }
  .bpm, .key, .drone, .metro { cursor: ns-resize; user-select: none; touch-action: none;
    transition: border-color .12s, color .12s; }
  .bpm { font-variant-numeric: tabular-nums; }
  .bpm small, .drone small, .metro small, .sep { color: var(--text-faint); }
  .bpm:hover, .key:hover, .drone:hover, .metro:hover { border-color: var(--text-faint); }
  .bpm.adjusted, .key.adjusted, .drone.adjusted, .metro.adjusted { color: var(--accent); border-color: var(--accent); }
  .bpm.adjusted small, .key.adjusted small, .drone.adjusted small, .metro.adjusted small { color: color-mix(in srgb, var(--accent) 70%, transparent); }
  .key.adjusted small { font-size: var(--t-xs); }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--c); box-shadow: 0 0 7px -1px var(--c); }
  .micon { width: 15px; height: 15px; display: block; }
  .metro { padding: 4px 8px; cursor: pointer; }
  .spacer { flex: 1; }

  .transport { display: flex; align-items: center; gap: var(--s-3); flex: none; }
  .time { color: var(--text-dim); font-size: var(--t-sm); font-variant-numeric: tabular-nums; }
  .play { width: 38px; height: 38px; padding: 0; border-radius: 50%; display: grid; place-items: center;
    font-size: 13px; background: var(--accent); color: var(--accent-contrast); border-color: var(--accent); }
  .play:hover { filter: brightness(1.08); border-color: var(--accent); }

  .overview { display: flex; }
  main { display: grid; grid-template-columns: minmax(0, 1fr) 332px; gap: var(--s-3); min-height: 0; }
  .roll { min-width: 0; min-height: 0; }

  .fallback { display: grid; place-items: center; height: 100vh; gap: var(--s-3); color: var(--text-dim); }
  .fallback .back { position: fixed; top: var(--s-4); left: var(--s-4); width: auto; padding: 6px 12px; }

  @media (max-width: 880px) {
    main { grid-template-columns: 1fr; grid-template-rows: 1fr auto; }
  }
</style>
