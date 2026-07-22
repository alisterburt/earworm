<script>
  import { stemMeta, melodicStems } from "../lib/stems.js";
  import { selectedStem, relativeMode, transpose } from "../lib/stores.js";
  import { notePc, pcColor, keyUsesFlats, transposeLabel, tokenSemitone, PALETTE } from "../lib/sonofield.js";

  let { motif, song, engine } = $props();
  const tonicPc = notePc(song.key?.tonic || "C");
  // absolute chips respell to the transposed key; colours stay (degree-relative)
  let flats = $derived(keyUsesFlats(tonicPc + $transpose, song.key?.mode || "major"));
  // Each token shows its degree/roman or its absolute note/chord per the toggle,
  // coloured by pitch class either way. Fall back to a parsed degrees string.
  const tokens = motif.tokens
    || (motif.degrees || "").split(/\s+/).filter(Boolean).map((d) => ({ deg: d, note: d, pc: null }));
  // Colour each chip by its scale degree (key-independent), so it matches the
  // degree shown AND stays correct for motifs whose key isn't the song's global
  // key. Falls back to pitch-class colour, then neutral.
  const chipColor = (tk) => {
    const semi = tokenSemitone(tk.deg);
    return semi != null ? PALETTE[semi] : (tk.pc != null ? pcColor(tk.pc, tonicPc) : "#5b6270");
  };
  // Motif's local key, shown only when it differs from the song's global key.
  const localKey = motif.key && motif.key !== song.key?.name ? motif.key : null;
  const TYPE = {
    progression: { label: "Progression", color: "#6a7bff" },
    melody: { label: "Melody", color: "#e74da7" },
    bass: { label: "Bass", color: "#06d6a0" },
    lick: { label: "Lick", color: "#f4a261" },
  };
  const typ = (t) => TYPE[t] || { label: t || "Motif", color: "#9aa3b2" };
  const melodic = new Set(melodicStems(song));

  // The single melodic instrument this motif belongs to (else null).
  const soloInst = (() => {
    const m = (motif.instruments || []).filter((i) => melodic.has(i));
    return m.length === 1 ? m[0] : null;
  })();

  const db = song.downbeats || [];
  const dur = song.duration || 0;
  const barStart = (n) => db.length ? db[Math.min(db.length - 1, Math.max(0, n - 1))] : null; // 1-indexed bar n
  const barEnd = (m) => db.length ? (m < db.length ? db[m] : dur) : null; // end of bar m

  // Resolve one reference piece to a bar-aligned {start,end} range: a "N-M" bar
  // range, then a named section, then a bare/"bar N" number.
  function pieceRange(piece) {
    const range = /(\d+)\s*[-–—]\s*(\d+)/.exec(piece);
    if (range && db.length) return { start: barStart(+range[1]), end: barEnd(+range[2]) };
    for (const s of song.sections || [])
      if (piece.toLowerCase().includes(s.name.toLowerCase())) return { start: s.start, end: s.end };
    const n = /\bbar\s*(\d+)/i.exec(piece) || /^\s*(\d+)\b/.exec(piece);
    if (n && db.length) return { start: barStart(+n[1]), end: barEnd(+n[1]) };
    return null;
  }

  // Each comma-separated reference in `bars` becomes its own link.
  const pieces = (motif.bars || "").split(/\s*,\s*/).map((p) => p.trim()).filter(Boolean)
    .map((text) => ({ text, r: pieceRange(text) }));

  // Clicking a reference loops that span (replacing any existing loop), seeks to
  // its start, and shows+solos the motif's instrument when it has just one.
  function go(r) {
    if (soloInst && engine) { selectedStem.set(soloInst); engine.setActive([soloInst]); }
    if (!engine) return;
    if (r && r.start != null && r.end != null && r.end > r.start) {
      engine.setLoop({ start: r.start, end: r.end });
      engine.seek(r.start + 0.001);
    } else {
      engine.setLoop(null);
    }
  }
</script>

<div class="motif" style="--t:{typ(motif.type).color}">
  <div class="head">
    <span class="badge">{typ(motif.type).label}</span>
    <span class="name">{motif.name}</span>
    {#if localKey}<span class="mkey" title="this motif's key">{localKey}</span>{/if}
  </div>
  {#if tokens.length}
    <span class="chips">
      {#each tokens as tk}
        <span class="chip" style="--c:{chipColor(tk)}">{$relativeMode ? tk.deg : transposeLabel(tk.note, $transpose, flats)}</span>
      {/each}
    </span>
  {/if}
  {#if motif.description}<p class="desc">{motif.description}</p>{/if}
  <div class="foot">
    {#if pieces.length}
      <span class="where">
        {#each pieces as pc, i}{#if i}<span class="sep">, </span>{/if}{#if pc.r || soloInst}<button class="link" onclick={() => go(pc.r)} title={soloInst ? `loop + solo ${soloInst}` : "loop this motif"}>{pc.text}</button>{:else}{pc.text}{/if}{/each}
      </span>
    {/if}
    <span class="insts">{#each motif.instruments || [] as inst}<span title={inst}>{stemMeta(inst).icon}</span>{/each}</span>
  </div>
</div>

<style>
  .motif { background: var(--surface-2); border: 1px solid var(--border);
    border-left: 3px solid var(--t); border-radius: var(--r-sm);
    padding: var(--s-3); display: flex; flex-direction: column; gap: var(--s-2); }
  .head { display: flex; align-items: center; gap: var(--s-2); }
  .badge { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
    color: var(--t); background: color-mix(in srgb, var(--t) 16%, transparent);
    padding: 2px 7px; border-radius: var(--r-sm); flex: none; }
  .name { font-weight: 650; font-size: var(--t-sm); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .mkey { flex: none; margin-left: auto; font-size: 9px; font-weight: 700; letter-spacing: .03em;
    color: var(--text-dim); background: color-mix(in srgb, var(--text-dim) 14%, transparent);
    padding: 2px 6px; border-radius: var(--r-sm); }
  .chips { display: inline-flex; flex-wrap: wrap; gap: 4px; }
  .chip { font: 600 12px var(--mono); padding: 2px 8px; border-radius: var(--r-sm);
    color: var(--c); background: color-mix(in srgb, var(--c) 16%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 45%, transparent); }
  .desc { color: var(--text-dim); font-size: var(--t-xs); margin: 0; line-height: 1.45; }
  .foot { display: flex; align-items: center; justify-content: space-between; gap: var(--s-2); margin-top: 2px; }
  .where { color: var(--text-faint); font-size: var(--t-xs); line-height: 1.5; }
  .where .sep { color: var(--text-faint); }
  .where .link { background: none; border: none; padding: 0; cursor: pointer; font-size: var(--t-xs);
    color: color-mix(in srgb, var(--t) 80%, var(--text-dim)); font-weight: 600;
    border-bottom: 1px dashed color-mix(in srgb, var(--t) 50%, transparent); border-radius: 0; }
  .where .link:hover { color: var(--t); border-bottom-color: var(--t); }
  .insts { display: flex; gap: 4px; font-size: 13px; }
</style>
