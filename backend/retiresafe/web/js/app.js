// RetireSafe console: a client for the evidence records the API produces. It shows only what the record
// contains; nothing displayed here is computed from anything else except the arithmetic shown on screen.
import { api, ApiError, setApiKey } from "./api.js";
import { trafficChart, coverageSpark } from "./charts.js";
import {
  $, $$, html, raw, esc, mount, num, compact, days, rate, when, ago, shortId, bytes, download, copy, toast,
  VERDICT, VERDICT_ORDER, COND, verdictBadge, triLabel, icon,
} from "./util.js";

const view = $("#view");
const crumbsEl = $("#crumbs");
const actionsEl = $("#actions");

// ---------- small per-browser conveniences (never relied on) ----------
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

// ---------- shell ----------
function setCrumbs(items) {
  mount(crumbsEl, items.map((c, i) => html`${i ? html`<span class="sep">/</span>` : ""}${c.href ? html`<a href="${c.href}">${c.t}</a>` : html`<span>${c.t}</span>`}`));
}
function setActions(content) { mount(actionsEl, content || ""); }
function markNav(key) { $$(".nav a").forEach((a) => a.classList.toggle("on", a.dataset.nav === key)); }

function errorView(e, retry) {
  if (e instanceof ApiError && e.status === 401) {
    mount(view, html`
      <div class="panel"><div class="bd stack">
        <div class="row">${icon("key")}<h2>API key required</h2></div>
        <p class="dim">This server was started with <code class="inline-code">RETIRESAFE_API_KEY</code>. Enter the key to continue. It is kept for this browser tab only.</p>
        <form class="row" id="keyform"><input class="input" id="apikey" type="password" autocomplete="off" placeholder="X-API-Key" required><button class="btn primary">Continue</button></form>
      </div></div>`);
    $("#keyform").addEventListener("submit", (ev) => { ev.preventDefault(); setApiKey($("#apikey").value.trim()); retry(); });
    return;
  }
  mount(view, html`<div class="notice err">${icon("alert")}<div><b>Request failed.</b> ${e.message || String(e)}</div></div>`);
}

function loading() { mount(view, html`<div class="skeleton"></div><div class="skeleton"></div>`); }

// ---------- home ----------
const CHAIN_INTRO = ["c1", "c2", "c3", "c4", "c5"];

