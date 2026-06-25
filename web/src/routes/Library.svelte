<script>
  import { onMount } from "svelte";
  import { loadLibrary, assetUrl } from "../lib/content.js";
  import { navigate } from "../lib/router.js";

  let songs = $state(null);
  let error = $state(null);

  onMount(async () => {
    try { songs = await loadLibrary(); }
    catch (e) { error = e.message; songs = []; }
  });

  const fmt = (s) => `${(s/60)|0}:${String((s|0)%60).padStart(2,"0")}`;
</script>

<div class="page">
  <header>
    <h1>chops</h1>
    <p class="sub">your library {#if songs?.length}· {songs.length} {songs.length === 1 ? "song" : "songs"}{/if}</p>
  </header>

  {#if songs === null}
    <p class="muted">loading…</p>
  {:else if songs.length === 0}
    <p class="muted">No songs yet. Run <code>uv run chops process "&lt;file&gt;.mp3"</code>.</p>
  {:else}
    <div class="grid">
      {#each songs as s (s.id)}
        <button class="card" onclick={() => navigate(`/song/${s.id}`)}>
          <div class="art">
            <img src={assetUrl(s.cover)} alt={s.title} loading="lazy" />
          </div>
          <div class="meta">
            <div class="title" title={s.title}>{s.title}</div>
            <div class="artist" title={s.artist}>{s.artist}</div>
            <div class="tags">{s.key}{#if s.tempo} · {Math.round(s.tempo)} bpm{/if} · {fmt(s.duration)}</div>
          </div>
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page { max-width: 1200px; margin: 0 auto; padding: var(--s-7) var(--s-5) var(--s-8); }
  header { margin-bottom: var(--s-6); }
  h1 { font-size: var(--t-2xl); margin: 0; letter-spacing: -0.02em; }
  .sub { color: var(--text-dim); margin: var(--s-2) 0 0; }
  .muted { color: var(--text-dim); }
  code { background: var(--surface-2); padding: 2px 6px; border-radius: var(--r-sm); }

  .grid {
    display: grid; gap: var(--s-5);
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  }
  .card {
    display: block; text-align: left; padding: 0; background: none; border: none;
    border-radius: var(--r-lg);
  }
  .art {
    aspect-ratio: 1; border-radius: var(--r-lg); overflow: hidden;
    background: var(--surface-2); box-shadow: var(--shadow-card);
    transition: transform var(--dur) var(--ease);
  }
  .art img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .card:hover .art { transform: translateY(-4px) scale(1.012); }
  .meta { padding: var(--s-3) var(--s-1) 0; }
  .title { font-weight: 650; line-height: 1.25; }
  .artist { color: var(--text-dim); font-size: var(--t-sm); margin-top: 2px; }
  .tags { color: var(--text-faint); font-size: var(--t-xs); margin-top: var(--s-2); }
</style>
