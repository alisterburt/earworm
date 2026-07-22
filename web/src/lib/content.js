// Helpers to resolve + fetch content assets.
// When VITE_CONTENT_BASE is set (web/.env.production -> the R2 public URL),
// assets come from the CDN; otherwise from public/content next to the app.
const BASE = import.meta.env.BASE_URL; // "/" in dev, "/earworm/" on GH Pages
const CDN = import.meta.env.VITE_CONTENT_BASE;
const ROOT = CDN ? CDN.replace(/\/?$/, "/") : BASE + "content/";

export const assetUrl = (rel) => ROOT + rel;

export async function loadLibrary() {
  const r = await fetch(assetUrl("library.json"));
  if (!r.ok) throw new Error("no library.json");
  return r.json();
}

export async function loadSong(id) {
  const r = await fetch(assetUrl(`${id}/analysis.json`));
  if (!r.ok) throw new Error(`no analysis for ${id}`);
  const d = await r.json();
  d._base = assetUrl(`${id}/`); // for resolving its audio/cover/midi
  return d;
}
