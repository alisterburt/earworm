<script>
  import { transport } from "../lib/engine.js";
  import { cleanMidi } from "../lib/stores.js";
  import AbsRelToggle from "./AbsRelToggle.svelte";

  let { song, engine } = $props();
  const SPEEDS = [25, 50, 70, 80, 90, 100];
  let section = $derived((song.sections || []).find((s) => $transport.time >= s.start && $transport.time < s.end));
</script>

<div class="ctrls">
  <div class="banner">
    {#if section}
      <span class="sname">{section.name}</span>
      {#if section.summary}<span class="ssum">{section.summary}</span>{/if}
    {/if}
  </div>
  <div class="right">
    <div class="grp">
      <span class="cap">midi</span>
      <div class="seg">
        <button class:active={!$cleanMidi} onclick={() => cleanMidi.set(false)}>Raw</button>
        <button class:active={$cleanMidi} onclick={() => cleanMidi.set(true)}>Clean</button>
      </div>
    </div>
    <div class="grp">
      <span class="cap">speed</span>
      <div class="seg">
        {#each SPEEDS as s}
          <button class:active={Math.round($transport.rate * 100) === s} onclick={() => engine.setRate(s / 100)}>{s}</button>
        {/each}
      </div>
    </div>
    <div class="grp">
      <span class="cap">names</span>
      <AbsRelToggle />
    </div>
  </div>
</div>

<style>
  .ctrls { display: flex; align-items: center; justify-content: space-between; gap: var(--s-4); flex-wrap: wrap; }
  .banner { display: flex; align-items: baseline; gap: var(--s-3); min-width: 0; }
  .sname { font-weight: 700; flex: none; }
  .ssum { color: var(--text-dim); font-size: var(--t-sm); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .right { display: flex; align-items: center; gap: var(--s-4); }
  .grp { display: inline-flex; align-items: center; gap: 6px; }
</style>
