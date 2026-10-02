// RetireSafe console: a reader for the evidence records the API produces. It shows only what a record
// contains; the only arithmetic it does is shown on screen (the quarantine formula).
import { api, ApiError, setApiKey } from "./api.js";
import { trafficChart, coverageSpark } from "./charts.js";
import {
  $, $$, html, raw, esc, mount, num, compact, days, rate, when, ago, shortId, bytes, download, copy, toast,
  VERDICT, VERDICT_ORDER, COND, verdictBadge, triLabel, icon,
} from "./util.js";

const view = $("#view");
const crumbsEl = $("#crumbs");
const actionsEl = $("#actions");
const CS = ["c1", "c2", "c3", "c4", "c5"];
const pad2 = (i) => String(i + 1).padStart(2, "0");

// ---------- per-browser conveniences (never relied on) ----------
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage disabled */ } },
};
const PILOT_LABEL = {
  before_strict: "Pilot · proposed deletion · strict",
  before_balanced: "Pilot · proposed deletion · balanced",
  after_strict: "Pilot · corrected change · strict",
};
const pilotTags = () => store.get("retiresafe.pilot", {});
function labelOf(id, s) {
  const tag = Object.entries(pilotTags()).find(([, v]) => v === id);
  if (tag) return PILOT_LABEL[tag[0]] || tag[0];
  return s && s.plan_input ? `${s.plan_input} · ${s.mode || ""}` : `Assessment ${shortId(id)}`;
}
function summaryOf(rec) {
  const plan = (rec.inputs || []).find((i) => i.role === "terraform_plan");
  return { plan_input: plan && plan.name, mode: rec.policy && rec.policy.mode };
}
const nameOf = (r) => r.resource.name || r.resource.address;
const go = (href) => { location.hash = href; };

// ---------- shell ----------
function setCrumbs(items) {
  mount(crumbsEl, items.map((c, i) => html`${i ? html`<span class="sep">/</span>` : ""}${c.href ? html`<a href="${c.href}">${c.t}</a>` : html`<span>${c.t}</span>`}`));
}
function setActions(content) { mount(actionsEl, content || ""); }
function markNav(key) { $$(".nav a").forEach((a) => a.classList.toggle("on", a.dataset.nav === key)); }
function loading() { mount(view, html`<div class="skeleton"></div><div class="skeleton"></div>`); }
function rowLinks() {
  $$("[data-href]").forEach((el) => el.addEventListener("click", (e) => { if (!e.target.closest("button")) go(el.dataset.href); }));
  $$("[data-href]").forEach((el) => el.addEventListener("keydown", (e) => { if (e.key === "Enter") go(el.dataset.href); }));
}
const secHd = (n, title, sub, right) => html`<div class="sec-hd"><span class="idx">(${n})</span><div><h2 class="h">${title}</h2>${sub ? html`<p>${sub}</p>` : ""}</div><div>${right || ""}</div></div>`;

function errorView(e, retry) {
  if (e instanceof ApiError && e.status === 401) {
    mount(view, html`
      <section class="sec reveal">
        ${secHd("—", "API key required", "This server was started with RETIRESAFE_API_KEY. Enter the key to continue; it is kept for this browser tab only.")}
        <form class="row" id="keyform"><div class="field"><label for="apikey">X-API-Key</label><input class="input" id="apikey" type="password" autocomplete="off" required></div><button class="btn primary">Continue</button></form>
      </section>`);
    $("#keyform").addEventListener("submit", (ev) => { ev.preventDefault(); setApiKey($("#apikey").value.trim()); retry(); });
    return;
  }
  mount(view, html`<section class="sec"><div class="notice err">${icon("alert")}<div><b>Request failed.</b> ${e.message || String(e)}</div></div></section>`);
}

// ---------- home ----------
async function home() {
  markNav("home");
  setCrumbs([{ t: "01 Reviews" }]);
  setActions(html`<a class="btn primary" href="#/new">${icon("plus")}New check</a>`);
  loading();
  const [list, k] = await Promise.all([api.list(), api.knowledge()]);
  const pilotIds = Object.values(pilotTags());
  const pilotLoaded = pilotIds.length && pilotIds.every((id) => list.some((a) => a.assessment_id === id));
  mount(view, html`
    <section class="hero reveal">
      <div>
        <div class="label">Pre‑flight check for cloud deletions</div>
        <h1 class="display">Retire it.<span class="sig">Don't hand it over.</span></h1>
        <p class="lede">Deleting a bucket, app or address can free its name for anyone to claim, while DNS records, code and clients still point at it. RetireSafe reads the change before it runs and stops it while a takeover path exists.</p>
        <div class="hero-actions">
          ${k.pilot_available && !pilotLoaded ? html`<button class="btn primary lg" id="loadPilot">See the recorded pilot <span class="arrow">→</span></button>` : ""}
          <a class="btn lg" href="#/new">Check your own change <span class="arrow">→</span></a>
        </div>
      </div>
      <div>
        <div class="label">A takeover needs all five. Break any one and it fails.</div>
        <div class="conds">${CS.map((c) => html`<div class="cond"><b>${c.toUpperCase()}</b><span>${COND[c].q}<small>${COND[c].long.split("· ")[1]}</small></span></div>`)}</div>
      </div>
    </section>
    ${list.length ? "" : html`
      <section class="sec reveal">
        ${secHd("02", "How it works")}
        <div class="steps">
          <div class="step"><b>01</b><span class="h">Upload the change</span><span class="dim">The Terraform plan, plus whatever might still point at the names: DNS export, code, access logs.</span></div>
          <div class="step"><b>02</b><span class="h">Read the verdict</span><span class="dim">Every name the change gives up is checked against the five conditions, with the evidence behind each.</span></div>
          <div class="step"><b>03</b><span class="h">Fix and re‑check</span><span class="dim">Apply the generated DNS change, code diff or tombstone, run again, and compare before and after.</span></div>
        </div>
      </section>`}
    <section class="sec reveal">
      ${secHd("02", "Assessments", list.length ? `${list.length} stored, newest first. Select one to open it.` : "Nothing yet. Load the recorded pilot or run your own check.",
        list.length > 1 ? html`<a class="btn" href="#/compare">${icon("compare")}Compare two</a>` : "")}
      ${list.length ? html`<div class="index">${list.map((a, i) => html`
        <div class="irow alist" data-href="#/a/${a.assessment_id}" tabindex="0" role="link">
          <span class="idx">${pad2(i)}</span>
          <div><div class="ttl">${labelOf(a.assessment_id, a)}</div><div class="sub">${shortId(a.assessment_id)} · created ${ago(a.created_at)}</div></div>
          <div><div class="label">Data as of</div><div class="small">${when(a.as_of)}</div><div class="label">${a.mode || ""} · ${a.enforcement || ""}</div></div>
          <div class="row">${VERDICT_ORDER.filter((v) => a.verdict_counts[v]).map((v) => html`<span class="badge v-${v}">${a.verdict_counts[v]} ${VERDICT[v].label}</span>`)}</div>
          <div class="gate-word ${a.gate_passed ? "pass" : "fail"}">${a.gate_passed ? (a.would_pass === false ? "Warn" : "Pass") : "Fail"}</div>
          <button class="btn ghost iconbtn del" data-del="${a.assessment_id}" title="Delete this record" aria-label="Delete">${icon("trash")}</button>
        </div>`)}</div>` : ""}
    </section>`);
  rowLinks();
  $$("[data-del]").forEach((b) => b.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (!confirm("Delete this assessment record from the server? This cannot be undone.")) return;
    await api.remove(b.dataset.del);
    toast("Assessment deleted");
    route();
  }));
  const lp = $("#loadPilot");
  if (lp) lp.addEventListener("click", loadPilot);
}

