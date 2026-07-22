<script>
  import { transport } from "../lib/engine.js";
  import { selectedStem } from "../lib/stores.js";
  import { presentStems, melodicStems, stemMeta } from "../lib/stems.js";

  let { song, engine } = $props();
  const stems = presentStems(song);
  const melodic = new Set(melodicStems(song));
  let allOn = $derived($transport.active.size >= stems.length);

  // Solo is additive: from "all on" it isolates one track; clicking another solo
  // adds it (so you can solo two+ at once); clicking a soloed track removes it,
  // and emptying the solo group returns to all-on.
  function solo(n) {
    const cur = new Set($transport.active);
    let next;
    if (cur.size >= stems.length) next = new Set([n]);
    else if (cur.has(n)) { cur.delete(n); next = cur.size ? cur : new Set(stems); }
    else { cur.add(n); next = cur; }
    engine.setActive([...next]);
  }
</script>

<div class="panel">
  <div class="panel-head">
    <span>Tracks</span>
    <button class="all" class:on={allOn} onclick={() => engine.allStems(true)}>all</button>
  </div>
  <div class="panel-body">
    {#each stems as n}
      {@const on = $transport.active.has(n)}
      {@const soloed = on && $transport.active.size < stems.length}
      {@const meta = stemMeta(n)}
      <div class="row" class:on style="--c:{meta.color}">
        <button class="ctl mute" class:active={!on} title="{on ? 'mute' : 'unmute'} {n}"
          onclick={() => engine.toggleStem(n)}>M</button>
        <button class="ctl solo" class:active={soloed} title="solo {n}"
          onclick={() => solo(n)}>S</button>
        <span class="label">
          <span class="dot"></span>
          <span class="icon">{meta.icon}</span>
          <span class="nm">{n}</span>
        </span>
        {#if melodic.has(n)}
          <button class="notes" class:sel={$selectedStem === n} title="show {n} in the piano roll"
            onclick={() => selectedStem.set(n)}>notes</button>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .all { padding: 2px 9px; font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .08em; border-radius: var(--r-pill); color: var(--text-faint); }
  .all.on { color: var(--text); border-color: var(--border-strong); }
  .panel-body { display: flex; flex-direction: column; gap: 3px; }

  .row { display: flex; align-items: center; gap: 6px; padding: 4px 6px; border-radius: var(--r-sm);
    background: var(--surface-2); border: 1px solid var(--border); opacity: .6;
    transition: opacity var(--dur) var(--ease), border-color var(--dur) var(--ease); }
  .row.on { opacity: 1; border-color: color-mix(in srgb, var(--c) 45%, var(--border)); }

  /* mute + solo: matching square controls on the left */
  .ctl { width: 22px; height: 22px; padding: 0; flex: none; display: grid; place-items: center;
    font-size: 10px; font-weight: 800; border-radius: var(--r-sm);
    background: var(--surface-3); border: 1px solid var(--border); color: var(--text-faint); }
  .ctl:hover { border-color: var(--border-strong); color: var(--text-dim); }
  .mute.active { background: color-mix(in srgb, var(--playhead) 22%, transparent);
    border-color: color-mix(in srgb, var(--playhead) 55%, transparent); color: var(--playhead); }
  .solo.active { background: color-mix(in srgb, var(--accent) 22%, transparent);
    border-color: color-mix(in srgb, var(--accent) 60%, transparent); color: var(--accent); }

  .label { display: flex; align-items: center; gap: 6px; flex: 1; min-width: 0; }
  .dot { width: 7px; height: 7px; border-radius: 50%; flex: none;
    background: var(--c); box-shadow: 0 0 6px -1px var(--c); opacity: .4; }
  .row.on .dot { opacity: 1; }
  .icon { font-size: 13px; line-height: 1; filter: grayscale(.5); }
  .row.on .icon { filter: none; }
  .nm { font-size: var(--t-sm); font-weight: 600; text-transform: capitalize;
    color: var(--text-dim); overflow: hidden; text-overflow: ellipsis; }
  .row.on .nm { color: var(--text); }

  .notes { padding: 4px 9px; font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .06em; border-radius: var(--r-sm); flex: none;
    background: var(--surface-3); border: 1px solid var(--border); color: var(--text-faint); }
  .notes.sel { color: var(--c); border-color: color-mix(in srgb, var(--c) 60%, transparent);
    background: color-mix(in srgb, var(--c) 16%, transparent); }
</style>