async function home() {
  markNav("home");
  setCrumbs([{ t: "Change reviews" }]);
  setActions(html`<a class="btn primary" href="#/new">${icon("plus")}New assessment</a>`);
  loading();
  const [list, k] = await Promise.all([api.list(), api.knowledge()]);
  const pilotIds = Object.values(pilotTags());
  const pilotLoaded = pilotIds.length && pilotIds.every((id) => list.some((a) => a.assessment_id === id));
  mount(view, html`
    <section class="hero">
      <div>
        <div class="eyebrow">Pre-flight check for cloud deletions</div>
        <h1>Retire cloud resources without handing their names to someone else.</h1>
        <p>Deleting a bucket, app or address can free its name for anyone to claim, while DNS records, code and clients still point at it. RetireSafe reads the change before it is applied and blocks it while a takeover path exists.</p>
        <div class="row hero-actions">
          ${k.pilot_available && !pilotLoaded ? html`<button class="btn primary" id="loadPilot">${icon("play")}Load the recorded pilot</button>` : ""}
          <a class="btn" href="#/new">${icon("plus")}Assess your own change</a>
          <a class="btn ghost" href="#/knowledge">${icon("book")}Rules and sources</a>
        </div>
      </div>
      <div class="conds" aria-label="the five takeover conditions">
        <div class="eyebrow">A takeover needs all five. Break one and it fails.</div>
        ${CHAIN_INTRO.map((c) => html`<div class="cond"><b>${c.toUpperCase()}</b><span>${COND[c].q}</span></div>`)}
      </div>
    </section>
    ${list.length ? html`
      <div class="panel">
        <div class="hd"><div><h2>Assessments</h2><div class="sub">${list.length} stored · newest first · retained ${"for the server's retention period"}</div></div>
          ${list.length > 1 ? html`<a class="btn" href="#/compare">${icon("compare")}Compare two</a>` : ""}</div>
        <div class="bd flush"><table class="t">
          <thead><tr><th>Assessment</th><th>Data as of</th><th>Policy</th><th>Gate</th><th>Verdicts</th><th class="num">Resources</th><th></th></tr></thead>
          <tbody>${list.map((a) => html`
            <tr class="click" data-href="#/a/${a.assessment_id}">
              <td><b>${labelOf(a.assessment_id, a)}</b><div class="tiny muted mono">${shortId(a.assessment_id)} · created ${ago(a.created_at)}</div></td>
              <td class="nowrap small">${when(a.as_of)}</td>
              <td class="small">${a.mode || "—"}<div class="tiny muted">${a.enforcement || ""}</div></td>
              <td>${gateBadge(a.gate_passed, a.would_pass)}</td>
              <td><div class="row">${VERDICT_ORDER.filter((v) => a.verdict_counts[v]).map((v) => html`<span class="badge v-${v}">${a.verdict_counts[v]} ${VERDICT[v].label}</span>`)}</div></td>
              <td class="num">${a.retiring ?? "—"}</td>
              <td class="num"><button class="btn ghost iconbtn danger" data-del="${a.assessment_id}" title="Delete this record" aria-label="Delete">${icon("trash")}</button></td>
            </tr>`)}</tbody></table></div>
      </div>` : html`
      <div class="panel"><div class="empty">
        ${icon("shield")}
        <div><b>No assessments yet.</b><br>${k.pilot_available ? "Load the recorded pilot to see a blocked deletion and the corrected change that passes, or run your own." : "Run an assessment on a Terraform plan to begin."}</div>
      </div></div>`}
  `);
  $$("tr[data-href]").forEach((tr) => tr.addEventListener("click", (e) => { if (!e.target.closest("button")) location.hash = tr.dataset.href; }));
  $$("[data-del]").forEach((b) => b.addEventListener("click", async () => {
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
  location.hash = `#/a/${r.imported.before_strict}`;
}

function gateBadge(passed, would) {
  if (passed && would !== false) return html`<span class="badge v-release">Pass</span>`;
  if (passed) return html`<span class="badge v-review">Advisory</span>`;
  return html`<span class="badge v-block">Fail</span>`;
}

// ---------- assessment ----------
function gateBanner(rec) {
  const g = rec.gate;
  const cls = g.passed && g.would_pass ? "pass" : g.passed ? "advisory" : "fail";
  const word = cls === "pass" ? "PASS" : cls === "advisory" ? "WARN" : "FAIL";
  const tfv = rec.plan && rec.plan.terraform_version;
  return html`
    <section class="gate ${cls}">
      <div class="word">${word}<small>Deletion gate</small></div>
      <div>
        <div class="sum">${g.summary}</div>
        <div class="meta">
          <span>Data as of ${when(rec.as_of)}</span>
          <span>Policy <b>${rec.policy.mode}</b> · ${rec.policy.enforcement}</span>
          <span>Rules ${rec.tool.rules_version}</span>
          ${tfv ? html`<span>Terraform ${tfv}</span>` : ""}
          ${g.waivers_applied ? html`<span>${g.waivers_applied} waiver(s) applied</span>` : ""}
        </div>
      </div>
      <div class="counts">${VERDICT_ORDER.filter((v) => g.verdict_counts[v]).map((v) => html`
        <div class="count"><b class="cnum-${v}">${g.verdict_counts[v]}</b><span>${VERDICT[v].label}</span></div>`)}</div>
    </section>`;
}

function assessmentActions(rec) {
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

function pathStrip(r) {
  if (!r.paths.length) return html`<div class="strip"><i></i></div>`;
  const cls = { hijackable: "h", unknown: "u", safe: "s", waived: "w" };
  return html`<div class="strip" title="reference paths: red hijackable, amber unverified, green broken">${r.paths.map((p) => html`<i class="${cls[p.status] || ""}"></i>`)}</div>`;
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
  setCrumbs([{ t: "Change reviews", href: "#/" }, { t: label }]);
  setActions(assessmentActions(rec));
  wireAssessmentActions(rec);
  const tabs = html`<nav class="tabs">
    <a href="#/a/${id}" class="${tab === "resources" ? "on" : ""}">Resources</a>
    <a href="#/a/${id}/evidence" class="${tab === "evidence" ? "on" : ""}">Evidence and provenance</a>
    <a href="#/a/${id}/report" class="${tab === "report" ? "on" : ""}">Report</a></nav>`;
  let body;
  if (tab === "evidence") body = evidenceTab(rec);
  else if (tab === "report") body = html`<div class="panel"><div class="bd"><pre class="code" id="md">Loading…</pre></div></div>`;
  else body = resourcesTab(rec);
  mount(view, html`${gateBanner(rec)}${tabs}${body}`);
  if (tab === "report") $("#md").textContent = await api.report(id);
}

function resourcesTab(rec) {
  const rs = [...rec.resources].sort((a, b) => VERDICT_ORDER.indexOf(a.verdict) - VERDICT_ORDER.indexOf(b.verdict));
  const named = rs.filter((r) => r.verdict !== "not_name_bearing");
  const other = rs.filter((r) => r.verdict === "not_name_bearing");
  const card = (r) => {
    const t = pathTally(r);
    const ns = r.resource.attributes && r.resource.attributes.bucket_namespace;
    const req = r.traffic.reduce((s, x) => s + x.requests, 0);
    return html`
      <a class="rcard ${r.verdict === "not_name_bearing" ? "muted-card" : ""}" href="#/a/${rec.assessment_id}/r/${encodeURIComponent(r.resource.address)}">
        <div class="spread">${verdictBadge(r.verdict)}<span class="tiny muted">${r.resource.type}</span></div>
        <div><div class="nm">${r.resource.name || r.resource.address}</div><div class="addr">${r.resource.address}</div></div>
        ${pathStrip(r)}
        <div class="why">${r.reasons[0] || ""}</div>
        <div class="row tiny">
          ${r.paths.length ? html`<span class="chip"><b>${r.paths.length}</b> paths</span>` : html`<span class="chip">no references found</span>`}
          ${t.hijackable ? html`<span class="chip s-hijackable"><b>${t.hijackable}</b> hijackable</span>` : ""}
          ${t.unknown ? html`<span class="chip s-unknown"><b>${t.unknown}</b> unverified</span>` : ""}
          ${ns ? html`<span class="chip">${ns} namespace</span>` : ""}
          ${r.traffic.length ? html`<span class="chip"><b>${compact(req)}</b> requests</span>` : ""}
        </div>
      </a>`;
  };
  const nc = rec.not_checked || [];
  return html`
    <div class="cards">${named.map(card)}</div>
    ${other.length ? html`<div class="stack"><div class="eyebrow">Also deleted by this plan · no reclaimable name</div><div class="cards">${other.map(card)}</div></div>` : ""}
    ${nc.length ? html`<div class="notice">${icon("info")}<div><b>Not checked by this assessment.</b> ${nc.join("; ")}.</div></div>` : ""}`;
}

function evidenceTab(rec) {
  const red = rec.tool.redaction || {};
  const sr = red.secret_rules || {};
  const logs = Object.entries(rec.parse_stats || {});
  const cited = Object.entries(rec.sources || {});
  return html`
    <div class="grid g2">
      <div class="panel"><div class="hd"><h2>Inputs</h2><span class="sub">hashed when read</span></div>
        <div class="bd flush"><table class="t"><thead><tr><th>Role</th><th>Input</th><th>Fingerprint</th></tr></thead><tbody>
        ${(rec.inputs || []).map((i) => html`<tr><td class="small nowrap">${i.role}</td>
          <td><b class="small">${i.label || i.name}</b><div class="tiny muted">${i.bytes !== undefined ? bytes(i.bytes) : ""}${i.files !== undefined ? `${i.files} files` : ""}</div></td>
          <td class="hash">${i.sha256 ? html`sha256 ${i.sha256}` : i.sha256_tree ? html`tree sha256 ${i.sha256_tree}` : "—"}</td></tr>`)}
        </tbody></table></div></div>
      <div class="panel"><div class="hd"><h2>Tool and policy</h2></div><div class="bd stack">
        <dl class="kv">
          <dt>Tool</dt><dd>${rec.tool.name} ${rec.tool.version} · Python ${rec.tool.python}</dd>
          <dt>Rule set</dt><dd>${rec.tool.rules_version}</dd>
          <dt>Fingerprints</dt><dd class="hash">can-i-take-over-xyz @ ${rec.tool.fingerprint_catalogue_commit}</dd>
          <dt>Redaction</dt><dd>${red.terraform_sensitivity_mask ? "Terraform sensitivity masks" : ""}${red.attribute_minimisation ? " · attribute minimisation" : ""}${sr.loaded ? ` · ${sr.loaded} gitleaks rules` : ""}${sr.commit ? html` <span class="hash">@ ${sr.commit.slice(0, 12)}</span>` : ""}</dd>
          <dt>Mode</dt><dd>${rec.policy.mode} · ${rec.policy.enforcement}</dd>
          <dt>α (miss rate)</dt><dd>${rec.policy.alpha}</dd>
          <dt>β (rate bound)</dt><dd>${rec.policy.beta}</dd>
          <dt>Minimum log window</dt><dd>${rec.policy.min_window_days} d · logs must end within ${rec.policy.max_staleness_days} d</dd>
          <dt>Organisation accounts</dt><dd>${(rec.policy.org_account_ids || []).join(", ") || "—"}</dd>
          <dt>Internal domains</dt><dd>${(rec.policy.internal_domains || []).join(", ") || "—"}</dd>
          <dt>Waiver limit</dt><dd>${rec.policy.max_waiver_days} d</dd>
        </dl></div></div>
    </div>
    ${logs.length ? html`<div class="panel"><div class="hd"><h2>Access logs</h2><span class="sub">lines per day; shaded days had no logging at all</span></div>
      <div class="bd flush"><table class="t"><thead><tr><th>Log</th><th class="num">Lines</th><th class="num">Parsed</th><th class="num">Unparseable</th><th>Coverage</th></tr></thead><tbody>
      ${logs.map(([n, s]) => html`<tr><td class="mono small">${n}</td><td class="num">${num(s.lines)}</td><td class="num">${num(s.parsed)}</td>
        <td class="num">${num(s.failed)} <span class="tiny muted">(${num((100 * s.failed) / Math.max(1, s.lines), 2)}%)</span></td>
        <td>${coverageSpark(s.first_day, s.daily_lines)}${s.first_day ? html`<div class="tiny muted">from ${s.first_day}, ${(s.daily_lines || []).filter((x) => !x).length} day(s) without logging</div>` : ""}</td></tr>`)}
      </tbody></table></div></div>` : ""}
    ${Object.keys(rec.scan_stats || {}).length ? html`<div class="panel"><div class="hd"><h2>Repository scan</h2></div><div class="bd flush"><table class="t">
      <thead><tr><th>Repository</th><th class="num">Files scanned</th><th class="num">Skipped (binary)</th><th class="num">Skipped (large)</th><th class="num">Common-word matches discarded</th></tr></thead><tbody>
      ${Object.entries(rec.scan_stats).map(([n, s]) => html`<tr><td class="mono small">${n}</td><td class="num">${num(s.files_scanned)}</td><td class="num">${num(s.files_skipped_binary)}</td><td class="num">${num(s.files_skipped_large)}</td><td class="num">${num(s.literal_matches_discarded)}</td></tr>`)}
      </tbody></table></div></div>` : ""}
    ${(rec.waivers_rejected || []).length ? html`<div class="notice warn">${icon("alert")}<div><b>Waivers rejected:</b> ${rec.waivers_rejected.map((w) => `${w.resource || w.id || "?"}: ${w.reason || w.error || ""}`).join("; ")}</div></div>` : ""}
    <div class="panel"><div class="hd"><div><h2>Sources cited by this assessment</h2><div class="sub">every rule that decided a condition, with the primary text it rests on</div></div></div>
      <div class="bd flush">${cited.map(([k, s]) => sourceItem(k, s))}</div></div>`;
}

function sourceItem(k, s) {
  return html`<div class="src">
    <div class="spread"><b>${s.title}</b><span class="hash">src:${k}</span></div>
    ${s.quote ? html`<blockquote>${s.quote}</blockquote>` : ""}
    <div class="tiny muted">${s.verified_via ? html`Verified via ${s.verified_via}` : ""}${s.url ? html` · <a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.url}</a>` : ""}</div>
  </div>`;
}

// ---------- resource ----------
function linkClass(a, b) {
  const v = [a, b];
  if (v.includes("false")) return "broken";
  if (v.includes("unknown")) return "u";
  return "t";
}

function chainRow(rec, r, p, i) {
  const ref = r.references.find((x) => x.id === p.reference_id) || { kind: "?", location: p.reference_id, text: "" };
  const cs = ["c1", "c2", "c3", "c4", "c5"];
  const statusText = { hijackable: "Hijackable", unknown: "Unverified", safe: "Broken", waived: "Waived" }[p.status] || p.status;
  const integ = { sri: "Subresource Integrity", expected_bucket_owner: "ExpectedBucketOwner" }[ref.integrity_control] || ref.integrity_control;
  return html`
    <div class="chain-row" data-path="${i}">
      <div class="ref">
        <div class="tags"><span class="chip">${ref.kind}</span>${ref.method ? html`<span class="chip">${ref.method}</span>` : ""}${ref.context && ref.context !== "code" ? html`<span class="chip">${ref.context}</span>` : ""}${integ ? html`<span class="chip s-safe">${integ}</span>` : ""}${ref.removed_in_change ? html`<span class="chip s-safe">removed in this change</span>` : ""}</div>
        <div class="loc">${ref.location}</div>
        <div class="txt" title="${ref.text}">${ref.text}</div>
      </div>
      <div class="chain" role="group" aria-label="conditions">
        ${cs.map((c, j) => {
          const v = p.conditions[c] ? p.conditions[c].value : "unknown";
          return html`${j ? html`<span class="link ${linkClass(p.conditions[cs[j - 1]]?.value, v)}"></span>` : ""}
            <button class="node ${v}" data-c="${c}" data-p="${i}" title="${COND[c].long}: ${triLabel(v)}"><b>${c.toUpperCase()}</b>${raw(esc(COND[c].short).replace("&amp;shy;", "&shy;"))}</button>`;
        })}
      </div>
      <div class="status-cell"><b class="s-${p.status}">${statusText}</b>
        <span class="tiny muted">${p.broken_by.length ? `broken at ${p.broken_by.map((c) => c.toUpperCase()).join(", ")}` : p.status === "hijackable" ? "all five hold" : p.status === "unknown" ? "a condition is unverified" : ""}</span></div>
    </div>`;
}

function evidenceItems(rec, ids) {
  return html`<div class="ev">${ids.map((id) => {
    if (id.startsWith("src:")) {
      const s = (rec.sources || {})[id.slice(4)];
      return s ? html`<div class="ev-item"><b class="small">${s.title}</b><blockquote>${s.quote}</blockquote><div class="tiny muted">${s.verified_via || ""}</div><span class="id">${id}</span></div>`
        : html`<div class="ev-item"><span class="id">${id}</span></div>`;
    }
    const e = (rec.evidence || []).find((x) => x.id === id);
    return e ? html`<div class="ev-item"><div class="spread"><b class="small">${e.detail}</b><span class="chip">${e.source}</span></div><div class="tiny muted mono">${e.location}</div><span class="id">${id}</span></div>`
      : html`<div class="ev-item"><span class="id">${id}</span></div>`;
  })}</div>`;
}

function inspector(rec, r, i, c) {
  const p = r.paths[i];
  const cond = p.conditions[c];
  const v = cond ? cond.value : "unknown";
  return html`
    <div class="hdr"><span class="badge plain ${v === "true" ? "v-block" : v === "false" ? "v-release" : "v-review"}">${triLabel(v)}</span><h3>${COND[c].long}</h3></div>
    <div class="dim small">${COND[c].q}</div>
    <div>${cond ? cond.reason : "not evaluated"}</div>
    ${cond && cond.evidence_ids.length ? evidenceItems(rec, cond.evidence_ids) : ""}`;
}

function trafficBlock(rec, r, t) {
  const file = t.source.split("[")[0];
  const cov = (rec.parse_stats || {})[file];
  const chart = trafficChart(t, cov && cov.daily_lines, rec.as_of);
  const p = rec.policy;
  const q = t.quarantine_days_conservative;
  let verdict;
  if (!t.fresh) verdict = html`<div class="verdict-line notice warn">The log ends more than ${p.max_staleness_days} d before the assessment time, so it cannot show whether consumers remain (C4 UNKNOWN).</div>`;
  else if (!t.window_sufficient) verdict = html`<div class="verdict-line notice warn">The log covers ${days(t.window_days)}, less than the ${p.min_window_days} d minimum, so silence cannot be trusted (C4 UNKNOWN).</div>`;
  else if (!t.requests) verdict = html`<div class="verdict-line notice warn">No requests in the window. With zero events the rate bound is zero and no quarantine can be computed; silence alone is not treated as proof of no consumers.</div>`;
  else if (t.silence_days > q) verdict = html`<div class="verdict-line notice">${icon("info")}<div>Silent for <b>${days(t.silence_days)}</b>, longer than the conservative quarantine <b>${days(q)}</b>: a consumer at even the lower-bound rate would have been seen with probability ≥ ${num(100 * (1 - p.alpha), 0)}%. The logs show no remaining consumer.</div></div>`;
  else verdict = html`<div class="verdict-line notice err">${icon("alert")}<div>Silent for only <b>${days(t.silence_days)}</b>, within the conservative quarantine <b>${days(q)}</b>: consumers are still active.</div></div>`;
  const lnA = -Math.log(p.alpha);
  return html`
    <div class="stack">
      <div class="spread"><div class="mono small">${t.source}</div><div class="tiny muted">${when(t.window_start)} → ${when(t.window_end)} · ${days(t.window_days)}</div></div>
      ${chart || html`<div class="notice">${icon("info")}<div>This record predates daily counts; statistics only.</div></div>`}
      <div class="legend"><span><span class="sw bar"></span>requests per day</span><span class="tiny">amber band: quarantine D* after the last request · green band: observed silence · grey columns: no logging that day</span></div>
      <div class="stats">
        <div class="stat"><span>Requests</span><b>${num(t.requests)}</b></div>
        <div class="stat"><span>Clients · external</span><b>${num(t.distinct_clients)} · ${t.external_share === null ? "—" : num(100 * t.external_share, 0) + "%"}</b></div>
        <div class="stat"><span>Last request</span><b>${when(t.last_seen, false)}</b></div>
        <div class="stat"><span>Silence vs D*</span><b>${days(t.silence_days)} / ${days(q)}</b></div>
      </div>
      ${t.requests ? html`<div class="formula">
        λ̂ = n / T = ${num(t.requests)} / ${num(t.window_days, 2)} d = <b>${rate(t.rate_mle_per_day)}</b><br>
        λ<sub>lo</sub> = Gamma<sup>-1</sup>(β = ${p.beta}; n + ½, T) = <b>${rate(t.rate_lower_per_day)}</b> <span class="muted">(Jeffreys posterior, lower bound)</span><br>
        D* = −ln α / λ<sub>lo</sub> = ${num(lnA, 3)} / ${num(t.rate_lower_per_day, t.rate_lower_per_day < 10 ? 3 : 0)} = <b>${days(q)}</b> <span class="muted">(α = ${p.alpha})</span>
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
  const label = labelOf(id, summaryOf(rec));
  setCrumbs([{ t: "Change reviews", href: "#/" }, { t: label, href: `#/a/${id}` }, { t: addr }]);
  setActions(assessmentActions(rec));
  wireAssessmentActions(rec);
  const res = r.resource;
  const attrs = res.attributes || {};
  const t = pathTally(r);
  const rc = r.reclaimable;
  mount(view, html`
    <section class="panel"><div class="bd stack">
      <div class="spread">
        <div class="row">${verdictBadge(r.verdict)}<span class="mono small dim">${res.address}</span></div>
        <div class="row tiny muted"><span>${res.type}</span>${res.region ? html`<span>· ${res.region}</span>` : ""}<span>· action ${res.action}</span></div>
      </div>
      <h1 class="break">${res.name || res.address}</h1>
      <div class="stack">${r.reasons.map((x) => html`<div>${x}</div>`)}</div>
      <div class="row tiny">
        ${r.paths.length ? html`<span class="chip"><b>${r.paths.length}</b> reference paths</span>` : ""}
        ${t.hijackable ? html`<span class="chip s-hijackable"><b>${t.hijackable}</b> hijackable</span>` : ""}
        ${t.unknown ? html`<span class="chip s-unknown"><b>${t.unknown}</b> unverified</span>` : ""}
        ${t.safe ? html`<span class="chip s-safe"><b>${t.safe}</b> broken</span>` : ""}
        <span class="chip">risk interval <b>${num(r.risk_interval[0], 2)}–${num(r.risk_interval[1], 2)}</b></span>
      </div>
    </div></section>

    <section class="panel">
      <div class="hd"><div><h2>Takeover paths</h2><div class="sub">each surviving reference against the five conditions · select a condition to see its evidence</div></div>
        <div class="legend"><span><span class="sw"></span>holds</span><span><span class="sw u"></span>unverified</span><span><span class="sw b"></span>broken</span></div></div>
      ${r.paths.length ? html`<div class="chains">${r.paths.map((p, i) => chainRow(rec, r, p, i))}</div><div class="inspector hidden" id="insp"></div>`
        : html`<div class="bd"><div class="notice">${icon("info")}<div>No reference to this name was found in the supplied DNS inventory, infrastructure plan, repositories or access logs. ${rc.value === "false" ? "The name cannot be obtained by anyone else, so release is safe regardless." : ""}</div></div></div>`}
    </section>

    <div class="split">
      <div class="stack">
        ${r.traffic.length ? html`<section class="panel"><div class="hd"><div><h2>Consumers in access logs</h2><div class="sub">condition C4: is anyone still asking for this name?</div></div></div>
          <div class="bd stack">${r.traffic.map((x) => trafficBlock(rec, r, x))}</div></section>` : ""}
        ${r.patches.length ? html`<section class="panel"><div class="hd"><div><h2>Remediation</h2><div class="sub">generated from the evidence; apply, then re-run the assessment</div></div></div>
          <div class="bd stack">${r.patches.map((p, i) => html`
            <div class="stack">
              <div class="spread"><div><span class="chip">${PATCH_KIND[p.kind] || p.kind}</span> <b>${p.title}</b></div>
                <div class="row"><button class="btn ghost iconbtn" data-copy="${i}" title="Copy" aria-label="Copy">${icon("copy")}</button><button class="btn ghost iconbtn" data-dl="${i}" title="Download" aria-label="Download">${icon("download")}</button></div></div>
              ${p.applies_to && p.applies_to.length ? html`<div class="tiny muted">applies to ${p.applies_to.join(", ")}</div>` : ""}
              ${codeBlock(p.content, p.kind)}
            </div>`)}</div></section>` : ""}
      </div>
      <div class="stack">
        <section class="panel"><div class="hd"><h2>Can someone else get this name?</h2>
          <span class="badge plain ${rc.value === "true" ? "v-block" : rc.value === "false" ? "v-release" : "v-review"}">C2 ${triLabel(rc.value)}</span></div>
          <div class="bd stack"><div>${rc.reason}</div>${evidenceItems(rec, rc.evidence_ids)}</div></section>
        ${r.tombstone ? html`<section class="panel"><div class="hd"><h2>Tombstone plan</h2><span class="badge v-tombstone">keep the name</span></div>
          <div class="bd stack"><dl class="kv">
            <dt>Review after</dt><dd>${r.tombstone.review_after} <span class="muted">(${r.tombstone.review_basis_days} d after the data)</span></dd>
            <dt>Holding cost</dt><dd>${r.tombstone.holding_cost}</dd>
            <dt>Exit</dt><dd>${r.tombstone.release_path}</dd></dl>
            ${r.tombstone.sources && r.tombstone.sources.length ? evidenceItems(rec, r.tombstone.sources) : ""}</div></section>` : ""}
        ${(r.waivers_applied || []).length ? html`<section class="panel"><div class="hd"><h2>Waivers applied</h2></div><div class="bd stack">
          ${r.waivers_applied.map((w) => html`<dl class="kv"><dt>Type</dt><dd>${w.type || w.kind || ""}</dd><dt>Approver</dt><dd>${w.approver || ""}</dd><dt>Expires</dt><dd>${w.expires || ""}</dd><dt>Reason</dt><dd>${w.reason || ""}</dd></dl>`)}</div></section>` : ""}
        <section class="panel"><div class="hd"><h2>Resource</h2></div><div class="bd stack">
          <dl class="kv">${Object.entries(attrs).filter(([k, v]) => !k.startsWith("_") && v !== null && v !== "").map(([k, v]) => html`<dt class="mono tiny">${k}</dt><dd class="mono tiny">${typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>`)}</dl>
          ${attrs._omitted_attributes ? html`<div class="tiny muted">${attrs._omitted_attributes} further attributes were not stored (attribute minimisation).</div>` : ""}
          ${res.endpoints && res.endpoints.length ? html`<details class="fold"><summary>${res.endpoints.length} names this resource answers to</summary>
            <div class="stack small fold-body">${res.endpoints.map((e) => html`<div class="mono tiny"><span class="muted">${e.kind}</span> ${e.name}</div>`)}</div></details>` : ""}
        </div></section>
        ${r.not_checked.length ? html`<section class="panel"><div class="hd"><h2>Not checked</h2></div><div class="bd"><ul class="small dim">${r.not_checked.map((x) => html`<li>${x}</li>`)}</ul></div></section>` : ""}
      </div>
    </div>`);

  const insp = $("#insp");
  $$(".node").forEach((n) => n.addEventListener("click", () => {
    const already = n.classList.contains("sel");
    $$(".node.sel").forEach((x) => x.classList.remove("sel"));
    if (already) { insp.classList.add("hidden"); return; }
    n.classList.add("sel");
    mount(insp, inspector(rec, r, Number(n.dataset.p), n.dataset.c));
    insp.classList.remove("hidden");
    const row = n.closest(".chain-row");
    row.after(insp);
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
  setCrumbs([{ t: "Change reviews", href: "#/" }, { t: "Compare" }]);
  setActions("");
  loading();
  const list = await api.list(200);
  const tags = pilotTags();
  if (!a || !b) {
    if (tags.before_strict && tags.after_strict && list.some((x) => x.assessment_id === tags.after_strict)) [a, b] = [tags.before_strict, tags.after_strict];
    else if (list.length >= 2) [a, b] = [list[1].assessment_id, list[0].assessment_id];
  }
  const picker = (sel, idn) => html`<select class="input" id="${idn}">${list.map((x) => html`<option value="${x.assessment_id}" ${x.assessment_id === sel ? raw("selected") : ""}>${labelOf(x.assessment_id, x)} (${shortId(x.assessment_id)})</option>`)}</select>`;
  if (list.length < 2) {
    mount(view, html`<div class="panel"><div class="empty">${icon("compare")}<div>Two assessments are needed to compare. Run the same change before and after applying RetireSafe's fixes.</div></div></div>`);
    return;
  }
  const [A, B] = await Promise.all([api.get(a), api.get(b)]);
  const addrs = [...new Set([...A.resources, ...B.resources].map((r) => r.resource.address))];
  const byA = Object.fromEntries(A.resources.map((r) => [r.resource.address, r]));
  const byB = Object.fromEntries(B.resources.map((r) => [r.resource.address, r]));
  const hij = (rec) => rec.resources.reduce((s, r) => s + r.paths.filter((p) => p.status === "hijackable").length, 0);
  const mini = (rec, id) => html`<a class="mini-gate ${rec.gate.passed ? "pass" : "fail"}" href="#/a/${id}">
      <div class="spread"><span class="w">${rec.gate.passed ? "PASS" : "FAIL"}</span><span class="tiny muted">${rec.policy.mode}</span></div>
      <div class="small">${labelOf(id, summaryOf(rec))}</div>
      <div class="tiny muted">${hij(rec)} hijackable path(s) · ${rec.resources.length} resources retiring</div></a>`;
  const inputsA = Object.fromEntries((A.inputs || []).map((i) => [i.role + ":" + (i.label || i.name), i]));
  const inputsB = Object.fromEntries((B.inputs || []).map((i) => [i.role + ":" + (i.label || i.name), i]));
  const fp = (i) => i && (i.sha256 || i.sha256_tree);
  const roles = [...new Set([...(A.inputs || []), ...(B.inputs || [])].map((i) => i.role))];
  mount(view, html`
    <div class="panel"><div class="bd grid g2">
      <div class="field"><span class="lab">Before</span>${picker(a, "pa")}</div>
      <div class="field"><span class="lab">After</span>${picker(b, "pb")}</div>
    </div></div>
    <div class="flow">${mini(A, a)}<div class="arrow">→</div>${mini(B, b)}</div>
    <div class="panel"><div class="hd"><h2>Verdicts by resource</h2></div><div class="bd flush"><table class="t">
      <thead><tr><th>Resource</th><th>Before</th><th>After</th><th>What changed</th></tr></thead><tbody>
      ${addrs.map((ad) => {
        const x = byA[ad], y = byB[ad];
        const note = !y ? "no longer deleted by the plan: the name is kept"
          : !x ? "newly deleted by the plan"
          : x.verdict === y.verdict ? "unchanged" : `${VERDICT[x.verdict].label} → ${VERDICT[y.verdict].label}`;
        const hx = x ? x.paths.filter((p) => p.status === "hijackable").length : 0;
        const hy = y ? y.paths.filter((p) => p.status === "hijackable").length : 0;
        return html`<tr><td><div class="mono small">${ad}</div><div class="tiny muted">${(x || y).resource.name || ""}</div></td>
          <td>${x ? verdictBadge(x.verdict) : html`<span class="muted small">not retiring</span>`}${x && hx ? html`<div class="tiny s-hijackable">${hx} hijackable</div>` : ""}</td>
          <td>${y ? verdictBadge(y.verdict) : html`<span class="badge v-tombstone">kept</span>`}${y && hy ? html`<div class="tiny s-hijackable">${hy} hijackable</div>` : ""}</td>
          <td class="small dim">${note}</td></tr>`;
      })}</tbody></table></div></div>
    <div class="panel"><div class="hd"><h2>Inputs</h2><span class="sub">what was different between the two runs</span></div><div class="bd flush"><table class="t">
      <thead><tr><th>Role</th><th>Before</th><th>After</th><th></th></tr></thead><tbody>
      ${roles.map((role) => {
        const ia = (A.inputs || []).filter((i) => i.role === role), ib = (B.inputs || []).filter((i) => i.role === role);
        const same = ia.length === ib.length && ia.every((i) => ib.some((j) => fp(j) === fp(i)));
        return html`<tr><td class="small">${role}</td><td class="small">${ia.map((i) => html`<div>${i.label || i.name} <span class="hash">${(fp(i) || "").slice(0, 12)}</span></div>`)}</td>
          <td class="small">${ib.map((i) => html`<div>${i.label || i.name} <span class="hash">${(fp(i) || "").slice(0, 12)}</span></div>`)}</td>
          <td>${same ? html`<span class="badge v-neutral">identical</span>` : html`<span class="badge v-review">changed</span>`}</td></tr>`;
      })}</tbody></table></div></div>`);
  const go = () => { location.hash = `#/compare/${$("#pa").value}/${$("#pb").value}`; };
  $("#pa").addEventListener("change", go);
  $("#pb").addEventListener("change", go);
  void inputsA; void inputsB;
}

// ---------- new assessment ----------
async function newAssessment() {
  markNav("new");
  setCrumbs([{ t: "Change reviews", href: "#/" }, { t: "New assessment" }]);
  setActions("");
  mount(view, html`
    <form id="nf" class="stack" autocomplete="off">
      <div class="panel"><div class="hd"><div><h2>1 · The change</h2><div class="sub">a Terraform plan in JSON: <code class="inline-code">terraform show -json plan.out &gt; plan.json</code></div></div></div>
        <div class="bd grid g2">
          ${dropzone("plan", "Terraform plan (JSON)", "required", false, ".json")}
          ${dropzone("dns", "DNS inventory", "Route 53 export (list-resource-record-sets JSON) or BIND zone files", true, "")}
        </div></div>
      <div class="panel"><div class="hd"><div><h2>2 · Where the names might still be used</h2><div class="sub">repositories are scanned in memory on the server and deleted after the run</div></div></div>
        <div class="bd grid g2">
          ${dropzone("repo", "Repository archive", ".zip or .tar.gz of the code that may reference the resources", false, ".zip,.tar,.gz,.tgz")}
          <div class="field"><label for="repoLabel">Repository label</label><input class="input" id="repoLabel" placeholder="app"><span class="hint">shown in file:line locations</span></div>
          ${dropzone("logs", "Access logs", "S3 server access logs, CloudFront standard logs, or Common Log Format", true, "")}
          <div class="field"><span class="lab">Log settings</span><div id="logrows" class="stack"><span class="hint">add log files to configure them</span></div></div>
        </div></div>
      <div class="panel"><div class="hd"><div><h2>3 · Policy</h2><div class="sub">strict never releases a name someone else could claim; balanced releases on evidence</div></div></div>
        <div class="bd grid g3">
          <div class="field"><span class="lab">Mode</span><div class="seg"><label><input type="radio" name="mode" value="strict" checked><span>Strict</span></label><label><input type="radio" name="mode" value="balanced"><span>Balanced</span></label></div></div>
          <div class="field"><span class="lab">Enforcement</span><div class="seg"><label><input type="radio" name="enf" value="enforce" checked><span>Enforce</span></label><label><input type="radio" name="enf" value="advisory"><span>Advisory</span></label></div><span class="hint">advisory reports but never fails the gate</span></div>
          <div class="field"><label for="alpha">α · tolerated miss probability</label><input class="input" id="alpha" type="number" step="any" min="0.0001" max="0.5" value="0.01"></div>
          <div class="field"><label for="accts">Organisation account IDs</label><input class="input" id="accts" placeholder="123456789012, 210987654321"></div>
          <div class="field"><label for="idom">Internal domains / CIDRs</label><input class="input" id="idom" placeholder="corp.example, 10.0.0.0/8"><span class="hint">clients here are not counted as external</span></div>
          <div class="field"><label for="asof">Assess as of (optional)</label><input class="input" id="asof" placeholder="2026-10-01T00:00:00Z"><span class="hint">defaults to now</span></div>
          <div class="field"><label for="mig">Migrations (optional)</label><textarea class="input" id="mig" placeholder="old-bucket=new-bucket-123456789012-us-east-1-an"></textarea><span class="hint">one old=new per line; used to write code patches</span></div>
          <div class="field"><label for="waivers">Waivers (optional JSON list)</label><textarea class="input" id="waivers" placeholder='[{"resource": "...", "type": "accept_reference", ...}]'></textarea></div>
        </div></div>
      <div class="spread"><div id="nmsg" class="small dim"></div><button class="btn primary" id="go">${icon("shield")}Run assessment</button></div>
    </form>`);
  const files = { plan: [], dns: [], repo: [], logs: [] };
  $$(".drop input[type=file]").forEach((inp) => {
    const zone = inp.closest(".drop");
    const show = () => {
      files[inp.name] = [...inp.files];
      mount($(".files", zone), files[inp.name].map((f) => html`<div>${f.name} <span class="muted">${bytes(f.size)}</span></div>`));
      if (inp.name === "logs") renderLogRows();
    };
    inp.addEventListener("change", show);
    ["dragenter", "dragover"].forEach((e) => zone.addEventListener(e, () => zone.classList.add("over")));
    ["dragleave", "drop"].forEach((e) => zone.addEventListener(e, () => zone.classList.remove("over")));
  });
  function renderLogRows() {
    const box = $("#logrows");
    if (!files.logs.length) { mount(box, html`<span class="hint">add log files to configure them</span>`); return; }
    mount(box, files.logs.map((f, i) => html`<div class="logrow" data-i="${i}">
      <span class="mono tiny break">${f.name}</span>
      <select class="input" data-k="format"><option value="s3">S3 access</option><option value="cloudfront">CloudFront</option><option value="clf">CLF</option></select>
      <input class="input" data-k="host" placeholder="host (CLF: required)">
      <input class="input" data-k="path_prefix" placeholder="path prefix (optional)"></div>`));
  }
  const csv = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);
  $("#nf").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const msg = $("#nmsg");
    if (!files.plan.length) { mount(msg, html`<span class="s-hijackable">A Terraform plan is required.</span>`); return; }
    const internal = csv($("#idom").value);
    const policy = {
      mode: $("input[name=mode]:checked").value, enforcement: $("input[name=enf]:checked").value,
      alpha: Number($("#alpha").value), org_account_ids: csv($("#accts").value),
      internal_domains: internal.filter((x) => !/[/:]|^\d+\.\d+/.test(x)), internal_cidrs: internal.filter((x) => /[/:]|^\d+\.\d+/.test(x)),
    };
    const cfg = { policy };
    if ($("#asof").value.trim()) cfg.as_of = $("#asof").value.trim();
    if ($("#repoLabel").value.trim()) cfg.repo_label = $("#repoLabel").value.trim();
    const mig = $("#mig").value.split("\n").map((l) => l.trim()).filter(Boolean);
    if (mig.length) cfg.migrate_to = Object.fromEntries(mig.map((l) => l.split("=").map((x) => x.trim())));
    if ($("#waivers").value.trim()) {
      try { cfg.waivers = JSON.parse($("#waivers").value); } catch (e) { mount(msg, html`<span class="s-hijackable">Waivers are not valid JSON: ${e.message}</span>`); return; }
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
    const tick = setInterval(() => mount(msg, html`<span class="spinner"></span> ${phase} · ${Math.round((Date.now() - t0) / 1000)} s`), 500);
    try {
      const rec = await api.createAssessment(fd, (f) => { phase = f >= 1 ? "Assessing (large logs take a minute)" : `Uploading ${Math.round(f * 100)}%`; });
      location.hash = `#/a/${rec.assessment_id}`;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { errorView(e, newAssessment); return; }
      mount(msg, html`<span class="s-hijackable">${e.message}</span>`);
    } finally { clearInterval(tick); btn.disabled = false; }
  });
}

function dropzone(name, title, hint, multiple, accept) {
  return html`<div class="drop"><input type="file" name="${name}" ${multiple ? raw("multiple") : ""} ${accept ? raw(`accept="${esc(accept)}"`) : ""} aria-label="${title}">
    <span class="t">${title}</span><span class="hint">${hint === "required" ? "required · drop a file or click" : hint}</span><div class="files"></div></div>`;
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
  setCrumbs([{ t: "Drift scan" }]);
  setActions("");
  loading();
  const k = await api.knowledge();
  const owned = k.owned_domains || [];
  mount(view, html`
    <div class="panel"><div class="hd"><div><h2>Live drift scan</h2><div class="sub">read-only DNS lookups and unauthenticated S3 checks for names you already publish</div></div></div>
      <div class="bd stack">
        ${owned.length ? html`<div class="notice">${icon("info")}<div>Scope is limited to the domains this server was told your organisation owns: ${owned.map((d) => html`<code class="inline-code">${d}</code> `)}. Other names are refused.</div></div>`
          : html`<div class="notice warn">${icon("alert")}<div><b>Live scans are disabled.</b> Start the server with <code class="inline-code">RETIRESAFE_OWNED_DOMAINS=example.com,example.org</code> listing domains you own. RetireSafe never probes names outside that list.</div></div>`}
        <div class="field"><label for="hosts">Hostnames, one per line</label><textarea class="input" id="hosts" placeholder="cdn.example.com&#10;assets.example.com" ${owned.length ? "" : raw("disabled")}></textarea></div>
        <div class="spread"><span class="small dim" id="smsg"></span><button class="btn primary" id="sgo" ${owned.length ? "" : raw("disabled")}>${icon("radar")}Scan</button></div>
      </div></div>
    <div id="sres"></div>`);
  if (!owned.length) return;
  $("#sgo").addEventListener("click", async () => {
    const hosts = $("#hosts").value.split(/\s+/).map((h) => h.trim()).filter(Boolean);
    if (!hosts.length) return;
    $("#sgo").disabled = true;
    mount($("#smsg"), html`<span class="spinner"></span> resolving ${hosts.length} name(s)…`);
    try {
      const r = await api.scan(hosts);
      mount($("#smsg"), html`${r.names} checked · ${r.reclaimable} reclaimable`);
      mount($("#sres"), html`<div class="panel"><div class="hd"><h2>Findings</h2><span class="sub">${when(r.created_at)}</span></div>
        ${r.refused_not_owned.length ? html`<div class="bd"><div class="notice warn">${icon("alert")}<div>Refused (not under an owned domain): ${r.refused_not_owned.join(", ")}</div></div></div>` : ""}
        <div class="bd flush"><table class="t"><thead><tr><th>Hostname</th><th>Classification</th><th>CNAME chain</th><th>Service</th><th>Detail</th></tr></thead><tbody>
        ${r.findings.map((f) => { const l = LADDER[f.classification] || ["v-neutral", f.classification, ""]; return html`<tr>
          <td class="mono small">${f.hostname}</td><td><span class="badge ${l[0]}" title="${l[2]}">${l[1]}</span></td>
          <td class="mono tiny">${f.chain.length ? f.chain.join(" → ") : "—"}</td><td class="small">${f.service || "—"}</td><td class="small dim">${f.detail}</td></tr>`; })}
        </tbody></table></div></div>`);
    } catch (e) { mount($("#smsg"), html`<span class="s-hijackable">${e.message}</span>`); }
    finally { $("#sgo").disabled = false; }
  });
}

// ---------- knowledge ----------
async function knowledge() {
  markNav("knowledge");
  setCrumbs([{ t: "Rules and sources" }]);
  setActions(html`<a class="btn ghost" href="/docs" target="_blank" rel="noopener">${icon("ext")}API reference</a>`);
  loading();
  const k = await api.knowledge();
  const src = Object.entries(k.sources);
  mount(view, html`
    <div class="grid g3">
      <div class="panel"><div class="bd stack"><span class="eyebrow">Rule set</span><h2 class="mono">${k.rules_version}</h2><span class="small dim">versioned with every evidence record</span></div></div>
      <div class="panel"><div class="bd stack"><span class="eyebrow">Fingerprint catalogue</span><h2 class="mono">${k.fingerprint_catalogue_commit.slice(0, 12)}</h2><span class="small dim">can-i-take-over-xyz, pinned commit</span></div></div>
      <div class="panel"><div class="bd stack"><span class="eyebrow">Name-bearing types</span><h2 class="mono">${k.name_bearing_resource_types.length}</h2><span class="small dim">resource types whose deletion can free a claimable name</span></div></div>
    </div>
    <div class="panel"><div class="hd"><h2>Covered resource types</h2></div><div class="bd row">${k.name_bearing_resource_types.map((t) => html`<span class="chip mono">${t}</span>`)}</div></div>
    <div class="panel"><div class="hd"><div><h2>Source register</h2><div class="sub">${src.length} primary sources; each rule cites the text it rests on</div></div></div>
      <div class="bd flush">${src.map(([key, s]) => sourceItem(key, s))}</div></div>`);
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
    mount($("#health"), html`<div class="row"><span><span class="dot ok"></span>API online</span><span class="mono">v${h.version}</span></div>
      ${k ? html`<div class="row"><span>Rules</span><span class="mono">${k.rules_version}</span></div>` : ""}`);
  } catch {
    mount($("#health"), html`<div class="row"><span><span class="dot bad"></span>API unreachable</span></div>`);
  }
}

function theme() {
  const saved = store.get("retiresafe.theme", null);
  if (saved) document.documentElement.dataset.theme = saved;
  $("#theme").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    const next = cur === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    store.set("retiresafe.theme", next);
  });
}

theme();
health();
window.addEventListener("hashchange", route);
route();
