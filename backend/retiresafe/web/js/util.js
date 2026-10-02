// Rendering helpers. Every interpolated value is HTML-escaped unless it was produced by html`` or raw():
// evidence records carry text copied from repositories and DNS, which must never become markup.

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);

class Safe {
  constructor(s) { this.s = s; }
  toString() { return this.s; }
}
export const raw = (s) => new Safe(String(s));

function part(v) {
  if (v === null || v === undefined || v === false) return "";
  if (v instanceof Safe) return v.s;
  if (Array.isArray(v)) return v.map(part).join("");
  return esc(v);
}

export function html(strings, ...vals) {
  let out = strings[0];
  for (let i = 0; i < vals.length; i++) out += part(vals[i]) + strings[i + 1];
  return new Safe(out);
}

export function mount(el, content) { el.innerHTML = part(content); }

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// ---------- formatting ----------
export function num(n, digits = 0) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}
export function compact(n) {
  if (n === null || n === undefined) return "—";
  const a = Math.abs(n);
  if (a >= 1e6) return (n / 1e6).toFixed(a >= 1e7 ? 0 : 1) + "M";
  if (a >= 1e4) return (n / 1e3).toFixed(0) + "k";
  if (a >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(Math.round(n * 100) / 100);
}
export function days(d) {
  if (d === null || d === undefined) return "—";
  if (d < 1 / 24) return `${num(d * 1440, 1)} min`;
  if (d < 1) return `${num(d * 24, 1)} h`;
  return `${num(d, 1)} d`;
}
export function rate(r) {
  if (r === null || r === undefined) return "—";
  return r >= 100 ? `${num(r, 0)}/d` : `${num(r, 2)}/d`;
}
export function when(iso, withTime = true) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (x) => String(x).padStart(2, "0");
  const date = `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}`;
  return withTime ? `${date} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())} UTC` : date;
}
export function ago(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (!Number.isFinite(s)) return "";
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}
export const shortId = (id) => (id || "").slice(0, 8);
export const bytes = (b) => (b === undefined || b === null) ? "—"
  : b >= 1 << 30 ? `${(b / 2 ** 30).toFixed(2)} GB` : b >= 1 << 20 ? `${(b / 2 ** 20).toFixed(1)} MB`
  : b >= 1024 ? `${(b / 1024).toFixed(1)} KB` : `${b} B`;

// ---------- vocabulary ----------
export const VERDICT = {
  block: { label: "Block", hint: "a surviving reference would hand traffic to whoever reclaims the name" },
  tombstone: { label: "Tombstone", hint: "keep owning the name, delete the content" },
  release: { label: "Release", hint: "the name can be let go" },
  review: { label: "Review", hint: "evidence is incomplete; a person decides" },
  not_name_bearing: { label: "No name at risk", hint: "deleting it releases no reclaimable name" },
};
export const VERDICT_ORDER = ["block", "review", "tombstone", "release", "not_name_bearing"];
export const COND = {
  c1: { short: "Released", long: "C1 · The name is given up", q: "Does this change give the name up?" },
  c2: { short: "Claimable", long: "C2 · Someone else can claim it", q: "Could another account register the same name afterwards?" },
  c3: { short: "Still pointed at", long: "C3 · A pointer survives", q: "Does a DNS record, config or code line still point at the name?" },
  c4: { short: "Still used", long: "C4 · Someone still uses it", q: "Is anyone still sending requests along that pointer?" },
  c5: { short: "Would be trusted", long: "C5 · Nothing would stop it", q: "Would the consumer accept content from a new owner?" },
};
export const verdictBadge = (v) => html`<span class="badge v-${v}">${(VERDICT[v] || { label: v }).label}</span>`;
export const triLabel = (v) => v === "true" ? "TRUE" : v === "false" ? "FALSE" : "UNKNOWN";

export function download(name, text, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

let toastTimer;
export function toast(msg) {
  let t = $(".toast");
  if (!t) { t = document.createElement("div"); t.className = "toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 2600);
}

export async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast("Copied to clipboard"); }
  catch { toast("Copy failed: select the text and copy manually"); }
}

// ---------- icons (stroke icons drawn for this console) ----------
const I = {
  shield: '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6L12 3Z"/>',
  list: '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  compare: '<path d="M7 4v16M17 4v16M3 8l4-4 4 4M13 16l4 4 4-4"/>',
  radar: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 12 18 6"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15Z"/><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  alert: '<path d="M12 4 2.5 20h19L12 4Z"/><path d="M12 10v4M12 17h.01"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  play: '<path d="M7 5v14l11-7L7 5Z"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M16 7l3 3"/>',
  ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  print: '<path d="M7 9V3h10v6M7 17H4v-7h16v7h-3M7 14h10v7H7z"/>',
};
export const icon = (name) => raw(`<svg viewBox="0 0 24 24" aria-hidden="true">${I[name] || ""}</svg>`);
