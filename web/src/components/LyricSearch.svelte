<script>
  let { song, engine } = $props();
  let q = $state("");
  const fmt = (s) => `${(s/60)|0}:${String((s|0)%60).padStart(2,"0")}`;
  const segs = song.lyrics?.segments || [];
  let results = $derived(
    q.trim().length < 2 ? []
      : segs.filter((s) => s.text.toLowerCase().includes(q.trim().toLowerCase())).slice(0, 12)
  );
  function go(s) { engine.seek(s.start); q = ""; }
</script>

<div class="search">
  <input placeholder="search lyrics…" bind:value={q} />
  {#if results.length}
    <div class="results">
      {#each results as s}
        <button onclick={() => go(s)}>
          <span class="t">{fmt(s.start)}</span><span class="txt">{s.text}</span>
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .search { position: relative; }
  input { background: var(--surface-2); border: 1px solid var(--border); color: var(--text);
    border-radius: var(--r-pill); padding: 6px 14px; width: 220px; font-size: var(--t-sm); }
  input:focus { outline: none; border-color: var(--accent); }
  .results { position: absolute; right: 0; top: 110%; z-index: 30; width: 360px;
    background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r-md);
    box-shadow: var(--shadow-2); overflow: hidden; }
  .results button { display: flex; gap: var(--s-3); width: 100%; text-align: left;
    background: none; border: none; border-radius: 0; padding: 8px 12px; font-size: var(--t-sm); }
  .results button:hover { background: var(--surface-3); }
  .t { color: var(--text-faint); font-variant-numeric: tabular-nums; min-width: 38px; }
  .txt { color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
