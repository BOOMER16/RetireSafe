// Operator tooling: findings queue, CLI reproduction, command palette and keyboard shortcuts.
import { $, $$, html, mount, download, copy, toast, triLabel } from "./util.js";

// ---------- findings ----------
const SEV = { hijackable: 0, unknown: 1, waived: 2, safe: 3 };
export const STATUS_LABEL = { hijackable: "Hijackable", unknown: "Unverified", waived: "Waived", safe: "Broken" };

/** One row per reference path in the record (nothing inferred). */
export function findingsOf(rec, label) {
  const out = [];
  rec.resources.forEach((r) => r.paths.forEach((p) => {
    const ref = r.references.find((x) => x.id === p.reference_id) || {};
    out.push({
      status: p.status, resource: r.resource.address, name: r.resource.name || r.resource.address, verdict: r.verdict,
      kind: ref.kind || "?", method: ref.method || "", location: ref.location || p.reference_id, text: ref.text || "",
      broken: p.broken_by || [], conds: p.conditions, assessment: rec.assessment_id, label, as_of: rec.as_of,
      href: `#/a/${rec.assessment_id}/r/${encodeURIComponent(r.resource.address)}`,
    });
  }));
  return out.sort((a, b) => SEV[a.status] - SEV[b.status]);
}

const condStrip = (conds) => html`<span class="cstrip">${["c1", "c2", "c3", "c4", "c5"].map((c) => {
  const v = conds[c] ? conds[c].value : "unknown";
  return html`<i class="cb ${v === "true" ? "t" : v === "false" ? "f" : "u"}" title="${c.toUpperCase()} ${triLabel(v)}"></i>`;
})}</span>`;

export function findingsTable(rows, { id = "ft", showAssessment = false, initial = "open" } = {}) {
  const n = (s) => rows.filter((f) => f.status === s).length;
  const filters = [["open", "Open", n("hijackable") + n("unknown")], ["hijackable", "Hijackable", n("hijackable")],
    ["unknown", "Unverified", n("unknown")], ["safe", "Broken", n("safe")], ["all", "All", rows.length]];
  return html`
    <div class="toolbar" data-ft="${id}">
      <div class="filters" role="tablist">${filters.map(([k, t, c]) => html`<button class="fbtn ${k === initial ? "on" : ""}" data-f="${k}" role="tab">${t} <b>${c}</b></button>`)}</div>
      <input class="input search" data-q placeholder="Filter by resource, file or kind" aria-label="filter findings">
      <button class="btn" data-csv>Export CSV</button>
    </div>
    <table class="t dense ft" id="${id}">
      <thead><tr><th>Status</th><th>C1–C5</th><th>Resource</th><th>Reference</th><th>Kind</th>${showAssessment ? html`<th>Assessment</th>` : ""}</tr></thead>
      <tbody>${rows.map((f) => html`
        <tr class="click" tabindex="0" data-href="${f.href}" data-status="${f.status}" data-text="${`${f.name} ${f.resource} ${f.location} ${f.kind} ${f.method}`.toLowerCase()}">
          <td><span class="sev sev-${f.status}">${STATUS_LABEL[f.status] || f.status}</span>${f.broken.length ? html`<div class="hash">breaks at ${f.broken.map((c) => c.toUpperCase()).join(",")}</div>` : ""}</td>
          <td>${condStrip(f.conds)}</td>
          <td><b class="small">${f.name}</b><div class="hash">${f.resource}</div></td>
          <td class="refcell"><div class="mono small">${f.location}</div><div class="hash trunc">${f.text}</div></td>
          <td class="mono small">${f.kind}${f.method ? html`<div class="hash">${f.method}</div>` : ""}</td>
          ${showAssessment ? html`<td class="small">${f.label}<div class="hash">as of ${(f.as_of || "").slice(0, 10)}</div></td>` : ""}
        </tr>`)}</tbody>
    </table>
    <div class="hash ft-empty hidden" data-empty>No findings match this filter.</div>`;
}

