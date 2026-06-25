<script>
  import { relativeMode } from "../lib/stores.js";
</script>

<!-- uses the shared global `.seg` segmented-control style (styles/app.css) -->
<div class="seg" role="group" aria-label="note naming">
  <button class:active={!$relativeMode} onclick={() => relativeMode.set(false)}>Notes</button>
  <button class:active={$relativeMode} onclick={() => relativeMode.set(true)}>Degrees</button>
</div>
