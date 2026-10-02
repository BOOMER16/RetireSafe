// Thin client for the RetireSafe REST API (same origin). The API key, when the server requires one,
// is kept in sessionStorage only, so it disappears when the tab closes.

const KEY = "retiresafe.apiKey";

function apiKey() {
  try { return sessionStorage.getItem(KEY) || ""; } catch { return ""; }
}
export function setApiKey(k) {
  try { k ? sessionStorage.setItem(KEY, k) : sessionStorage.removeItem(KEY); } catch { /* storage disabled */ }
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`);
    this.status = status;
  }
}

function headers(extra = {}) {
  const h = { ...extra };
  const k = apiKey();
  if (k) h["X-API-Key"] = k;
  return h;
}

async function detail(res) {
  try {
    const j = await res.json();
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail)) return j.detail.map((d) => `${(d.loc || []).join(".")}: ${d.msg}`).join("; ");
    return JSON.stringify(j);
  } catch { return res.statusText; }
}

async function call(method, path, body, accept = "json") {
  const opts = { method, headers: headers(body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : {}) };
  if (body) opts.body = body instanceof FormData ? body : JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) throw new ApiError(res.status, await detail(res));
  return accept === "text" ? res.text() : res.json();
}

const cache = new Map();

export const api = {
  health: () => call("GET", "/healthz"),
  knowledge: async () => {
    if (!cache.has("k")) cache.set("k", call("GET", "/v1/knowledge").catch((e) => { cache.delete("k"); throw e; }));
    return cache.get("k");
  },
  list: (limit = 100) => call("GET", `/v1/assessments?limit=${limit}`),
  get: async (id) => {
    if (!cache.has(id)) cache.set(id, call("GET", `/v1/assessments/${encodeURIComponent(id)}`).catch((e) => { cache.delete(id); throw e; }));
    return cache.get(id);
  },
  report: (id) => call("GET", `/v1/assessments/${encodeURIComponent(id)}/report.md`, null, "text"),
  remove: (id) => { cache.delete(id); return call("DELETE", `/v1/assessments/${encodeURIComponent(id)}`); },
  scan: (hostnames) => call("POST", "/v1/drift-scans", { hostnames }),

  // XHR rather than fetch so large access logs show upload progress.
  createAssessment(form, onProgress) {
    return new Promise((resolve, reject) => {
      const x = new XMLHttpRequest();
      x.open("POST", "/v1/assessments");
      const k = apiKey();
      if (k) x.setRequestHeader("X-API-Key", k);
      x.upload.onprogress = (e) => e.lengthComputable && onProgress && onProgress(e.loaded / e.total);
      x.upload.onload = () => onProgress && onProgress(1);
      x.onload = () => {
        let j = null;
        try { j = JSON.parse(x.responseText); } catch { /* not JSON */ }
        if (x.status >= 200 && x.status < 300 && j) { cache.set(j.assessment_id, Promise.resolve(j)); resolve(j); }
        else reject(new ApiError(x.status, j && typeof j.detail === "string" ? j.detail : x.statusText));
      };
      x.onerror = () => reject(new ApiError(0, "network error"));
      x.send(form);
    });
  },
};
