"""TB1 - Surviving DNS references on real, popular hostnames.

Input  : Cisco Umbrella top-1M FQDN list (real resolver popularity data).
Method : passive DNS (CNAME chain walk) + fingerprint catalogue (can-i-take-over-xyz)
         + S3 existence probe (HTTP GET against the S3 API: 404 NoSuchBucket / 403 / 301).
Output : aggregate counts on the evidence ladder
           stale reference -> reclaimable endpoint (candidate) -> (impact not tested)
         Hostnames are NOT published; raw results stay in a local, git-ignored file.
Ethics : read-only lookups. Nothing is registered, claimed or written.
"""
import csv
import collections
import concurrent.futures as cf
import json
import os
import random
import re
import sys
import time
import requests

from common import DATA, OUT, query, registrable, resolver, save

N_TOP = int(os.environ.get("N_TOP", 10000))
N_RAND = int(os.environ.get("N_RAND", 10000))

fps = json.load(open(os.path.join(DATA, "cito/fingerprints.json")))
SUFFIX = []  # (suffix, fp)
for fp in fps:
    for c in fp["cname"]:
        if re.search(r"[a-z]", c):
            SUFFIX.append((c.lower().strip("."), fp))
SUFFIX.sort(key=lambda x: -len(x[0]))


def match_fp(host):
    host = host.lower().rstrip(".")
    for suf, fp in SUFFIX:
        if host == suf or host.endswith("." + suf):
            return fp
    if re.search(r"(^|\.)s3[.-]([a-z0-9-]+\.)?amazonaws\.com$|s3-website", host):
        return next(f for f in fps if f["service"] == "AWS/S3")
    return None


def s3_bucket(src, target):
    t = target.rstrip(".").lower()
    m = re.match(r"^(.+?)\.s3[.-](website[.-])?([a-z0-9-]+\.)?amazonaws\.com$", t)
    if m:
        return m.group(1)
    return src.rstrip(".").lower()  # website endpoint without bucket label => bucket == hostname


def s3_probe(bucket):
    try:
        r = requests.get(f"https://s3.amazonaws.com/{bucket}", timeout=10, allow_redirects=False)
        if r.status_code == 404 and "NoSuchBucket" in r.text:
            return "NoSuchBucket"
        return f"exists:{r.status_code}"
    except Exception as e:  # noqa
        return "probe_error"


def walk(fqdn):
    res = resolver()
    chain, cur, fp_hit = [], fqdn, None
    for _ in range(8):
        st, ans = query(res, cur, "CNAME")
        if st != "OK" or not ans:
            break
        cur = ans[0].rstrip(".")
        chain.append(cur)
        fp_hit = fp_hit or match_fp(cur)
    rec = {"fqdn": fqdn, "chain": chain, "service": fp_hit["service"] if fp_hit else None}
    if not chain:
        rec["class"] = "no_cname"
        return rec
    st, _ = query(res, chain[-1], "A")
    if st == "NXDOMAIN":
        st6, _ = query(res, chain[-1], "AAAA")
        st = "NXDOMAIN" if st6 == "NXDOMAIN" else st
    rec["target_status"] = st
    if st == "NXDOMAIN":
        reg = registrable(chain[-1])
        rs, _ = query(res, reg, "NS") if reg else ("ERROR", [])
        rec["target_registrable"] = reg
        rec["registrable_status"] = rs
    if fp_hit and fp_hit["service"] == "AWS/S3":
        rec["s3"] = s3_probe(s3_bucket(fqdn if len(chain) == 1 else chain[-2], chain[0]))
    rec["class"] = classify(rec, fp_hit)
    return rec


def classify(rec, fp_hit):
    """Evidence-ladder class. Correction (2026-10-01): an S3 bucket that exists (403/301/200) is a healthy
    reference; the first version fell through to "provider_needs_http_fingerprint" for those."""
    st = rec.get("target_status")
    if not rec["chain"]:
        return "no_cname"
    if rec.get("registrable_status") == "NXDOMAIN":
        return "dangling_unregistered_domain"
    if fp_hit and fp_hit["service"] == "AWS/S3" and rec.get("s3") == "NoSuchBucket":
        return "reclaimable_candidate"
    if fp_hit and fp_hit["service"] == "AWS/S3" and str(rec.get("s3", "")).startswith("exists"):
        return "cname_resolves"
    if fp_hit and st == "NXDOMAIN" and fp_hit["nxdomain"] and fp_hit["vulnerable"]:
        return "reclaimable_candidate"
    if st == "NXDOMAIN":
        return "stale_cname_target_missing"
    if fp_hit and fp_hit["vulnerable"] and not fp_hit["nxdomain"]:
        return "provider_needs_http_fingerprint"
    return "cname_resolves"


def main():
    raw_path = os.path.join(OUT, "tb1_raw.private.jsonl")
    t0 = time.time()
    if "--from-raw" in sys.argv:
        # re-derive the summary from stored per-host results (no new network queries)
        by_service = {fp["service"]: fp for fp in fps}
        out = [json.loads(line) for line in open(raw_path)]
        for r in out:
            r["class"] = classify(r, by_service.get(r.get("service")))
        seconds = None
    else:
        rows = list(csv.reader(open(os.path.join(DATA, "top-1m.csv"))))
        names = [r[1] for r in rows]
        rng = random.Random(42)
        sample = names[:N_TOP] + rng.sample(names[N_TOP:], N_RAND)
        out = []
        with cf.ThreadPoolExecutor(128) as ex:
            for i, rec in enumerate(ex.map(walk, sample)):
                rec["stratum"] = "top" if i < N_TOP else "random"
                out.append(rec)
        with open(raw_path, "w") as f:
            for r in out:
                f.write(json.dumps(r) + "\n")
        seconds = round(time.time() - t0)
    agg = {"n": len(out), "seconds": seconds, "by_stratum": {},
           "classification_rule": "2026-10-01 corrected: existing S3 buckets count as cname_resolves"}
    for s in ("top", "random"):
        sub = [r for r in out if r["stratum"] == s]
        agg["by_stratum"][s] = {
            "n": len(sub),
            "class": collections.Counter(r["class"] for r in sub),
            "provider_hits": collections.Counter(r["service"] for r in sub if r["service"]),
            "reclaimable_by_service": collections.Counter(
                r["service"] for r in sub if r["class"] == "reclaimable_candidate"),
            "s3_probe": collections.Counter(r.get("s3") for r in sub if r.get("s3")),
            "cname_chain_len": collections.Counter(len(r["chain"]) for r in sub),
        }
    save("tb1_summary.json", agg)
    print(json.dumps(agg, indent=1, default=str))


if __name__ == "__main__":
    main()
