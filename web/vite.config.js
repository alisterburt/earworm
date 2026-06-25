import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// base: "/" in dev, "/chops/" for a GitHub Pages project site.
// Override at build time with CHOPS_BASE=/whatever/ npm run build.
export default defineConfig({
  base: process.env.CHOPS_BASE || "/",
  plugins: [svelte()],
});
