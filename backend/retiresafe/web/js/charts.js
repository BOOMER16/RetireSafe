// Hand-drawn SVG charts (no chart library: nothing third-party runs in the console).
import { html, raw, compact, when, days } from "./util.js";

const DAY = 86400000;
const midnight = (iso) => { const d = new Date(iso); return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()); };

function ticks(max) {
  if (max <= 0) return [0];
  const step = 10 ** Math.floor(Math.log10(max));
  const nice = [1, 2, 5, 10].map((m) => m * step).find((s) => max / s <= 4) || step * 10;
  const out = [];
  for (let v = 0; v <= max + 1e-9; v += nice) out.push(v);
  return out;
}

/**
 * Daily requests for one log view, with the silence window, the conservative quarantine D*
 * and days on which the log itself recorded nothing (gaps in logging, not silence).
 */
export function trafficChart(t, coverage, asOf) {
  const daily = t.daily_requests || [];
  if (!daily.length || !t.window_start) return null;
  const W = 820, H = 230, L = 46, R = 14, T = 30, B = 34;
  const d0 = midnight(t.window_start);
  const at = (iso) => (new Date(iso).getTime() - d0) / DAY;
  const last = t.last_seen ? at(t.last_seen) : null;
  const now = asOf ? at(asOf) : daily.length;
  const qEnd = last !== null && t.quarantine_days_conservative ? last + t.quarantine_days_conservative : null;
  const span = Math.max(daily.length, Math.ceil(now), qEnd ? Math.min(Math.ceil(qEnd) + 1, daily.length * 3) : 0);
  const x = (d) => L + (d / span) * (W - L - R);
  const max = Math.max(1, ...daily);
  const tk = ticks(max);
  const top = tk[tk.length - 1] || max;
  const y = (v) => T + (1 - v / top) * (H - T - B);
  const bw = Math.max(1, (W - L - R) / span - 1.5);

  const parts = [];
  // gaps in the log itself
  if (coverage && coverage.length) {
    coverage.forEach((n, i) => { if (n === 0) parts.push(`<rect class="gap" x="${x(i)}" y="${T}" width="${x(i + 1) - x(i)}" height="${H - T - B}"><title>No log lines at all on this day: a gap in logging, not silence</title></rect>`); });
  }
  // silence window and quarantine
  if (last !== null && now > last) parts.push(`<rect class="silence" x="${x(last)}" y="${T}" width="${Math.max(0, x(Math.min(now, span)) - x(last))}" height="${H - T - B}"/>`);
  if (qEnd !== null) {
    const qe = Math.min(qEnd, span);
    parts.push(`<rect class="q" x="${x(last)}" y="${T}" width="${Math.max(1, x(qe) - x(last))}" height="${H - T - B}"/>`);
    if (qEnd <= span) parts.push(`<line class="q-edge" x1="${x(qEnd)}" x2="${x(qEnd)}" y1="${T - 4}" y2="${H - B}"/>`);
  }
  // grid + y labels
  tk.forEach((v) => {
    parts.push(`<line class="gridline" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/>`);
    parts.push(`<text x="${L - 6}" y="${y(v) + 3.5}" text-anchor="end">${compact(v)}</text>`);
  });
  // bars
  daily.forEach((v, i) => {
    if (!v) return;
    const label = `${when(new Date(d0 + i * DAY).toISOString(), false)}: ${v.toLocaleString("en-US")} requests`;
    parts.push(`<rect class="bar" x="${x(i) + .75}" y="${y(v)}" width="${bw}" height="${Math.max(1, y(0) - y(v))}"><title>${label}</title></rect>`);
  });
  parts.push(`<line class="axis" x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}"/>`);
  // x labels: weekly
  for (let i = 0; i <= span; i += 7) {
    parts.push(`<text x="${x(i)}" y="${H - B + 15}" text-anchor="middle">${when(new Date(d0 + i * DAY).toISOString(), false).slice(5)}</text>`);
  }
  // markers
  const marks = [];
  if (last !== null) marks.push([x(last), "last request", "last"]);
  if (qEnd !== null && qEnd <= span) marks.push([x(qEnd), `D* ${days(t.quarantine_days_conservative)}`, "q"]);
  if (asOf && now <= span) marks.push([x(now), "as of", "asof"]);
  marks.sort((a, b) => a[0] - b[0]);
  // markers closer than ~70px share one label so the text never overlaps
  const groups = [];
  marks.forEach((m) => {
    const g = groups[groups.length - 1];
    if (g && m[0] - g.x0 < 70) g.items.push(m); else groups.push({ x0: m[0], items: [m] });
  });
  groups.forEach((g, gi) => {
    g.items.forEach(([px, , cls]) => { if (cls !== "q") parts.push(`<line class="${cls}" x1="${px}" x2="${px}" y1="${T - 4}" y2="${H - B}"/>`); });
    const cx = Math.min(W - R - 60, Math.max(L + 40, g.items.reduce((s, m) => s + m[0], 0) / g.items.length));
    parts.push(`<text class="lbl" x="${cx}" y="${T - 10 - (gi % 2) * 0}" text-anchor="middle">${g.items.map((m) => m[1]).join(" · ")}</text>`);
  });
  return html`<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Requests per day for ${t.source}">${raw(parts.join(""))}</svg>`;
}

/** Lines per day for a whole log file: shows where logging stopped. */
export function coverageSpark(first, lines) {
  if (!lines || !lines.length) return "";
  const W = 260, H = 34, max = Math.max(1, ...lines), bw = W / lines.length;
  const d0 = Date.parse(first + "T00:00:00Z");
  const bars = lines.map((n, i) => {
    const h = n ? Math.max(1.5, (n / max) * (H - 2)) : 0;
    const label = `${when(new Date(d0 + i * DAY).toISOString(), false)}: ${n.toLocaleString("en-US")} lines${n ? "" : " (no logging)"}`;
    return n ? `<rect class="bar" x="${i * bw}" y="${H - h}" width="${Math.max(1, bw - 1)}" height="${h}"><title>${label}</title></rect>`
      : `<rect class="gap" x="${i * bw}" y="0" width="${Math.max(1, bw - 1)}" height="${H}"><title>${label}</title></rect>`;
  }).join("");
  return html`<svg class="chart" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="log lines per day">${raw(bars)}</svg>`;
}
