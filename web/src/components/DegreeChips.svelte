<script>
  import { tokenizeDegrees, tokenSemitone, PALETTE } from "../lib/sonofield.js";
  let { text = "" } = $props();
  // A token that is only punctuation (a bare "/", "·", "-") is a phrase separator,
  // not a chord — render it as a faint divider. Slash-chords like "V/♭VII" still
  // contain letters/numerals so they remain a single chip.
  const isSep = (t) => !/[A-Za-z0-9]/.test(t);
  let toks = $derived(tokenizeDegrees(text).map((t) => ({ t, sep: isSep(t), semi: tokenSemitone(t) })));
</script>

<span class="chips">
  {#each toks as k}
    {#if k.sep}<span class="sep">{k.t}</span>
    {:else}<span class="chip" style="--c:{k.semi != null ? PALETTE[k.semi] : '#5b6270'}">{k.t}</span>{/if}
  {/each}
</span>

<style>
  .chips { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 4px; }
  .chip { font: 600 12px var(--mono); padding: 2px 8px; border-radius: var(--r-sm);
    color: var(--c); background: color-mix(in srgb, var(--c) 16%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 45%, transparent); }
  .sep { color: var(--text-faint); font-size: 12px; padding: 0 1px; }
</style>
