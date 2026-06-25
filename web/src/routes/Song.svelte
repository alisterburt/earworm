<script>
  import { onMount, onDestroy } from "svelte";
  import { loadSong } from "../lib/content.js";
  import { navigate } from "../lib/router.js";
  import { Engine, transport } from "../lib/engine.js";
  import { selectedStem } from "../lib/stores.js";
  import { melodicStems } from "../lib/stems.js";
  import { notePc, pcColor } from "../lib/sonofield.js";
  import OverviewWaveform from "../components/OverviewWaveform.svelte";
  import SectionView from "../components/SectionView.svelte";
  import SideRail from "../components/SideRail.svelte";
  import SectionControls from "../components/SectionControls.svelte";
  import LyricSearch from "../components/LyricSearch.svelte";

  let { id } = $props();
  let song = $state(null);
  let error = $state(null);
  let engine = null;

  onMount(async () => {
    try {
      song = await loadSong(id);
      selectedStem.set(melodicStems(song)[0] || null);
      engine = new Engine(song); engine.load();
    } catch (e) { error = e.message; }
  });
  onDestroy(() => engine?.destroy());
  function onKey(e) { if (e.code === "Space" && engine) { e.preventDefault(); engine.toggle(); } }

  const fmt = (t) => `${(t / 60) | 0}:${String((t | 0) % 60).padStart(2, "0")}`;
  let keyColor = $derived(song ? pcColor(notePc(song.key?.tonic || "C"), notePc(song.key?.tonic || "C")) : "#fff");
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
      <span class="key"><span class="dot" style="--c:{keyColor}"></span>{song.key.name}</span>
      <span class="bpm">{Math.round(song.tempo)} <small>bpm</small></span>
      {#if song.time_signature}<span class="sig">{song.time_signature.numerator}/{song.time_signature.denominator}</span>{/if}

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

    <footer><SectionControls {song} {engine} /></footer>
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
  .key, .bpm, .sig { display: inline-flex; align-items: center; gap: 5px; flex: none;
    color: var(--text-dim); font-size: var(--t-sm); padding: 4px 9px;
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-pill); }
  .bpm { font-variant-numeric: tabular-nums; } .bpm small, .sep { color: var(--text-faint); }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--c); box-shadow: 0 0 7px -1px var(--c); }
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
