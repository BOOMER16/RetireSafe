"""TB2 - "Is this endpoint really dead?" Runtime-traffic survival model.

Real data : NASA-HTTP July 1995 access log (1.89M requests, Internet Traffic Archive).
Question   : the brief's core uncertainty - "Observe runtime traffic and retain
             uncertainty about offline or infrequent clients." When a platform
             engineer sees an endpoint with no hits for D days, how confident can
             they be that NO consumer still depends on it?

Model      : treat each resource's requests as a homogeneous Poisson process with
             rate lambda (req/day) estimated from its observed history. Under that
             model the chance of seeing zero requests across a silent window of
             length D is exp(-lambda*D). We INVERT it: for each resource, how long a
             silent window would we need before P(miss) <= alpha? That window is the
             evidence-based quarantine the retirement workflow should enforce.
             Rare/bursty resources need a far longer silence than the mean.

Validation : hold out the LAST 7 days; estimate lambda on the first 24; measure how
             many "idle in the holdout" resources actually got traffic later, and
             compare the empirical miss-rate to the Poisson prediction. This tells us
             whether a simple rate model is safe enough or over-confident (it is, for
             bursty tails -> motivates the empirically-calibrated quarantine).
"""
import collections
import datetime as dt
import math
import os
import re

from common import DATA, OUT, save

LOG = os.environ.get("RS_LOG", os.path.join(DATA, "nasa-http", "NASA_access_log_Jul95"))
LINE = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "(?:(\S+) (\S+?)(?: \S+)?)?" (\d{3}|-) (\d+|-)')
EPOCH = None


def parse(path):
    global EPOCH
    hits = collections.defaultdict(list)       # resource -> [day_float]
    status_ok = collections.defaultdict(int)
    total = bad = 0
    for ln in open(path, "rb"):
        total += 1
        m = LINE.match(ln.decode("latin-1"))
        if not m:
            bad += 1
            continue
        host, ts, meth, url, status, size = m.groups()
        try:
            t = dt.datetime.strptime(ts[:20], "%d/%b/%Y:%H:%M:%S")
        except ValueError:
            bad += 1
            continue
        if EPOCH is None:
            EPOCH = t
        day = (t - EPOCH).total_seconds() / 86400.0
        res = url.split("?")[0] if url else "-"
        hits[res].append(day)
        if status and status.startswith("2"):
            status_ok[res] += 1
    return hits, status_ok, total, bad


def main():
    hits, ok, total, bad = parse(LOG)
    span = max(max(v) for v in hits.values())
    n_res = len(hits)
    # ---- quarantine window per resource (alpha = 1% miss tolerance) ----
    alpha = 0.01
    windows = []
    for res, days in hits.items():
        n = len(days)
        lam = n / span  # req/day MLE over observed span
        if lam <= 0:
            continue
        # D such that exp(-lam*D) <= alpha  ->  D >= -ln(alpha)/lam
        windows.append((res, n, lam, -math.log(alpha) / lam))
    windows.sort(key=lambda x: x[3])
    # mean-rate naive view vs tail
    import statistics
    qs = sorted(w[3] for w in windows)

    def pct(p):
        return round(qs[min(len(qs) - 1, int(p / 100 * len(qs)))], 2)

    # ---- hold-out validation: train 0-24d, test 24-end ----
    T = 24.0
    trained = {r: [d for d in ds if d < T] for r, ds in hits.items()}
    predicted_miss = empirical = tested = 0
    # resources with >=1 hit in training, SILENT in a 3-day pre-holdout window
    probe_lo, probe_hi = T - 3, T
    cohort = []
    for r, ds in hits.items():
        tr = [d for d in ds if d < T]
        if not tr:
            continue
        silent = not any(probe_lo <= d < probe_hi for d in tr)  # looked idle for 3d at cutoff
        if not silent:
            continue
        lam = len(tr) / T
        future = any(d >= T for d in ds)            # did traffic actually return?
        p_future = 1 - math.exp(-lam * (span - T))  # model's predicted P(return)
        cohort.append((r, lam, future, p_future))
    tested = len(cohort)
    empirical = sum(1 for _, _, f, _ in cohort if f)          # really came back
    predicted = sum(p for _, _, _, p in cohort)               # expected count back
    # decile reliability of the probability model
    cohort.sort(key=lambda x: x[3])
    rel = []
    B = 10
    for b in range(B):
        lo, hi = b * len(cohort) // B, (b + 1) * len(cohort) // B
        chunk = cohort[lo:hi]
        if chunk:
            rel.append({"bin": b, "n": len(chunk),
                        "pred": round(sum(c[3] for c in chunk) / len(chunk), 3),
                        "obs": round(sum(1 for c in chunk if c[2]) / len(chunk), 3)})

    summ = {
        "dataset": "NASA-HTTP Jul 1995 (Internet Traffic Archive)",
        "requests_total": total, "parse_failures": bad,
        "distinct_resources": n_res, "observed_span_days": round(span, 2),
        "quarantine_days_for_1pct_miss": {
            "p50": pct(50), "p90": pct(90), "p99": pct(99),
            "max": round(qs[-1], 2), "mean": round(statistics.mean(qs), 2)},
        "interpretation": (
            "A single mean-rate rule is unsafe: half of resources need <= "
            f"{pct(50)}d of silence to be 99% sure they are dead, but the long "
            f"tail needs up to {round(qs[-1],1)}d. Retirement must quarantine "
            "per-resource, not globally."),
        "holdout_validation": {
            "train_days": T, "idle_cohort_size": tested,
            "actually_returned": empirical,
            "poisson_expected_return": round(predicted, 1),
            "predicted_over_observed_ratio": round(predicted / max(1, empirical), 3),
            "note": (
                "Poisson UNDER-predicts returns: unsafe as a deletion gate"
                if empirical > 1.1 * predicted else
                "Poisson OVER-predicts returns (conservative, mis-calibrated): "
                "good for ranking, recalibrate before using as a probability"
                if predicted > 1.1 * empirical else
                "Poisson tracks empirical returns within 10%"),
            "reliability_deciles": rel},
    }
    save("tb2_summary.json", summ)
    # top risky (rare-but-real) resources that still returned a 2xx
    risky = [{"resource": r, "req": n, "rate_per_day": round(lam, 3),
              "quarantine_days": round(d, 1), "ok_2xx": ok.get(r, 0)}
             for r, n, lam, d in windows if ok.get(r, 0) > 0][-25:]
    save("tb2_longtail.json", risky)
    import json
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