async function loadPilot() {
  const r = await api.importPilot();
  store.set("retiresafe.pilot", r.imported);
  toast("Recorded pilot loaded");
  go(`#/a/${r.imported.before_strict}`);
}

// ---------- assessment ----------
function gateSection(rec) {
  const g = rec.gate;
  const cls = g.passed && g.would_pass ? "pass" : g.passed ? "advisory" : "fail";
  const word = cls === "pass" ? "Pass" : cls === "advisory" ? "Warn" : "Fail";
  const tfv = rec.plan && rec.plan.terraform_version;
  return html`
    <section class="gate ${cls} reveal">
      <div class="word">${word}</div>
      <div>
        <div class="label">Deletion gate</div>
        <div class="sum">${g.summary}</div>
        <div class="meta">
          <span class="label">Data as of <b>${when(rec.as_of)}</b></span>
          <span class="label">Policy <b>${rec.policy.mode}</b> · ${rec.policy.enforcement}</span>
          <span class="label">Rules <b>${rec.tool.rules_version}</b></span>
          ${tfv ? html`<span class="label">Terraform <b>${tfv}</b></span>` : ""}
          ${g.waivers_applied ? html`<span class="label"><b>${g.waivers_applied}</b> waiver(s)</span>` : ""}
        </div>
      </div>
      <div class="ledger">${VERDICT_ORDER.map((v) => html`
        <div class="${g.verdict_counts[v] ? "" : "zero"}"><b class="${g.verdict_counts[v] ? `v-${v === "tombstone" ? "neutral" : v}` : ""}">${g.verdict_counts[v] || 0}</b><span class="label">${VERDICT[v].label}</span></div>`)}</div>
    </section>`;
}

/** Plain-language next steps, built only from the record's verdicts and path counts. */
function nextSteps(rec) {
  const by = (v) => rec.resources.filter((r) => r.verdict === v);
  const list = (rs) => rs.map((r) => nameOf(r)).join(", ");
  const hij = (rs) => rs.reduce((s, r) => s + r.paths.filter((p) => p.status === "hijackable").length, 0);
  const items = [];
  const blocks = by("block"), review = by("review"), tomb = by("tombstone"), rel = by("release"), nn = by("not_name_bearing");
  if (blocks.length) items.push(html`<li><span><b>Don't delete ${list(blocks)} yet.</b> ${hij(blocks)} live takeover path(s) still lead to ${blocks.length > 1 ? "these names" : "this name"}. Open ${blocks.length > 1 ? "each one" : "it"} below for the exact DNS change and code diff that remove them.</span></li>`);
  if (review.length) items.push(html`<li><span><b>A person must decide on ${list(review)}.</b> The evidence is incomplete; the resource page lists what could not be verified.</span></li>`);
  if (tomb.length) items.push(html`<li><span><b>Keep ${list(tomb)} as a tombstone.</b> Empty ${tomb.length > 1 ? "them" : "it"} but keep owning the name; the Terraform to do that is generated for you.</span></li>`);
  rel.forEach((r) => items.push(html`<li><span><b>${nameOf(r)} can be deleted.</b> <span class="dim">${r.reasons[0] || ""}</span></span></li>`));
  if (nn.length) items.push(html`<li><span class="dim">${nn.length} other deleted resource(s) give up no claimable name and are outside the takeover check.</span></li>`);
  if (!rec.gate.passed) items.push(html`<li><span><b>Re‑run this check after applying the fixes</b>, then use <a href="#/compare"><u>Before / after</u></a> to confirm the gate passes.</span></li>`);
  else items.push(html`<li><span><b>This change can proceed.</b> Keep the evidence record with the change for audit.</span></li>`);
  return html`<section class="next reveal"><span class="idx">(01) What to do</span><ol>${items}</ol></section>`;
}

function assessmentActions() {
  return html`
    <button class="btn" id="dlJson">${icon("download")}Evidence JSON</button>
    <button class="btn" id="dlMd">${icon("download")}Report</button>
    <button class="btn ghost iconbtn" id="print" title="Print" aria-label="Print">${icon("print")}</button>`;
}
function wireAssessmentActions(rec) {
  $("#dlJson").addEventListener("click", () => download(`retiresafe-${shortId(rec.assessment_id)}.json`, JSON.stringify(rec, null, 2)));
  $("#dlMd").addEventListener("click", async () => download(`retiresafe-${shortId(rec.assessment_id)}.md`, await api.report(rec.assessment_id), "text/markdown"));
  $("#print").addEventListener("click", () => window.print());
}

function pathBar(r) {
  if (!r.paths.length) return "";
  const cls = { hijackable: "h", unknown: "u", safe: "s", waived: "w" };
  return html`<div class="pathbar" title="one bar per reference path: red hijackable, amber unverified, green broken">${r.paths.map((p) => html`<i class="${cls[p.status] || ""}"></i>`)}</div>`;
}
function pathTally(r) {
  const t = {};
  r.paths.forEach((p) => { t[p.status] = (t[p.status] || 0) + 1; });
  return t;
}

async function assessment(id, tab = "resources") {
  markNav("home");
  loading();
  const rec = await api.get(id);
  const label = labelOf(id, summaryOf(rec));
  setCrumbs([{ t: "01 Reviews", href: "#/" }, { t: label }]);
  setActions(assessmentActions());
  wireAssessmentActions(rec);
  const tabs = html`<nav class="tabs">
    <a href="#/a/${id}" class="${tab === "resources" ? "on" : ""}">Resources</a>
    <a href="#/a/${id}/evidence" class="${tab === "evidence" ? "on" : ""}">Evidence &amp; provenance</a>
    <a href="#/a/${id}/report" class="${tab === "report" ? "on" : ""}">Report</a></nav>`;
  let body;
  if (tab === "evidence") body = evidenceTab(rec);
  else if (tab === "report") body = html`<section class="sec">${secHd("02", "Markdown report", "The same report the CLI writes with --markdown.")}<pre class="code" id="md">Loading…</pre></section>`;
  else body = resourcesTab(rec);
  mount(view, html`${gateSection(rec)}${tab === "resources" ? nextSteps(rec) : ""}${tabs}${body}`);
  rowLinks();
  if (tab === "report") $("#md").textContent = await api.report(id);
}