export function wireFindings(id, rows) {
  const bar = $(`[data-ft="${id}"]`);
  const table = $(`#${id}`);
  if (!bar || !table) return;
  let f = $(".fbtn.on", bar)?.dataset.f || "open";
  const apply = () => {
    const q = $("[data-q]", bar).value.trim().toLowerCase();
    let shown = 0;
    $$("tbody tr", table).forEach((tr) => {
      const st = tr.dataset.status;
      const okF = f === "all" || (f === "open" ? st === "hijackable" || st === "unknown" : st === f);
      const ok = okF && (!q || tr.dataset.text.includes(q));
      tr.classList.toggle("hidden", !ok);
      shown += ok;
    });
    $(`[data-empty]`, bar.parentElement)?.classList.toggle("hidden", shown > 0);
  };
  $$(".fbtn", bar).forEach((b) => b.addEventListener("click", () => {
    $$(".fbtn", bar).forEach((x) => x.classList.toggle("on", x === b));
    f = b.dataset.f;
    apply();
  }));
  $("[data-q]", bar).addEventListener("input", apply);
  $("[data-csv]", bar).addEventListener("click", () => {
    const vis = new Set($$("tbody tr:not(.hidden)", table).map((tr) => tr.dataset.href + "|" + tr.dataset.text));
    const keep = rows.filter((r) => vis.has(r.href + "|" + `${r.name} ${r.resource} ${r.location} ${r.kind} ${r.method}`.toLowerCase()));
    download("retiresafe-findings.csv", toCsv(keep), "text/csv");
  });
  apply();
}

// Spreadsheet formula injection: cells starting with = + - @ (or tab/CR) are prefixed with a quote.
const cell = (v) => {
  let s = String(v ?? "");
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return `"${s.replace(/"/g, '""')}"`;
};
function toCsv(rows) {
  const head = ["status", "resource_address", "name", "verdict", "kind", "method", "location", "c1", "c2", "c3", "c4", "c5", "broken_by", "assessment_id", "as_of"];
  const lines = rows.map((r) => [r.status, r.resource, r.name, r.verdict, r.kind, r.method, r.location,
    ...["c1", "c2", "c3", "c4", "c5"].map((c) => (r.conds[c] ? r.conds[c].value : "")), r.broken.join(" "), r.assessment, r.as_of].map(cell).join(","));
  return [head.join(","), ...lines].join("\r\n") + "\r\n";
}

// ---------- CLI reproduction ----------
/** Rebuild the `retiresafe assess` command from what the record stores; <…> marks values it does not store. */
export function reproduce(rec) {
  const q = (s) => (/^[\w@%+=:,./<>-]+$/.test(s) ? s : `'${String(s).replace(/'/g, "'\\''")}'`);
  const a = ["retiresafe assess"];
  const ins = rec.inputs || [];
  ins.filter((i) => i.role === "terraform_plan").forEach((i) => a.push(`--plan ${q(i.name)}`));
  ins.filter((i) => i.role === "dns_inventory").forEach((i) => a.push(`--dns ${q(i.name)}`));
  ins.filter((i) => i.role === "repository").forEach((i) => a.push(`--repo ${q(`${i.label || i.name}=<path-to-${i.label || i.name}>`)}`));
  const seen = new Set();
  ins.filter((i) => i.role.startsWith("access_log")).forEach((i) => {
    if (seen.has(i.name)) return;
    seen.add(i.name);
    const fmt = i.role.split(":")[1] || "<format>";
    const prefixes = new Set();
    rec.resources.forEach((r) => r.traffic.forEach((t) => {
      const m = t.source.match(/^(.*?)(?:\[(.*)\])?$/);
      if (m && m[1] === i.name) prefixes.add(m[2] || "");
    }));
    (prefixes.size ? [...prefixes] : [""]).forEach((p) => a.push(`--log ${q(`${i.name},format=${fmt}${fmt === "clf" ? ",host=<host>" : ""}${p ? `,path_prefix=${p}` : ""}`)}`));
  });
  const pol = rec.policy || {};
  if (pol.mode) a.push(`--mode ${pol.mode}`);
  if (pol.enforcement) a.push(`--enforcement ${pol.enforcement}`);
  (pol.org_account_ids || []).forEach((x) => a.push(`--org-account ${q(x)}`));
  (pol.internal_domains || []).forEach((x) => a.push(`--internal-domain ${q(x)}`));
  (pol.internal_cidrs || []).forEach((x) => a.push(`--internal-cidr ${q(x)}`));
  if (rec.as_of) a.push(`--as-of ${q(rec.as_of)}`);
  a.push("--out evidence.json --markdown report.md --sarif findings.sarif");
  return a.join(" \\\n    ");
}

// ---------- command palette ----------
let palEl, helpEl, items = [], sel = 0, source;

