import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// base: "/" in dev, "/earworm/" for a GitHub Pages project site.
// Override at build time with EARWORM_BASE=/whatever/ npm run build.
export default defineConfig({
  base: process.env.EARWORM_BASE || "/",
  plugins: [svelte()],
});
