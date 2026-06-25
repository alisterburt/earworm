<script>
  import { route } from "./lib/router.js";
  import Library from "./routes/Library.svelte";
  import Song from "./routes/Song.svelte";

  // Lightweight (not secure) client-side gate. Password: bleepbloop — see README.
  let unlocked = $state(localStorage.getItem("chops-unlocked") === "1");
  let pw = $state("");
  let err = $state(false);
  function submit(e) {
    e?.preventDefault();
    if (pw === "bleepbloop") { unlocked = true; localStorage.setItem("chops-unlocked", "1"); }
    else { err = true; pw = ""; }
  }
</script>

{#if !unlocked}
  <div class="gate">
    <form onsubmit={submit}>
      <h1>chops</h1>
      <!-- svelte-ignore a11y_autofocus -->
      <input type="password" placeholder="password" bind:value={pw} class:err
             autofocus oninput={() => (err = false)} />
      <button type="submit">Enter</button>
    </form>
  </div>
{:else if $route.name === "song"}
  <Song id={$route.params.id} />
{:else}
  <Library />
{/if}

<style>
  .gate { height: 100vh; display: grid; place-items: center; }
  form { display: flex; flex-direction: column; gap: var(--s-3); align-items: center; }
  h1 { font-size: var(--t-2xl); margin: 0 0 var(--s-2); letter-spacing: -0.02em; }
  input { background: var(--surface-2); border: 1px solid var(--border); color: var(--text);
    border-radius: var(--r-pill); padding: 10px 18px; width: 240px; font-size: var(--t-md); text-align: center; }
  input:focus { outline: none; border-color: var(--accent); }
  input.err { border-color: var(--playhead); }
  button { padding: 8px 22px; border-radius: var(--r-pill); background: var(--accent);
    color: var(--accent-contrast); border-color: var(--accent); font-weight: 600; }
  button:hover { filter: brightness(1.08); border-color: var(--accent); }
</style>
