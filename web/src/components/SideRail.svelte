<script>
  import StemsPanel from "./StemsPanel.svelte";
  import MotifPanel from "./MotifPanel.svelte";
  let { song, engine } = $props();
</script>

<aside class="rail">
  <StemsPanel {song} {engine} />
  {#if (song.motifs || []).length}<MotifPanel {song} {engine} />{/if}
</aside>

<style>
  /* Tracks stays fixed at the top; motifs panel takes the slack and scrolls. */
  .rail { display: flex; flex-direction: column; gap: var(--s-3); min-height: 0; height: 100%; }
  .rail > :global(.panel) { flex: 0 0 auto; }
  .rail > :global(.panel:last-child) { flex: 1 1 auto; min-height: 0; }
</style>
