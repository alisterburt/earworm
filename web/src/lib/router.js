import { writable } from "svelte/store";

// Minimal hash router: #/, #/song/:id
function parse() {
  const hash = location.hash.slice(1) || "/";
  const [path] = hash.split("?");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "song" && parts[1]) return { name: "song", params: { id: parts[1] } };
  return { name: "library", params: {} };
}

export const route = writable(parse());
window.addEventListener("hashchange", () => route.set(parse()));
export const navigate = (to) => { location.hash = to; };