function resourcesTab(rec) {
  const rs = [...rec.resources].sort((a, b) => VERDICT_ORDER.indexOf(a.verdict) - VERDICT_ORDER.indexOf(b.verdict));
  const nc = rec.not_checked || [];
  return html`
    <section class="sec reveal">
      ${secHd("02", "Resources this change deletes", "One row per resource. The bar shows its reference paths: red can be hijacked, amber is unverified, green is broken by at least one condition.")}
      <div class="index">${rs.map((r, i) => {
        const t = pathTally(r);
        return html`
          <div class="irow rlist ${r.verdict === "not_name_bearing" ? "muted-row" : ""}" data-href="#/a/${rec.assessment_id}/r/${encodeURIComponent(r.resource.address)}" tabindex="0" role="link">
            <span class="idx">${pad2(i)}</span>
            <div><div class="ttl">${nameOf(r)}</div><div class="sub">${r.resource.address}</div>${pathBar(r)}</div>
            <div class="small dim">${r.reasons[0] || ""}
              <div class="row">${t.hijackable ? html`<span class="chip"><b>${t.hijackable}</b> hijackable</span>` : ""}${t.unknown ? html`<span class="chip"><b>${t.unknown}</b> unverified</span>` : ""}${r.traffic.length ? html`<span class="chip"><b>${compact(r.traffic.reduce((s, x) => s + x.requests, 0))}</b> requests</span>` : ""}</div></div>
            <div>${verdictBadge(r.verdict)}</div>
            <span class="go">→</span>
          </div>`;
      })}</div>
      ${nc.length ? html`<div class="notice">${icon("info")}<div><b>Not checked:</b> ${nc.join("; ")}.</div></div>` : ""}
    </section>`;
}

function evidenceTab(rec) {
  const red = rec.tool.redaction || {};
  const sr = red.secret_rules || {};
  const logs = Object.entries(rec.parse_stats || {});
  const cited = Object.entries(rec.sources || {});
  return html`
    <section class="sec reveal">
      ${secHd("02", "Inputs", "Every input is fingerprinted when read, so the decision can be tied to exactly what was examined.")}
      <table class="t"><thead><tr><th>Role</th><th>Input</th><th>Fingerprint</th></tr></thead><tbody>
      ${(rec.inputs || []).map((i) => html`<tr><td class="small nowrap">${i.role}</td>
        <td><b>${i.label || i.name}</b><div class="tiny muted">${i.bytes !== undefined ? bytes(i.bytes) : ""}${i.files !== undefined ? `${i.files} files` : ""}</div></td>
        <td class="hash">${i.sha256 ? html`sha256 ${i.sha256}` : i.sha256_tree ? html`tree sha256 ${i.sha256_tree}` : "—"}</td></tr>`)}
      </tbody></table>
    </section>
    <section class="sec reveal">
      ${secHd("03", "Tool and policy")}
      <div class="grid g2">
        <dl class="kv">
          <dt>Tool</dt><dd>${rec.tool.name} ${rec.tool.version} · Python ${rec.tool.python}</dd>
          <dt>Rule set</dt><dd>${rec.tool.rules_version}</dd>
          <dt>Fingerprints</dt><dd class="hash">can-i-take-over-xyz @ ${rec.tool.fingerprint_catalogue_commit}</dd>
          <dt>Redaction</dt><dd>${red.terraform_sensitivity_mask ? "Terraform sensitivity masks" : ""}${red.attribute_minimisation ? " · attribute minimisation" : ""}${sr.loaded ? ` · ${sr.loaded} gitleaks rules` : ""}${sr.commit ? html` <span class="hash">@ ${sr.commit.slice(0, 12)}</span>` : ""}</dd>
        </dl>
        <dl class="kv">
          <dt>Mode</dt><dd>${rec.policy.mode} · ${rec.policy.enforcement}</dd>
          <dt>α · β</dt><dd>${rec.policy.alpha} miss rate · ${rec.policy.beta} rate bound</dd>
          <dt>Log window</dt><dd>at least ${rec.policy.min_window_days} d, ending within ${rec.policy.max_staleness_days} d</dd>
          <dt>Org accounts</dt><dd>${(rec.policy.org_account_ids || []).join(", ") || "—"}</dd>
          <dt>Internal</dt><dd>${[...(rec.policy.internal_domains || []), ...(rec.policy.internal_cidrs || [])].join(", ") || "—"}</dd>
          <dt>Waiver limit</dt><dd>${rec.policy.max_waiver_days} d</dd>
        </dl>
      </div>
    </section>
    ${logs.length ? html`<section class="sec reveal">
      ${secHd("04", "Access logs", "Lines per day for each file. Shaded days had no logging at all: gaps, not silence.")}
      <table class="t"><thead><tr><th>Log</th><th class="num">Lines</th><th class="num">Parsed</th><th class="num">Unparseable</th><th>Coverage</th></tr></thead><tbody>
      ${logs.map(([n, s]) => html`<tr><td class="mono small">${n}</td><td class="num">${num(s.lines)}</td><td class="num">${num(s.parsed)}</td>
        <td class="num">${num(s.failed)} <span class="tiny muted">(${num((100 * s.failed) / Math.max(1, s.lines), 2)}%)</span></td>
        <td>${coverageSpark(s.first_day, s.daily_lines)}${s.first_day ? html`<div class="tiny muted">from ${s.first_day} · ${(s.daily_lines || []).filter((x) => !x).length} day(s) without logging</div>` : ""}</td></tr>`)}
      </tbody></table></section>` : ""}
    ${Object.keys(rec.scan_stats || {}).length ? html`<section class="sec reveal">
      ${secHd("05", "Repository scan")}
      <table class="t"><thead><tr><th>Repository</th><th class="num">Files scanned</th><th class="num">Skipped binary</th><th class="num">Skipped large</th><th class="num">Common‑word matches dropped</th></tr></thead><tbody>
      ${Object.entries(rec.scan_stats).map(([n, s]) => html`<tr><td class="mono small">${n}</td><td class="num">${num(s.files_scanned)}</td><td class="num">${num(s.files_skipped_binary)}</td><td class="num">${num(s.files_skipped_large)}</td><td class="num">${num(s.literal_matches_discarded)}</td></tr>`)}
      </tbody></table></section>` : ""}
    ${(rec.waivers_rejected || []).length ? html`<section class="sec"><div class="notice warn">${icon("alert")}<div><b>Waivers rejected:</b> ${rec.waivers_rejected.map((w) => `${w.resource || w.id || "?"}: ${w.reason || w.error || ""}`).join("; ")}</div></div></section>` : ""}
    <section class="sec reveal">
      ${secHd("06", "Sources cited", "Every rule that decided a condition, with the primary text it rests on.")}
      <div>${cited.map(([k, s], i) => sourceItem(k, s, i))}</div>
    </section>`;
}

function sourceItem(k, s, i) {
  return html`<div class="src">
    <span class="idx">${pad2(i)}</span>
    <div><div class="ttl">${s.title}</div>
      ${s.quote ? html`<blockquote>“${s.quote}”</blockquote>` : ""}
      <div class="label">${s.verified_via ? html`Verified via ${s.verified_via}` : ""} · src:${k}${s.url ? html` · <a href="${s.url}" target="_blank" rel="noopener noreferrer"><u>${s.url}</u></a>` : ""}</div></div>
  </div>`;
}

