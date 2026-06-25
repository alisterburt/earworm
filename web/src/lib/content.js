// Helpers to resolve + fetch content assets under the configured base path.
const BASE = import.meta.env.BASE_URL; // "/" in dev, "/chops/" on GH Pages

export const assetUrl = (rel) => BASE + "content/" + rel;

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
