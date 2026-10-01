"""Cross-check the backend against the research test beds on the same real data.

  tb2   engine CLF parser + quarantine maths vs testbeds/results/tb2_summary.json (NASA Jul 1995)
  tb3   engine traffic summaries vs testbeds/results/tb3_summary.json             (NASA Jul 1995)
  tb1   engine drift scanner (live DNS + S3) vs the TB1 per-host results         (Umbrella sample)

Only aggregate numbers are written (validation/results/*.json); no third-party hostnames.

    python validation/cross_check.py tb2 tb3 [tb1 --tb1-raw PATH]
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
import time
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
from retiresafe.analysis.traffic import Policy, quarantine_days, summarise  # noqa: E402
from retiresafe.collectors.access_logs import ParseStats, read_clf  # noqa: E402

OUT = HERE / "results"
from retiresafe.paths import nasa_log  # noqa: E402

NASA_JUL = nasa_log("NASA_access_log_Jul95")


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _pct(qs: list[float], p: float) -> float:          # same percentile rule as the research test bed
    return round(qs[min(len(qs) - 1, int(p / 100 * len(qs)))], 2)


def check_tb2(log: Path) -> dict:
    ref = _load(ROOT / "testbeds/results/tb2_summary.json")
    st = ParseStats()
    counts = collections.Counter()
    tmin = tmax = None
    for r in read_clf(log, None, st):
        counts[r.path] += 1
        tmin = r.ts if tmin is None or r.ts < tmin else tmin
        tmax = r.ts if tmax is None or r.ts > tmax else tmax
    span = (tmax - tmin).total_seconds() / 86400
    qs = sorted(quarantine_days(n / span, 0.01) for n in counts.values())
    got = {"requests_total": st.lines, "parse_failures": st.failed, "distinct_resources": len(counts),
           "observed_span_days": round(span, 2),
           "quarantine_days_for_1pct_miss": {"p50": _pct(qs, 50), "p90": _pct(qs, 90), "p99": _pct(qs, 99),
                                             "max": round(qs[-1], 2), "mean": round(statistics.mean(qs), 2)}}
    want = {k: ref[k] for k in got}
    return {"check": "tb2", "match": got == want, "engine": got, "research": want}


def check_tb3(log: Path) -> dict:
    ref = _load(ROOT / "testbeds/results/tb3_summary.json")
    st = ParseStats()
    rows = collections.defaultdict(list)
    tmin = tmax = None
    for r in read_clf(log, None, st):
        rows[r.path].append(r)
        tmin = r.ts if tmin is None or r.ts < tmin else tmin
        tmax = r.ts if tmax is None or r.ts > tmax else tmax
    win = tmax - timedelta(days=3)
    dead = [p for p, rs in rows.items() if len(rs) >= 30 and sum(r.ts >= win for r in rs) <= 1]
    pol = Policy(internal_domains=["nasa.gov"])
    summ = {p: summarise(p, tmin, tmax, rows[p], tmax, pol) for p in dead}
    with_ext = sum(1 for s in summ.values() if s.external_clients > 0)
    top = sorted(summ.items(), key=lambda kv: -kv[1].external_clients)[:5]
    got = {"resources_looking_dead_in_window": len(dead), "of_those_with_live_external_dependents": with_ext,
           "max_hidden_external_clients_on_one_dead_looking_resource": top[0][1].external_clients if top else 0}
    want = {k: ref[k] for k in got}
    research_top = {o["resource"]: o for o in ref["top_offenders"][:5]}
    per_resource = []
    for path, s in top:
        o = research_top.get(path, {})
        per_resource.append({"resource": path,
                             "engine": {"clients": s.distinct_clients, "networks_24": s.distinct_networks_24,
                                        "external": s.external_clients},
                             "research": {"clients": o.get("distinct_clients_all_time"),
                                          "networks_24": o.get("distinct_/24_networks"),
                                          "external": o.get("distinct_external_clients")}})
    exact = got == want and all(p["engine"] == p["research"] for p in per_resource)
    return {"check": "tb3", "match": exact, "engine": got, "research": want, "top5": per_resource}


MAP = {"no_cname": "no_cname", "cname_resolves": "cname_resolves",
       "provider_needs_http_fingerprint": "provider_needs_http_check",
       "stale_cname_target_missing": "stale_target_missing", "reclaimable_candidate": "reclaimable_candidate",
       "dangling_unregistered_domain": "dangling_unregistered_domain"}


def check_tb1(raw: Path) -> dict:
    from retiresafe.probes import live
    rows = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines()]
    # every name that had a CNAME in TB1 (where all non-trivial classes live)
    sample = [r for r in rows if r["chain"]]
    t0 = time.time()
    found = {f.hostname: f.classification for f in live.scan([r["fqdn"] for r in sample])}
    conf = collections.Counter()
    for r in sample:
        conf[(MAP[r["class"]], found.get(r["fqdn"].lower(), "missing"))] += 1
    agree = sum(v for (a, b), v in conf.items() if a == b)
    flagged = {"reclaimable_candidate", "dangling_unregistered_domain"}
    tb1_flag = sum(v for (a, _), v in conf.items() if a in flagged)
    both_flag = sum(v for (a, b), v in conf.items() if a in flagged and b in flagged)
    return {"check": "tb1", "names": len(sample), "seconds": round(time.time() - t0),
            "agreement": round(agree / len(sample), 4),
            "tb1_reclaimable": tb1_flag, "engine_also_reclaimable": both_flag,
            "engine_reclaimable_total": sum(v for (_, b), v in conf.items() if b in flagged),
            "confusion": {f"{a} -> {b}": v for (a, b), v in sorted(conf.items())},
            "note": "TB1 ran earlier the same day; live DNS can change between runs, so disagreement on a "
                    "handful of names is expected and reported, not hidden."}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("checks", nargs="+", choices=["tb1", "tb2", "tb3"])
    ap.add_argument("--log", default=str(NASA_JUL))
    ap.add_argument("--tb1-raw", default=str(ROOT / "testbeds/results/tb1_raw.private.jsonl"))
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    for c in a.checks:
        res = {"tb2": lambda: check_tb2(Path(a.log)), "tb3": lambda: check_tb3(Path(a.log)),
               "tb1": lambda: check_tb1(Path(a.tb1_raw))}[c]()
        (OUT / f"{c}.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in res.items() if k not in ("confusion",)}, indent=1))


if __name__ == "__main__":
    main()