// ---------- resource ----------
function matrixRow(r, p, i) {
  const ref = r.references.find((x) => x.id === p.reference_id) || { kind: "?", location: p.reference_id, text: "" };
  const statusText = { hijackable: "Hijackable", unknown: "Unverified", safe: "Broken", waived: "Waived" }[p.status] || p.status;
  const integ = { sri: "Subresource Integrity", expected_bucket_owner: "ExpectedBucketOwner" }[ref.integrity_control] || ref.integrity_control;
  return html`
    <div class="mrow st-${p.status}" data-path="${i}">
      <div class="mref">
        <div class="row"><span class="chip">${ref.kind}</span>${ref.method ? html`<span class="chip">${ref.method}</span>` : ""}${ref.context && ref.context !== "code" ? html`<span class="chip">${ref.context}</span>` : ""}${integ ? html`<span class="chip s-safe">${integ}</span>` : ""}${ref.removed_in_change ? html`<span class="chip s-safe">removed in this change</span>` : ""}</div>
        <div class="loc">${ref.location}</div>
        <div class="txt" title="${ref.text}">${ref.text}</div>
      </div>
      ${CS.map((c) => {
        const v = p.conditions[c] ? p.conditions[c].value : "unknown";
        return html`<div class="mcell ${v === "false" ? "gap" : ""}"><button class="cell ${v}" data-c="${c}" data-p="${i}" aria-label="${COND[c].long}: ${triLabel(v)}. Show evidence." title="${COND[c].short}: ${triLabel(v)}"><span>${v === "true" ? "✓" : v === "false" ? c.toUpperCase() : "?"}</span></button></div>`;
      })}
      <div class="mstatus"><b class="s-${p.status}">${statusText}</b>
        <span class="tiny muted">${p.broken_by.length ? `chain breaks at ${p.broken_by.map((c) => c.toUpperCase()).join(", ")}` : p.status === "hijackable" ? "all five hold" : p.status === "unknown" ? "a condition is unverified" : ""}</span></div>
    </div>`;
}

function evidenceItems(rec, ids) {
  return html`<div class="ev">${ids.map((id) => {
    if (id.startsWith("src:")) {
      const s = (rec.sources || {})[id.slice(4)];
      return s ? html`<div class="ev-item"><b>${s.title}</b>${s.quote ? html`<blockquote>“${s.quote}”</blockquote>` : ""}<span class="id">${s.verified_via || ""} · ${id}</span></div>`
        : html`<div class="ev-item"><span class="id">${id}</span></div>`;
    }
    const e = (rec.evidence || []).find((x) => x.id === id);
    return e ? html`<div class="ev-item"><b>${e.detail}</b><span class="id">${e.source} · ${e.location}</span></div>`
      : html`<div class="ev-item"><span class="id">${id}</span></div>`;
  })}</div>`;
}

function inspector(rec, r, i, c) {
  const p = r.paths[i];
  const cond = p.conditions[c];
  const v = cond ? cond.value : "unknown";
  return html`
    <div><div class="tri ${v === "true" ? "s-hijackable" : v === "false" ? "s-safe" : "s-unknown"}">${triLabel(v)}</div><div class="label">${COND[c].long}</div></div>
    <div class="stack"><div class="dim">${COND[c].q}</div><div class="h">${cond ? cond.reason : "not evaluated"}</div>
      ${cond && cond.evidence_ids.length ? evidenceItems(rec, cond.evidence_ids) : ""}</div>`;
}

function trafficBlock(rec, t) {
  const file = t.source.split("[")[0];
  const cov = (rec.parse_stats || {})[file];
  const chart = trafficChart(t, cov && cov.daily_lines, rec.as_of);
  const p = rec.policy;
  const q = t.quarantine_days_conservative;
  let verdict;
  if (!t.fresh) verdict = html`<div class="verdict-line warn">The log ends more than ${p.max_staleness_days} d before the assessment time, so it cannot show whether anyone still uses the name (C4 unknown).</div>`;
  else if (!t.window_sufficient) verdict = html`<div class="verdict-line warn">The log covers ${days(t.window_days)}, less than the ${p.min_window_days} d minimum, so silence cannot be trusted (C4 unknown).</div>`;
  else if (!t.requests) verdict = html`<div class="verdict-line warn">No requests in the window. With zero events no quarantine can be computed, so silence alone is not treated as proof.</div>`;
  else if (t.silence_days > q) verdict = html`<div class="verdict-line ok"><span>Silent for <b>${days(t.silence_days)}</b>, longer than the conservative quarantine <b>${days(q)}</b>. A consumer at even the lower‑bound rate would have shown up with ≥ ${num(100 * (1 - p.alpha), 0)}% probability, so the logs show <b>no one still using it</b>.</span></div>`;
  else verdict = html`<div class="verdict-line bad"><span>Silent for only <b>${days(t.silence_days)}</b>, inside the conservative quarantine <b>${days(q)}</b>: <b>consumers are still active.</b></span></div>`;
  return html`
    <div class="stack">
      <div class="spread"><span class="label"><b>${t.source}</b></span><span class="label">${when(t.window_start, false)} → ${when(t.window_end, false)} · ${days(t.window_days)}</span></div>
      ${chart || html`<div class="notice">${icon("info")}<div>This record predates daily counts; statistics only.</div></div>`}
      <div class="legend"><span><i class="sw bar"></i>Requests / day</span><span><i class="sw q"></i>Quarantine D*</span><span><i class="sw si"></i>Observed silence</span><span><i class="sw gp"></i>No logging</span></div>
      <div class="stats">
        <div class="stat"><span class="label">Requests</span><b>${compact(t.requests)}</b></div>
        <div class="stat"><span class="label">Clients · external</span><b>${compact(t.distinct_clients)} · ${t.external_share === null ? "—" : num(100 * t.external_share, 0) + "%"}</b></div>
        <div class="stat"><span class="label">Last request</span><b>${when(t.last_seen, false)}</b></div>
        <div class="stat"><span class="label">Silence / D*</span><b>${days(t.silence_days)} / ${days(q)}</b></div>
      </div>
      ${t.requests ? html`<div class="formula">
        λ̂ = n / T = ${num(t.requests)} / ${num(t.window_days, 2)} d = <b>${rate(t.rate_mle_per_day)}</b><br>
        λ<sub>lo</sub> = Gamma<sup>−1</sup>(β = ${p.beta}; n + ½, T) = <b>${rate(t.rate_lower_per_day)}</b> <span class="muted">Jeffreys lower bound</span><br>
        D* = −ln α / λ<sub>lo</sub> = ${num(-Math.log(p.alpha), 3)} / ${num(t.rate_lower_per_day, t.rate_lower_per_day < 10 ? 3 : 0)} = <b>${days(q)}</b> <span class="muted">α = ${p.alpha}</span>
      </div>` : ""}
      ${verdict}
    </div>`;
}

