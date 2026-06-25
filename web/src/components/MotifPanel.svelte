<script>
  import MotifCard from "./MotifCard.svelte";
  let { song, engine } = $props();
  const motifs = song.motifs || [];
</script>

<div class="panel">
  <div class="panel-head"><span>Motifs to learn</span></div>
  <div class="panel-body">
    {#each motifs as m}
      <MotifCard motif={m} {song} {engine} />
    {:else}
      <p class="empty">No motifs.</p>
    {/each}
  </div>
</div>

<style>
  .panel-body { display: flex; flex-direction: column; gap: var(--s-2); }
  .empty { color: var(--text-faint); font-size: var(--t-sm); padding: var(--s-2); }
</style>
