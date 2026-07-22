import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { defineConfig, loadEnv } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// base: "/" in dev, "/earworm/" for a GitHub Pages project site.
// Override at build time with EARWORM_BASE=/whatever/ npm run build.
//
// VITE_CONTENT_BASE (web/.env.production) points the app at the CDN (R2 public
// URL). When set, builds leave public/content out of dist — songs are served
// from the CDN, not GitHub Pages. Dev always uses the local content dir.
export default defineConfig(({ mode }) => {
  const cdn = loadEnv(mode, process.cwd(), "VITE_").VITE_CONTENT_BASE;
  return {
    base: process.env.EARWORM_BASE || "/",
    plugins: [
      svelte(),
      // Skipping the public-dir copy also skips .nojekyll, which GH Pages needs.
      cdn && {
        name: "nojekyll-without-public-copy",
        closeBundle: () => writeFileSync(join(process.cwd(), "dist", ".nojekyll"), ""),
      },
    ],
    build: { copyPublicDir: !cdn },
  };
});
