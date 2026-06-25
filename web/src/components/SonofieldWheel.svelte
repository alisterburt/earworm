<script>
  import { PALETTE, DEGREE_LABELS, FIFTHS } from "../lib/sonofield.js";
  let { size = 200, playing = false, onToggle = () => {}, labels = true } = $props();

  const cx = size / 2, cy = size / 2;
  const R = size * 0.42;
  const dot = labels ? size * 0.045 : size * 0.035;
  const dots = FIFTHS.map((semi, i) => {
    const a = (i / 12) * Math.PI * 2;
    return { x: cx + R * Math.sin(a), y: cy - R * Math.cos(a), color: PALETTE[semi], label: DEGREE_LABELS[semi] };
  });
  const cr = size * 0.27; // center disc radius
</script>

<svg width={size} height={size} viewBox="0 0 {size} {size}" class="wheel">
  {#each dots as d}
    <circle cx={d.x} cy={d.y} r={dot} fill={d.color} opacity={labels ? 1 : 0.92} />
    {#if labels}<text x={d.x} y={d.y - dot - 4} text-anchor="middle" class="lbl">{d.label}</text>{/if}
  {/each}
  <g class="center" role="button" tabindex="0" onclick={onToggle}
     onkeydown={(e) => (e.key === "Enter" || e.key === " ") && onToggle()}>
    <circle {cx} {cy} r={cr} fill="var(--surface-3)" stroke="var(--border-strong)" />
    {#if playing}
      <rect x={cx - size*0.075} y={cy - size*0.08} width={size*0.05} height={size*0.16} rx={size*0.018} fill="var(--text)" />
      <rect x={cx + size*0.025} y={cy - size*0.08} width={size*0.05} height={size*0.16} rx={size*0.018} fill="var(--text)" />
    {:else}
      <path d="M {cx - size*0.055} {cy - size*0.085} L {cx + size*0.095} {cy} L {cx - size*0.055} {cy + size*0.085} Z" fill="var(--text)" />
    {/if}
  </g>
</svg>

<style>
  .wheel { display: block; }
  .lbl { fill: var(--text-dim); font-size: 10px; font-family: var(--font); }
  .center { cursor: pointer; }
  .center circle { transition: stroke var(--dur) var(--ease), filter var(--dur) var(--ease); }
  .center:hover circle { stroke: var(--accent); filter: drop-shadow(0 0 10px color-mix(in srgb, var(--accent) 50%, transparent)); }
</style>
