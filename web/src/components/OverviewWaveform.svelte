<script>
  import { onMount } from "svelte";
  import { transport } from "../lib/engine.js";
  import { notePc, spanColor, pcColor, chordRootPc, chordName, chordColorAt,
    keyUsesFlats, transposeLabel, keyAt } from "../lib/sonofield.js";
  import { relativeMode, transpose } from "../lib/stores.js";
  import { presentStems, stemMeta } from "../lib/stems.js";
  import { loadStemPeaks } from "../lib/stempeaks.js";

  let { song, engine } = $props();
  let canvas, wrap;
  let width = $state(1000);
  const H = 92;
  // key in effect at time t (honours mid-song key changes via song.keys)
  const keyRegions = song.keys?.length ? song.keys : null;
  const keyFallback = song.key || { tonic: "C", mode: "major" };
  const keyAtT = (t) => keyAt(keyRegions, t, keyFallback);
  const tonicAtT = (t) => notePc(keyAtT(t).tonic || "C");
  const chords = song.chords || [];
  const sections = song.sections || [];
  const dur = song.duration || 1;

  const hx = (h) => [parseInt(h.slice(1,3),16), parseInt(h.slice(3,5),16), parseInt(h.slice(5,7),16)];
  function mix(a, b, t) { const x=hx(a), y=hx(b);
    return `rgb(${x[0]+(y[0]-x[0])*t|0},${x[1]+(y[1]-x[1])*t|0},${x[2]+(y[2]-x[2])*t|0})`; }
  const colorOf = (s) => spanColor(chords, s.start, s.end, tonicAtT(s.start)) || "#7a8499";
  // Waveform colour follows the CHORD sounding at each point (muted toward a
  // neutral so it stays legible); section bands/popover keep their section colour.
  const waveColorAt = (t) => mix(chordColorAt(chords, t, tonicAtT(t)) || "#56607a", "#39435a", 0.40);

  let cur = $derived(sections.findIndex((s) => $transport.time >= s.start && $transport.time < s.end));

  // hover context block for a section: vibe + chord motif + lyrics
  let hovered = $state(null);
  // Chords of a section: assign each chord by its MIDPOINT so one straddling the
  // boundary lands in the section it mostly occupies (not double-counted), then
  // collapse a sustained chord to a single entry.
  function secChordSeq(s) {
    const out = [];
    for (const c of chords) {
      if (c.label === "N") continue;
      const mid = (c.start + c.end) / 2;
      if (mid < s.start || mid >= s.end) continue;
      if (out[out.length - 1] !== c.label) out.push(c.label);
    }
    return out;
  }

  // Repeating chord cycle within a section: shortest period whose repetition
  // covers the sequence, tolerating ~1-in-6 mismatches (e.g. a turnaround chord).
  function chordMotif(seq) {
    const n = seq.length;
    if (n < 4) return null;
    for (let p = 1; p <= Math.floor(n / 2); p++) {
      let miss = 0;
      for (let i = p; i < n; i++) if (seq[i] !== seq[i % p]) miss++;
      if (miss / (n - p) <= 0.17) return { cycle: seq.slice(0, p), reps: Math.round(n / p) };
    }
    return null;
  }

  // chip colour/text are computed in the hovered section's local key (tp/md)
  const chordColor = (lab, tp) => {
    const r = chordRootPc(lab);
    return r == null ? "#5b6270" : pcColor(r, tp);
  };
  // chip text: roman when relative, else the chord respelled into the transposed key
  const chLabel = (lab, tp, md) => $relativeMode
    ? (chordName(lab, tp, md, true) || lab)
    : transposeLabel(lab, $transpose, keyUsesFlats(tp + $transpose, md));
  function secLyrics(s) {
    return (song.lyrics?.segments || [])
      .filter((g) => g.start < s.end - 0.1 && g.end > s.start + 0.1)
      .map((g) => g.text.trim())
      .filter(Boolean);
  }
  // Popover left (px), clamped so it never spills off either edge of the overview.
  let popW = $state(320);
  function popLeft(s) {
    const center = ((s.start + s.end) / 2 / dur) * width;
    const m = 6;
    return Math.max(m, Math.min(center - popW / 2, width - popW - m));
  }

  // ---- mix / individual-tracks toggle (button shown on hover). A one-shot
  // treadmill slide animates between the combined waveform (roll 0) and the
  // stacked stem lanes (roll 1). ----
  let stemPeaks = null, loadingStems = false;
  let roll = 0, target = 0, anim = null; // 0 = mix, 1 = individual tracks
  let tracksMode = $state(false), hovering = $state(false);
  let tFrom = 0, tStart = 0, tDur = 1;
  const SLIDE_MS = 420; // transition duration (higher = slower)
  const smooth = (u) => u * u * (3 - 2 * u); // ease-in-out

  function tweenTo(t) {
    tFrom = roll; target = t; tStart = performance.now();
    tDur = Math.max(150, Math.abs(target - tFrom) * SLIDE_MS);
    startAnim();
  }

  function ensureStems() {
    if (stemPeaks || loadingStems) return;
    loadingStems = true;
    loadStemPeaks(song).then((s) => { stemPeaks = s; render(); }).catch(() => {})
      .finally(() => { loadingStems = false; });
  }
  function toggleTracks() {
    tracksMode = !tracksMode;
    ensureStems();
    tweenTo(tracksMode ? 1 : 0);
  }

  function startAnim() {
    if (anim) return;
    const tick = () => {
      const u = Math.min(1, (performance.now() - tStart) / tDur);
      roll = tFrom + (target - tFrom) * smooth(u);
      render();
      if (u >= 1) { roll = target; anim = null; } else anim = requestAnimationFrame(tick);
    };
    anim = requestAnimationFrame(tick);
  }

  function render() {
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr; canvas.height = H * dpr;
    canvas.style.width = width + "px"; canvas.style.height = H + "px";
    const ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, H);
    ctx.save(); ctx.beginPath(); ctx.rect(0, 0, width, H); ctx.clip(); // never paint outside the wave area
    const kA = Math.floor(roll);
    for (const k of [kA, kA + 1]) {
      const yOff = (k - roll) * H;
      if (yOff <= -H || yOff >= H) continue; // panel fully off-screen
      if ((((k % 2) + 2) % 2) === 0) drawCombined(ctx, yOff); else drawStems(ctx, yOff);
    }
    // depth: darken top & bottom edges (fixed to the frame)
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, "rgba(8,9,12,0.55)"); g.addColorStop(0.5, "rgba(8,9,12,0)"); g.addColorStop(1, "rgba(8,9,12,0.55)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, width, H);
    // section dividers (fixed)
    ctx.strokeStyle = "rgba(255,255,255,0.10)"; ctx.lineWidth = 1;
    for (const s of sections) { const x = Math.round((s.start / dur) * width) + 0.5;
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    ctx.restore();
  }

  function drawCombined(ctx, yOff) {
    const peaks = song.peaks || [], mid = H / 2 + yOff;
    for (let x = 0; x < width; x++) {
      const v = peaks[Math.floor((x / width) * peaks.length)] || 0;
      const h = v * (H * 0.44);
      ctx.fillStyle = waveColorAt((x / width) * dur);
      ctx.fillRect(x, mid - h, 1, Math.max(1, h * 2));
    }
  }

  function drawStems(ctx, yOff) {
    const names = stemPeaks ? stemPeaks.map((s) => s.name) : presentStems(song);
    const k = Math.max(1, names.length), lh = H / k;
    for (let i = 0; i < k; i++) {
      const name = names[i], col = stemMeta(name).color;
      const peaks = stemPeaks ? stemPeaks[i].peaks : null;
      const cy = yOff + lh * i + lh / 2, amp = lh * 0.42;
      if (i) { ctx.strokeStyle = "rgba(255,255,255,0.05)"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(0, yOff + lh * i + 0.5); ctx.lineTo(width, yOff + lh * i + 0.5); ctx.stroke(); }
      ctx.strokeStyle = col + "22"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(0, cy + 0.5); ctx.lineTo(width, cy + 0.5); ctx.stroke();
      if (peaks) {
        ctx.fillStyle = col; ctx.globalAlpha = 0.9;
        for (let x = 0; x < width; x++) {
          const h = (peaks[Math.floor((x / width) * peaks.length)] || 0) * amp;
          ctx.fillRect(x, cy - h, 1, Math.max(0.6, h * 2));
        }
        ctx.globalAlpha = 1;
      }
    }
  }

  onMount(() => {
    const ro = new ResizeObserver(() => { width = wrap.clientWidth; render(); });
    ro.observe(wrap); width = wrap.clientWidth; render();
    ensureStems(); // decode stems in the background so the first hover is instant
    return () => { ro.disconnect(); if (anim) cancelAnimationFrame(anim); };
  });

  function scrub(e) { const r = wrap.getBoundingClientRect(); engine.seek(((e.clientX - r.left) / r.width) * dur); }
  let dragging = false;
</script>

<div class="ov">
  <div class="wave" bind:this={wrap}
       onpointerenter={() => (hovering = true)} onpointerleave={() => (hovering = false)}
       onpointerdown={(e) => { dragging = true; wrap.setPointerCapture(e.pointerId); scrub(e); }}
       onpointermove={(e) => dragging && scrub(e)}
       onpointerup={(e) => { dragging = false; wrap.releasePointerCapture(e.pointerId); }}>
    <canvas bind:this={canvas}></canvas>
    <div class="playhead" style="left: {($transport.time / dur) * 100}%"></div>
    <button class="tracksbtn" class:show={hovering || tracksMode}
      onpointerdown={(e) => e.stopPropagation()} onclick={toggleTracks}>
      {tracksMode ? "mix" : "individual tracks"}
    </button>
  </div>
  {#if sections.length}
    <div class="sections">
      {#each sections as s, i}
        <button class="sec" class:cur={i === cur}
          style="left:{(s.start/dur)*100}%; width:{((s.end-s.start)/dur)*100}%; --c:{colorOf(s)}"
          onpointerenter={() => (hovered = i)} onpointerleave={() => (hovered = (hovered === i ? null : hovered))}
          onclick={() => engine.seek(s.start + 0.01)}><span>{s.name}</span></button>
      {/each}
    </div>
    {#if hovered != null}
      {@const s = sections[hovered]}
      {@const sk = keyAtT(s.start)}
      {@const sTonic = notePc(sk.tonic || "C")}
      {@const sMode = sk.mode || "major"}
      {@const ch = secChordSeq(s)}
      {@const motif = chordMotif(ch)}
      {@const extra = motif ? ch.filter((c) => !motif.cycle.includes(c)).filter((c, i, a) => a.indexOf(c) === i).length : new Set(ch).size}
      {@const showChords = ch.length > 0 && (!motif || extra > 1)}
      {@const ly = secLyrics(s)}
      <div class="pop" bind:clientWidth={popW} style="left:{popLeft(s)}px; --c:{colorOf(s)}">
        <div class="pop-name">{s.name}</div>
        {#if s.summary}<div class="pop-vibe">{s.summary}</div>{/if}
        {#if motif}
          <div class="pop-row"><span class="pop-cap">motif</span>
            <span class="chips">{#each motif.cycle as lab}<span class="chip" style="--c:{chordColor(lab, sTonic)}">{chLabel(lab, sTonic, sMode)}</span>{/each}{#if motif.reps > 1}<span class="reps">×{motif.reps}</span>{/if}</span></div>
        {/if}
        {#if showChords}
          <div class="pop-row"><span class="pop-cap">chords</span>
            <span class="chips">{#each ch as lab}<span class="chip" style="--c:{chordColor(lab, sTonic)}">{chLabel(lab, sTonic, sMode)}</span>{/each}</span></div>
        {/if}
        {#if ly.length}
          <div class="pop-row"><span class="pop-cap">lyrics</span>
            <div class="pop-lyrics">{#each ly.slice(0, 8) as line}<div>{line}</div>{/each}
              {#if ly.length > 8}<div class="more">…</div>{/if}</div></div>
        {:else}
          <div class="pop-row"><span class="pop-cap">lyrics</span><span class="pop-none">instrumental</span></div>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .ov { position: relative; display: flex; flex-direction: column; gap: 5px; flex: 1; min-width: 0; }
  .wave { position: relative; height: 92px; cursor: pointer; border-radius: var(--r-lg);
    overflow: hidden; background: #0e1015; box-shadow: inset 0 0 0 1px var(--border); }
  canvas { display: block; }
  .playhead { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--playhead);
    box-shadow: 0 0 8px var(--playhead); pointer-events: none; }
  .tracksbtn { position: absolute; top: 8px; right: 8px; padding: 3px 9px;
    font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
    border-radius: var(--r-pill); color: var(--text-dim);
    background: color-mix(in srgb, var(--surface) 82%, transparent);
    border: 1px solid var(--border); backdrop-filter: blur(6px);
    opacity: 0; transition: opacity var(--dur) var(--ease), color var(--dur) var(--ease);
    pointer-events: none; }
  .tracksbtn.show { opacity: 1; pointer-events: auto; }
  .tracksbtn:hover { color: var(--text); border-color: var(--border-strong); }
  .sections { position: relative; height: 24px; }
  .sec { position: absolute; top: 0; height: 100%; padding: 0 8px; border: none; margin: 0;
    border-radius: var(--r-sm); background: color-mix(in srgb, var(--c) 16%, var(--surface));
    color: var(--text-dim); font-size: var(--t-xs); font-weight: 600;
    overflow: hidden; white-space: nowrap; text-align: left;
    box-shadow: inset 2px 0 0 color-mix(in srgb, var(--c) 70%, transparent);
    transition: background var(--dur) var(--ease), color var(--dur) var(--ease); }
  .sec + .sec { margin-left: 2px; }
  .sec:hover { color: var(--text); background: color-mix(in srgb, var(--c) 28%, var(--surface)); }
  .sec.cur { color: var(--text); background: color-mix(in srgb, var(--c) 40%, var(--surface));
    box-shadow: inset 2px 0 0 var(--c), 0 0 0 1px color-mix(in srgb, var(--c) 55%, transparent); }

  /* hover context popover (floats below the section strip) */
  .pop { position: absolute; top: calc(100% + 6px); left: 0;
    z-index: 40; width: max-content; max-width: 340px; pointer-events: none;
    background: var(--surface-2); border: 1px solid var(--border-strong);
    border-top: 2px solid var(--c); border-radius: var(--r-md);
    box-shadow: var(--shadow-2); padding: var(--s-3); display: flex; flex-direction: column; gap: 6px; }
  .pop-name { font-weight: 700; font-size: var(--t-sm); color: var(--text); }
  .pop-vibe { color: var(--text-dim); font-size: var(--t-xs); line-height: 1.45; }
  .pop-row { display: flex; gap: var(--s-2); }
  .pop-cap { flex: none; width: 42px; color: var(--text-faint); font-size: 9px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .1em; padding-top: 3px; }
  .chips { display: inline-flex; flex-wrap: wrap; gap: 4px; align-items: center; }
  .chip { font: 600 11px var(--mono); padding: 1px 7px; border-radius: var(--r-sm);
    color: var(--c); background: color-mix(in srgb, var(--c) 16%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 40%, transparent); }
  .reps { color: var(--text-faint); font-size: 10px; font-weight: 700; margin-left: 2px; }
  .pop-lyrics { display: flex; flex-direction: column; gap: 1px; font-size: var(--t-xs);
    color: var(--text-dim); line-height: 1.4; }
  .pop-lyrics .more { color: var(--text-faint); }
  .pop-none { color: var(--text-faint); font-size: var(--t-xs); font-style: italic; }
</style>