function codeBlock(text, kind) {
  const lines = String(text).split("\n").map((l) => {
    let c = "";
    if (kind === "code_diff") {
      if (l.startsWith("+++") || l.startsWith("---")) c = "cmt";
      else if (l.startsWith("+")) c = "add";
      else if (l.startsWith("-")) c = "del";
      else if (l.startsWith("@@")) c = "hunk";
    } else if (/^\s*(#|\/\/)/.test(l)) c = "cmt";
    return c ? `<span class="${c}">${esc(l)}</span>` : esc(l);
  });
  return html`<pre class="code">${raw(lines.join("\n"))}</pre>`;
}
const PATCH_FILE = { route53_change_batch: "change-batch.json", code_diff: "references.patch", terraform_hcl: "tombstone.tf", advice: "advice.txt" };
const PATCH_KIND = { route53_change_batch: "Route 53 change batch", code_diff: "Code diff", terraform_hcl: "Terraform", advice: "Guidance" };

async function resource(id, addr) {
  markNav("home");
  loading();
  const rec = await api.get(id);
  const r = rec.resources.find((x) => x.resource.address === addr);
  if (!r) throw new ApiError(404, `resource ${addr} is not in this assessment`);
  setCrumbs([{ t: "01 Reviews", href: "#/" }, { t: labelOf(id, summaryOf(rec)), href: `#/a/${id}` }, { t: addr }]);
  setActions(assessmentActions());
  wireAssessmentActions(rec);
  const res = r.resource;
  const attrs = res.attributes || {};
  const t = pathTally(r);
  const rc = r.reclaimable;
  let n = 0;
  const sec = () => pad2(n++);
  mount(view, html`
    <section class="rhead reveal">
      <div>
        <div class="label">${res.type}${res.region ? ` · ${res.region}` : ""} · action ${res.action} · <span class="mono">${res.address}</span></div>
        <h1 class="display md">${nameOf(r)}</h1>
        <div class="why">${r.reasons.join(" ")}</div>
        <div class="row">
          ${r.paths.length ? html`<span class="chip"><b>${r.paths.length}</b> reference paths</span>` : ""}
          ${t.hijackable ? html`<span class="chip s-hijackable"><b>${t.hijackable}</b> hijackable</span>` : ""}
          ${t.unknown ? html`<span class="chip s-unknown"><b>${t.unknown}</b> unverified</span>` : ""}
          ${t.safe ? html`<span class="chip s-safe"><b>${t.safe}</b> broken</span>` : ""}
          <span class="chip">risk <b>${num(r.risk_interval[0], 2)}–${num(r.risk_interval[1], 2)}</b></span>
        </div>
      </div>
      <div class="stamp v-${r.verdict}">${VERDICT[r.verdict] ? VERDICT[r.verdict].label : r.verdict}</div>
    </section>

    <section class="sec reveal">
      ${secHd(sec(), "Takeover paths", "Each place that still points at this name, tested against the five conditions. A takeover needs every circle filled; a struck‑through circle breaks the chain. Select any circle to see why.")}
      ${r.paths.length ? html`
        <div class="howto"><span class="key"><span class="cell true" aria-hidden="true"><span>✓</span></span>holds</span><span class="key"><span class="cell false" aria-hidden="true"><span>C</span></span>false: breaks the chain</span><span class="key"><span class="cell unknown" aria-hidden="true"><span>?</span></span>not verified</span></div>
        <div class="matrix">
          <div class="mrow mhead"><div>Reference</div>${CS.map((c) => html`<div><b>${c.toUpperCase()}</b>${COND[c].short}</div>`)}<div>Result</div></div>
          ${r.paths.map((p, i) => matrixRow(r, p, i))}
        </div>
        <div class="inspector hidden" id="insp"></div>`
        : html`<div class="notice">${icon("info")}<div>Nothing in the supplied DNS inventory, plan, repositories or logs points at this name. ${rc.value === "false" ? "No one else can claim it either, so release is safe regardless." : ""}</div></div>`}
    </section>

    <div class="split">
      <div>
        ${r.traffic.length ? html`<section class="sec reveal">${secHd(sec(), "Is anyone still using it?", "Condition C4, from real access logs: requests per day, then the silence since the last one against the quarantine the statistics require.")}
          <div class="stack">${r.traffic.map((x) => trafficBlock(rec, x))}</div></section>` : ""}
        ${r.patches.length ? html`<section class="sec reveal">${secHd(sec(), "Fixes", "Generated from the evidence. Apply them, then run the check again.")}
          ${r.patches.map((p, i) => html`
            <div class="patch">
              <div class="pt"><span class="idx">${pad2(i)}</span><div><div class="label">${PATCH_KIND[p.kind] || p.kind}${p.applies_to && p.applies_to.length ? ` · ${p.applies_to.join(", ")}` : ""}</div><b>${p.title}</b></div>
                <div class="row"><button class="btn ghost iconbtn" data-copy="${i}" title="Copy" aria-label="Copy">${icon("copy")}</button><button class="btn ghost iconbtn" data-dl="${i}" title="Download" aria-label="Download">${icon("download")}</button></div></div>
              ${codeBlock(p.content, p.kind)}
            </div>`)}</section>` : ""}
      </div>
      <aside class="sec reveal">
        <div class="fact"><div class="h">Can someone else claim it? <span class="badge ${rc.value === "true" ? "v-block" : rc.value === "false" ? "v-release" : "v-review"}">C2 ${triLabel(rc.value)}</span></div>
          <div>${rc.reason}</div>${evidenceItems(rec, rc.evidence_ids)}</div>
        ${r.tombstone ? html`<div class="fact"><div class="h">Tombstone plan <span class="badge v-tombstone">keep the name</span></div>
          <dl class="kv"><dt>Review after</dt><dd>${r.tombstone.review_after} <span class="muted">(${r.tombstone.review_basis_days} d after the data)</span></dd>
            <dt>Holding cost</dt><dd>${r.tombstone.holding_cost}</dd><dt>Exit</dt><dd>${r.tombstone.release_path}</dd></dl>
          ${r.tombstone.sources && r.tombstone.sources.length ? evidenceItems(rec, r.tombstone.sources) : ""}</div>` : ""}
        ${(r.waivers_applied || []).length ? html`<div class="fact"><div class="h">Waivers applied</div>
          ${r.waivers_applied.map((w) => html`<dl class="kv"><dt>Type</dt><dd>${w.type || w.kind || ""}</dd><dt>Approver</dt><dd>${w.approver || ""}</dd><dt>Expires</dt><dd>${w.expires || ""}</dd><dt>Reason</dt><dd>${w.reason || ""}</dd></dl>`)}</div>` : ""}
        <div class="fact"><div class="h">Resource</div>
          <dl class="kv mono-v">${Object.entries(attrs).filter(([k, v]) => !k.startsWith("_") && v !== null && v !== "").map(([k, v]) => html`<dt>${k}</dt><dd>${typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>`)}</dl>
          ${attrs._omitted_attributes ? html`<div class="tiny muted">${attrs._omitted_attributes} further attributes were not stored (attribute minimisation).</div>` : ""}
          ${res.endpoints && res.endpoints.length ? html`<details class="fold"><summary>${res.endpoints.length} names this resource answers to</summary>
            <div class="stack fold-body">${res.endpoints.map((e) => html`<div class="mono tiny break"><span class="muted">${e.kind}</span> ${e.name}</div>`)}</div></details>` : ""}</div>
        ${r.not_checked.length ? html`<div class="fact"><div class="h">Not checked</div>${r.not_checked.map((x) => html`<div class="small dim">— ${x}</div>`)}</div>` : ""}
      </aside>
    </div>`);

  const insp = $("#insp");
  $$(".mrow:not(.mhead) .cell").forEach((cell) => cell.addEventListener("click", () => {
    const already = cell.classList.contains("sel");
    $$(".cell.sel").forEach((x) => x.classList.remove("sel"));
    if (already) { insp.classList.add("hidden"); return; }
    cell.classList.add("sel");
    mount(insp, inspector(rec, r, Number(cell.dataset.p), cell.dataset.c));
    insp.classList.remove("hidden");
    cell.closest(".mrow").after(insp);
  }));
  $$("[data-copy]").forEach((b) => b.addEventListener("click", () => copy(r.patches[b.dataset.copy].content)));
  $$("[data-dl]").forEach((b) => b.addEventListener("click", () => {
    const p = r.patches[b.dataset.dl];
    download(PATCH_FILE[p.kind] || "patch.txt", p.content, "text/plain");
  }));
}

// ---------- compare ----------
async function compare(a, b) {
  markNav("compare");
  setCrumbs([{ t: "03 Before / after" }]);
  setActions("");
  loading();
  const list = await api.list(200);
  const tags = pilotTags();
  if (list.length < 2) {
    mount(view, html`<section class="empty reveal"><h1 class="display md">Nothing to compare yet.</h1><p class="lede">Run the same change twice, before and after applying RetireSafe's fixes, and the difference shows up here.</p><a class="btn primary" href="#/">Back to reviews</a></section>`);
    return;
  }
  if (!a || !b) {
    if (tags.before_strict && tags.after_strict && list.some((x) => x.assessment_id === tags.after_strict)) [a, b] = [tags.before_strict, tags.after_strict];
    else [a, b] = [list[1].assessment_id, list[0].assessment_id];
  }
  const picker = (sel, idn) => html`<select class="input" id="${idn}">${list.map((x) => html`<option value="${x.assessment_id}" ${x.assessment_id === sel ? raw("selected") : ""}>${labelOf(x.assessment_id, x)} (${shortId(x.assessment_id)})</option>`)}</select>`;
  const [A, B] = await Promise.all([api.get(a), api.get(b)]);
  const addrs = [...new Set([...A.resources, ...B.resources].map((r) => r.resource.address))];
  const byA = Object.fromEntries(A.resources.map((r) => [r.resource.address, r]));
  const byB = Object.fromEntries(B.resources.map((r) => [r.resource.address, r]));
  const hij = (rec) => rec.resources.reduce((s, r) => s + r.paths.filter((p) => p.status === "hijackable").length, 0);
  const side = (rec, id, lab, sel) => html`<div class="side ${rec.gate.passed ? "pass" : "fail"}">
      <span class="label">${lab}</span>
      <div class="word">${rec.gate.passed ? "Pass" : "Fail"}</div>
      <div class="field">${sel}</div>
      <div class="label"><b>${hij(rec)}</b> hijackable path(s) · <b>${rec.resources.length}</b> resources deleted · ${rec.policy.mode} · <a href="#/a/${id}"><u>open</u></a></div></div>`;
  const fp = (i) => i && (i.sha256 || i.sha256_tree);
  const roles = [...new Set([...(A.inputs || []), ...(B.inputs || [])].map((i) => i.role))];
  mount(view, html`
    <section class="versus reveal">${side(A, a, "Before", picker(a, "pa"))}<div class="mid">→</div>${side(B, b, "After", picker(b, "pb"))}</section>
    <section class="sec reveal">
      ${secHd("01", "What happened to each resource")}
      <table class="t"><thead><tr><th>Resource</th><th>Before</th><th>After</th><th>Change</th></tr></thead><tbody>
      ${addrs.map((ad) => {
        const x = byA[ad], y = byB[ad];
        const note = !y ? "No longer deleted by the plan: the name is kept"
          : !x ? "Newly deleted by the plan"
          : x.verdict === y.verdict ? "Unchanged" : `${VERDICT[x.verdict].label} → ${VERDICT[y.verdict].label}`;
        const hx = x ? x.paths.filter((p) => p.status === "hijackable").length : 0;
        const hy = y ? y.paths.filter((p) => p.status === "hijackable").length : 0;
        return html`<tr><td><b>${(x || y).resource.name || ad}</b><div class="hash">${ad}</div></td>
          <td>${x ? verdictBadge(x.verdict) : html`<span class="muted small">not deleted</span>`}${x && hx ? html`<div class="tiny s-hijackable">${hx} hijackable</div>` : ""}</td>
          <td>${y ? verdictBadge(y.verdict) : html`<span class="badge v-tombstone">kept</span>`}${y && hy ? html`<div class="tiny s-hijackable">${hy} hijackable</div>` : ""}</td>
          <td class="dim">${note}</td></tr>`;
      })}</tbody></table>
    </section>
    <section class="sec reveal">
      ${secHd("02", "What was different between the runs", "Inputs are compared by fingerprint.")}
      <table class="t"><thead><tr><th>Role</th><th>Before</th><th>After</th><th></th></tr></thead><tbody>
      ${roles.map((role) => {
        const ia = (A.inputs || []).filter((i) => i.role === role), ib = (B.inputs || []).filter((i) => i.role === role);
        const same = ia.length === ib.length && ia.every((i) => ib.some((j) => fp(j) === fp(i)));
        const cell = (xs) => [...new Map(xs.map((i) => [fp(i), i])).values()].map((i) => html`<div>${i.label || i.name} <span class="hash">${(fp(i) || "").slice(0, 12)}</span></div>`);
        return html`<tr><td class="small">${role}</td><td>${cell(ia)}</td><td>${cell(ib)}</td>
          <td>${same ? html`<span class="badge v-neutral">identical</span>` : html`<span class="badge v-review">changed</span>`}</td></tr>`;
      })}</tbody></table>
    </section>`);
  const nav = () => go(`#/compare/${$("#pa").value}/${$("#pb").value}`);
  $("#pa").addEventListener("change", nav);
  $("#pb").addEventListener("change", nav);
}

// ---------- new assessment ----------
function dropzone(name, title, hint, multiple, accept, required) {
  return html`<div class="drop"><input type="file" name="${name}" ${multiple ? raw("multiple") : ""} ${accept ? raw(`accept="${esc(accept)}"`) : ""} aria-label="${title}">
    <span class="t">${title}${required ? html`<sup>required</sup>` : ""}</span><span class="hint">${hint}</span><div class="files"></div></div>`;
}

async function newAssessment() {
  markNav("new");
  setCrumbs([{ t: "02 New check" }]);
  setActions("");
  mount(view, html`
    <section class="rhead reveal"><div><div class="label">New check</div><h1 class="display md">What are you about to delete?</h1>
      <p class="why">Only the Terraform plan is required. Every extra input lets RetireSafe prove more instead of marking it unverified.</p></div></section>
    <form id="nf" autocomplete="off">
      <div class="form-sec reveal"><span class="idx">(01) The change</span>
        <div class="grid g2">
          ${dropzone("plan", "Terraform plan", "terraform show -json plan.out > plan.json", false, ".json", true)}
          ${dropzone("dns", "DNS records", "Route 53 export (list-resource-record-sets JSON) or BIND zone files", true, "")}
        </div></div>
      <div class="form-sec reveal"><span class="idx">(02) Who still uses it</span>
        <div class="stack">
          <div class="grid g2">
            ${dropzone("repo", "Code", "a .zip or .tar.gz of repositories that may reference the names", false, ".zip,.tar,.gz,.tgz")}
            ${dropzone("logs", "Access logs", "S3 server access logs, CloudFront standard logs, or Common Log Format", true, "")}
          </div>
          <div class="grid g2">
            <div class="field"><label for="repoLabel">Repository label</label><input class="input" id="repoLabel" placeholder="app"><span class="hint">shown in file:line locations</span></div>
            <div class="field"><span class="lab">Log settings</span><div id="logrows" class="stack"><span class="hint">add log files to configure them</span></div></div>
          </div>
        </div></div>
      <div class="form-sec reveal"><span class="idx">(03) Policy</span>
        <div class="stack"><div class="grid g3">
          <div class="field"><span class="lab">Mode</span><div class="seg"><label><input type="radio" name="mode" value="strict" checked>Strict</label><label><input type="radio" name="mode" value="balanced">Balanced</label></div><span class="hint">strict never releases a name someone else could claim; balanced releases on evidence</span></div>
          <div class="field"><span class="lab">Enforcement</span><div class="seg"><label><input type="radio" name="enf" value="enforce" checked>Enforce</label><label><input type="radio" name="enf" value="advisory">Advisory</label></div><span class="hint">advisory reports but never fails the gate</span></div>
          <div class="field"><label for="alpha">α · tolerated miss probability</label><input class="input" id="alpha" type="number" step="any" min="0.0001" max="0.5" value="0.01"></div>
          <div class="field"><label for="accts">Organisation account IDs</label><input class="input" id="accts" placeholder="123456789012, 210987654321"></div>
          <div class="field"><label for="idom">Internal domains / CIDRs</label><input class="input" id="idom" placeholder="corp.example, 10.0.0.0/8"><span class="hint">these clients are not counted as external</span></div>
          <div class="field"><label for="asof">Assess as of</label><input class="input" id="asof" placeholder="now (e.g. 2026-10-01T00:00:00Z)"></div>
        </div>
        <details class="fold"><summary>Advanced: migrations and waivers</summary>
          <div class="grid g2 fold-body">
            <div class="field"><label for="mig">Migrations</label><textarea class="input" id="mig" placeholder="old-bucket=new-bucket-123456789012-us-east-1-an"></textarea><span class="hint">one old=new per line; used to write code patches</span></div>
            <div class="field"><label for="waivers">Waivers (JSON list)</label><textarea class="input" id="waivers" placeholder='[{"resource": "...", "type": "accept_reference", ...}]'></textarea></div>
          </div></details></div>
      </div>
      <div class="submitbar"><div id="nmsg" class="small dim">Files are processed on this server and deleted after the run.</div><button class="btn primary lg" id="go">Run the check <span class="arrow">→</span></button></div>
    </form>`);
  const files = { plan: [], dns: [], repo: [], logs: [] };
  $$(".drop input[type=file]").forEach((inp) => {
    const zone = inp.closest(".drop");
    inp.addEventListener("change", () => {
      files[inp.name] = [...inp.files];
      zone.classList.toggle("has", files[inp.name].length > 0);
      mount($(".files", zone), files[inp.name].map((f) => html`<div>${f.name} <span class="muted">${bytes(f.size)}</span></div>`));
      if (inp.name === "logs") renderLogRows();
    });
    ["dragenter", "dragover"].forEach((e) => zone.addEventListener(e, () => zone.classList.add("over")));
    ["dragleave", "drop"].forEach((e) => zone.addEventListener(e, () => zone.classList.remove("over")));
  });
  function renderLogRows() {
    const box = $("#logrows");
    if (!files.logs.length) { mount(box, html`<span class="hint">add log files to configure them</span>`); return; }
    mount(box, files.logs.map((f, i) => html`<div class="logrow" data-i="${i}">
      <span class="mono tiny break">${f.name}</span>
      <select class="input" data-k="format" aria-label="format"><option value="s3">S3 access</option><option value="cloudfront">CloudFront</option><option value="clf">CLF</option></select>
      <input class="input" data-k="host" placeholder="host (CLF: required)" aria-label="host">
      <input class="input" data-k="path_prefix" placeholder="path prefix" aria-label="path prefix"></div>`));
  }
  const csv = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);
  $("#nf").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const msg = $("#nmsg");
    if (!files.plan.length) { mount(msg, html`<span class="sig">Add a Terraform plan first.</span>`); $(".drop").scrollIntoView({ behavior: "smooth", block: "center" }); return; }
    const internal = csv($("#idom").value);
    const isNet = (x) => /[/:]|^\d+\.\d+/.test(x);
    const cfg = { policy: {
      mode: $("input[name=mode]:checked").value, enforcement: $("input[name=enf]:checked").value,
      alpha: Number($("#alpha").value), org_account_ids: csv($("#accts").value),
      internal_domains: internal.filter((x) => !isNet(x)), internal_cidrs: internal.filter(isNet),
    } };
    if ($("#asof").value.trim()) cfg.as_of = $("#asof").value.trim();
    if ($("#repoLabel").value.trim()) cfg.repo_label = $("#repoLabel").value.trim();
    const mig = $("#mig").value.split("\n").map((l) => l.trim()).filter(Boolean);
    if (mig.length) cfg.migrate_to = Object.fromEntries(mig.map((l) => l.split("=").map((x) => x.trim())));
    if ($("#waivers").value.trim()) {
      try { cfg.waivers = JSON.parse($("#waivers").value); } catch (e) { mount(msg, html`<span class="sig">Waivers are not valid JSON: ${e.message}</span>`); return; }
    }
    cfg.logs = $$(".logrow").map((row) => {
      const o = { filename: files.logs[Number(row.dataset.i)].name };
      $$("[data-k]", row).forEach((el) => { if (el.value.trim()) o[el.dataset.k] = el.value.trim(); });
      return o;
    });
    const fd = new FormData();
    fd.append("plan", files.plan[0]);
    files.dns.forEach((f) => fd.append("dns", f));
    files.logs.forEach((f) => fd.append("logs", f));
    if (files.repo.length) fd.append("repo", files.repo[0]);
    fd.append("config", JSON.stringify(cfg));
    const btn = $("#go");
    btn.disabled = true;
    const t0 = Date.now();
    let phase = "Uploading";
    const tick = setInterval(() => mount(msg, html`<span class="spinner"></span> ${phase} · ${Math.round((Date.now() - t0) / 1000)} s`), 400);
    try {
      const rec = await api.createAssessment(fd, (f) => { phase = f >= 1 ? "Checking (large logs take a minute)" : `Uploading ${Math.round(f * 100)}%`; });
      go(`#/a/${rec.assessment_id}`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { errorView(e, newAssessment); return; }
      mount(msg, html`<span class="sig">${e.message}</span>`);
    } finally { clearInterval(tick); btn.disabled = false; }
  });
}

// ---------- drift scan ----------
const LADDER = {
  reclaimable_candidate: ["v-block", "Reclaimable", "the target name is free for anyone to claim"],
  dangling_unregistered_domain: ["v-block", "Unregistered domain", "the CNAME target's domain is not registered"],
  stale_target_missing: ["v-review", "Stale", "points at a missing target that cannot be claimed directly"],
  provider_needs_http_check: ["v-review", "Needs HTTP check", "provider match; confirm with an HTTP request"],
  lookup_error: ["v-review", "Lookup error", "never treated as clean"],
  cname_resolves: ["v-release", "Resolves", "target exists"],
  no_cname: ["v-neutral", "No CNAME", "nothing delegated"],
};

async function scan() {
  markNav("scan");
  setCrumbs([{ t: "04 Drift scan" }]);
  setActions("");
  loading();
  const k = await api.knowledge();
  const owned = k.owned_domains || [];
  mount(view, html`
    <section class="rhead reveal"><div><div class="label">Live, read‑only</div><h1 class="display md">Is anything already dangling?</h1>
      <p class="why">Checks names you already publish: follows each CNAME and asks whether its target could be claimed today. Only DNS lookups and unauthenticated S3 requests; nothing is created.</p></div></section>
    <section class="sec reveal">
      ${owned.length ? html`<div class="notice">${icon("info")}<div>Scope is limited to the domains this server was told your organisation owns: ${owned.map((d) => html`<code class="inline-code">${d}</code> `)}. Other names are refused.</div></div>`
        : html`<div class="notice warn">${icon("alert")}<div><b>Live scans are switched off.</b> Restart the server with <code class="inline-code">RETIRESAFE_OWNED_DOMAINS=example.com,example.org</code> listing domains you own. RetireSafe never probes names outside that list.</div></div>`}
      <div class="form-sec"><span class="idx">(01) Hostnames</span>
        <div class="stack"><div class="field"><label for="hosts">One per line</label><textarea class="input" id="hosts" placeholder="cdn.example.com&#10;assets.example.com" ${owned.length ? "" : raw("disabled")}></textarea></div>
        <div class="spread"><span class="small dim" id="smsg"></span><button class="btn primary lg" id="sgo" ${owned.length ? "" : raw("disabled")}>Scan <span class="arrow">→</span></button></div></div></div>
    </section>
    <div id="sres"></div>`);
  if (!owned.length) return;
  $("#sgo").addEventListener("click", async () => {
    const hosts = $("#hosts").value.split(/\s+/).map((h) => h.trim()).filter(Boolean);
    if (!hosts.length) return;
    $("#sgo").disabled = true;
    mount($("#smsg"), html`<span class="spinner"></span> resolving ${hosts.length} name(s)…`);
    try {
      const r = await api.scan(hosts);
      mount($("#smsg"), html`${r.names} checked · <b class="${r.reclaimable ? "sig" : ""}">${r.reclaimable} reclaimable</b>`);
      mount($("#sres"), html`<section class="sec reveal">${secHd("02", "Findings", when(r.created_at))}
        ${r.refused_not_owned.length ? html`<div class="notice warn">${icon("alert")}<div>Refused (not under an owned domain): ${r.refused_not_owned.join(", ")}</div></div>` : ""}
        <table class="t"><thead><tr><th>Hostname</th><th>Result</th><th>CNAME chain</th><th>Service</th><th>Detail</th></tr></thead><tbody>
        ${r.findings.map((f) => { const l = LADDER[f.classification] || ["v-neutral", f.classification, ""]; return html`<tr>
          <td class="mono small">${f.hostname}</td><td><span class="badge ${l[0]}" title="${l[2]}">${l[1]}</span></td>
          <td class="mono tiny">${f.chain.length ? f.chain.join(" → ") : "—"}</td><td class="small">${f.service || "—"}</td><td class="small dim">${f.detail}</td></tr>`; })}
        </tbody></table></section>`);
    } catch (e) { mount($("#smsg"), html`<span class="sig">${e.message}</span>`); }
    finally { $("#sgo").disabled = false; }
  });
}

// ---------- knowledge ----------
async function knowledge() {
  markNav("knowledge");
  setCrumbs([{ t: "05 Sources" }]);
  setActions(html`<a class="btn ghost" href="/docs" target="_blank" rel="noopener">${icon("ext")}API reference</a>`);
  loading();
  const k = await api.knowledge();
  const src = Object.entries(k.sources);
  mount(view, html`
    <section class="rhead reveal"><div><div class="label">How decisions are made</div><h1 class="display md">No rule without a source.</h1>
      <p class="why">Every condition RetireSafe decides cites the primary text it rests on. The rule set and the fingerprint catalogue are pinned and recorded in every evidence record.</p></div></section>
    <section class="sec reveal"><div class="grid g3">
      <div class="stack"><span class="label">Rule set</span><span class="bignum">${k.rules_version}</span></div>
      <div class="stack"><span class="label">Fingerprint catalogue · can-i-take-over-xyz</span><span class="bignum">${k.fingerprint_catalogue_commit.slice(0, 7)}</span></div>
      <div class="stack"><span class="label">Resource types covered</span><span class="bignum">${k.name_bearing_resource_types.length}</span></div>
    </div></section>
    <section class="sec reveal">${secHd("01", "Covered resource types", "Types whose deletion can give up a name someone else could claim.")}
      <div class="typelist">${k.name_bearing_resource_types.map((t) => html`<div>${t}</div>`)}</div></section>
    <section class="sec reveal">${secHd("02", "Source register", `${src.length} primary sources.`)}
      <div>${src.map(([key, s], i) => sourceItem(key, s, i))}</div></section>`);
}

// ---------- router ----------
const routes = [
  [/^#?\/?$/, () => home()],
  [/^#\/a\/([^/]+)$/, (m) => assessment(m[1])],
  [/^#\/a\/([^/]+)\/evidence$/, (m) => assessment(m[1], "evidence")],
  [/^#\/a\/([^/]+)\/report$/, (m) => assessment(m[1], "report")],
  [/^#\/a\/([^/]+)\/r\/(.+)$/, (m) => resource(m[1], decodeURIComponent(m[2]))],
  [/^#\/compare(?:\/([^/]+)\/([^/]+))?$/, (m) => compare(m[1], m[2])],
  [/^#\/new$/, () => newAssessment()],
  [/^#\/scan$/, () => scan()],
  [/^#\/knowledge$/, () => knowledge()],
];

async function route() {
  const h = location.hash || "#/";
  const hit = routes.find(([re]) => re.test(h));
  window.scrollTo(0, 0);
  try {
    if (!hit) throw new ApiError(404, "page not found");
    await hit[1](h.match(hit[0]));
  } catch (e) {
    console.error(e);
    errorView(e, route);
  }
}

async function health() {
  try {
    const [h, k] = await Promise.all([api.health(), api.knowledge().catch(() => null)]);
    mount($("#health"), html`<span class="dot ok"></span><span>API online · v${h.version}</span>`);
    if (k) mount($("#foot-rules"), html`Rules ${k.rules_version} · fingerprints ${k.fingerprint_catalogue_commit.slice(0, 7)}`);
  } catch {
    mount($("#health"), html`<span class="dot bad"></span><span>API unreachable</span>`);
  }
}

function theme() {
  const saved = store.get("retiresafe.theme", null);
  const prefersDark = matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = saved || (prefersDark ? "dark" : "light");
  $("#theme").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    store.set("retiresafe.theme", next);
  });
}

theme();
health();
window.addEventListener("hashchange", route);
route();