export function initPalette(getItems) {
  source = getItems;
  palEl = document.createElement("div");
  palEl.className = "overlay hidden";
  palEl.innerHTML = '<div class="pal" role="dialog" aria-modal="true" aria-label="Command palette"><div class="pal-in-wrap"><span class="pal-prompt">›</span><input class="pal-in" autocomplete="off" spellcheck="false" placeholder="Jump to an assessment, resource or command" aria-label="command"></div><div class="pal-list" role="listbox"></div><div class="pal-foot"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>↵</kbd> open</span><span><kbd>esc</kbd> close</span></div></div>';
  document.body.appendChild(palEl);
  palEl.addEventListener("click", (e) => { if (e.target === palEl) closePalette(); });
  const inp = $(".pal-in", palEl);
  inp.addEventListener("input", () => { sel = 0; renderPal(inp.value); });
  inp.addEventListener("keydown", (e) => {
    const vis = filtered(inp.value);
    if (e.key === "ArrowDown") { sel = Math.min(sel + 1, vis.length - 1); renderPal(inp.value); e.preventDefault(); }
    else if (e.key === "ArrowUp") { sel = Math.max(sel - 1, 0); renderPal(inp.value); e.preventDefault(); }
    else if (e.key === "Enter") { const it = vis[sel]; if (it) { closePalette(); it.run(); } e.preventDefault(); }
    else if (e.key === "Escape") closePalette();
  });

  helpEl = document.createElement("div");
  helpEl.className = "overlay hidden";
  helpEl.innerHTML = '<div class="pal help" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts"><div class="pal-head">Keyboard shortcuts</div><div class="keys">'
    + [["⌘K / Ctrl K  or  /", "command palette"], ["g r", "reviews"], ["g n", "new check"], ["g c", "before / after"], ["g d", "drift scan"], ["g s", "sources"],
      ["g f", "findings of this assessment"], ["g e", "evidence of this assessment"], ["j / k", "next / previous row"], ["↵", "open row"], ["t", "light / dark"], ["?", "this help"], ["esc", "close"]]
      .map(([k, d]) => `<div><span>${k.split("  ").map((x) => `<kbd>${x}</kbd>`).join(" or ")}</span><span>${d}</span></div>`).join("")
    + '</div><div class="pal-foot"><span><kbd>esc</kbd> close</span></div></div>';
  document.body.appendChild(helpEl);
  helpEl.addEventListener("click", (e) => { if (e.target === helpEl) helpEl.classList.add("hidden"); });
}

function filtered(q) {
  const t = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return items.filter((it) => t.every((w) => `${it.group} ${it.title} ${it.sub || ""}`.toLowerCase().includes(w))).slice(0, 40);
}
function renderPal(q) {
  const vis = filtered(q);
  let last = "";
  mount($(".pal-list", palEl), vis.length ? vis.map((it, i) => {
    const head = it.group !== last ? html`<div class="pal-group">${it.group}</div>` : "";
    last = it.group;
    return html`${head}<div class="pal-item ${i === sel ? "on" : ""}" role="option" data-i="${i}"><span>${it.title}</span><span class="hash">${it.sub || ""}</span></div>`;
  }) : html`<div class="pal-empty hash">No matches</div>`);
  $$(".pal-item", palEl).forEach((el) => el.addEventListener("click", () => { closePalette(); vis[Number(el.dataset.i)].run(); }));
  $(".pal-item.on", palEl)?.scrollIntoView({ block: "nearest" });
}
export async function openPalette() {
  helpEl.classList.add("hidden");
  palEl.classList.remove("hidden");
  const inp = $(".pal-in", palEl);
  inp.value = "";
  sel = 0;
  items = [];
  renderPal("");
  inp.focus();
  try { items = await source(); } catch { items = []; }
  renderPal(inp.value);
}
function closePalette() { palEl.classList.add("hidden"); }

// ---------- keyboard ----------
export function initKeys({ go, toggleTheme, current }) {
  let pending = null;
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openPalette(); return; }
    if (e.key === "Escape") { palEl.classList.add("hidden"); helpEl.classList.add("hidden"); return; }
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    if (pending) {
      const k = e.key.toLowerCase();
      pending = null;
      const cur = current();
      const map = { r: "#/", n: "#/new", c: "#/compare", d: "#/scan", s: "#/knowledge",
        f: cur ? `#/a/${cur}/findings` : null, e: cur ? `#/a/${cur}/evidence` : null };
      if (map[k]) { go(map[k]); e.preventDefault(); }
      return;
    }
    if (e.key === "g") { pending = setTimeout(() => { pending = null; }, 1200); return; }
    if (e.key === "/") { e.preventDefault(); openPalette(); return; }
    if (e.key === "?") { helpEl.classList.toggle("hidden"); return; }
    if (e.key === "t") { toggleTheme(); return; }
    if (e.key === "j" || e.key === "k") {
      const rows = $$("[data-href]:not(.hidden)").filter((el) => el.offsetParent !== null);
      if (!rows.length) return;
      const i = rows.indexOf(document.activeElement);
      const n = e.key === "j" ? Math.min(i + 1, rows.length - 1) : Math.max(i - 1, 0);
      rows[i < 0 ? 0 : n].focus();
      e.preventDefault();
    }
  });
}

export { copy, toast };
