"""TB3 - The coordination gap, quantified. "Looks unused here, still trusted there."

Real data: NASA-HTTP Jul 1995 access log.
Idea     : The brief says a resource "can appear unused to the team deleting it while
           remaining trusted elsewhere." We make that measurable. Rank resources by
           how QUIET they are in the final 3 days (what a dashboard would show the
           engineer), then reveal the BLAST RADIUS each still carries: distinct client
           hosts and distinct /24 networks that touched it over the full history, and
           whether those clients are external (non-nasa.gov) - i.e. third parties the
           deleting team cannot see or notify.

Output   : a decision table. The headline: a large share of resources that look dead
           in a recency window still have live external dependents - the precise
           failure mode RetireSafe must block.
"""
import collections
import datetime as dt
import ipaddress
import os
import re

from common import DATA, OUT, save

LOG = os.environ.get("RS_LOG", os.path.join(DATA, "nasa-http", "NASA_access_log_Jul95"))
LINE = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "(?:(\S+) (\S+?)(?: \S+)?)?" (\d{3}|-) (\d+|-)')


def net24(host):
    try:
        ip = ipaddress.ip_address(host)
        return str(ipaddress.ip_network(f"{host}/24", strict=False)) if ip.version == 4 else host
    except ValueError:
        return host  # a DNS name client


def external(host):
    return not host.lower().endswith(("nasa.gov", "ksc.nasa.gov", ".nasa.gov"))


def main():
    EPOCH = None
    last = 0.0
    recent = collections.defaultdict(int)      # hits in final window
    clients = collections.defaultdict(set)
    nets = collections.defaultdict(set)
    ext_clients = collections.defaultdict(set)
    total = collections.Counter()
    rows = []
    for ln in open(LOG, "rb"):
        m = LINE.match(ln.decode("latin-1"))
        if not m:
            continue
        host, ts, meth, url, status, size = m.groups()
        try:
            t = dt.datetime.strptime(ts[:20], "%d/%b/%Y:%H:%M:%S")
        except ValueError:
            continue
        if EPOCH is None:
            EPOCH = t
        day = (t - EPOCH).total_seconds() / 86400.0
        last = max(last, day)
        res = (url.split("?")[0] if url else "-")
        total[res] += 1
        clients[res].add(host)
        nets[res].add(net24(host))
        if external(host):
            ext_clients[res].add(host)
        rows.append((res, day, host))
    win = last - 3.0  # last 3 days = the "is anyone still using it?" dashboard view
    recent = collections.Counter(r for r, d, h in rows if d >= win)

    # resources that look DEAD in the recency window (<=1 hit) but have real history
    looks_dead = [r for r in total if total[r] >= 30 and recent[r] <= 1]
    report = []
    for r in looks_dead:
        report.append({
            "resource": r,
            "total_requests": total[r],
            "recent_3d_requests": recent[r],
            "distinct_clients_all_time": len(clients[r]),
            "distinct_/24_networks": len(nets[r]),
            "distinct_external_clients": len(ext_clients[r]),
        })
    report.sort(key=lambda x: -x["distinct_external_clients"])
    n_dead = len(looks_dead)
    with_ext = sum(1 for x in report if x["distinct_external_clients"] > 0)
    summ = {
        "dataset": "NASA-HTTP Jul 1995",
        "recency_window_days": 3,
        "resources_looking_dead_in_window": n_dead,
        "of_those_with_live_external_dependents": with_ext,
        "share_with_hidden_external_dependents": round(with_ext / max(1, n_dead), 3),
        "max_hidden_external_clients_on_one_dead_looking_resource":
            max((x["distinct_external_clients"] for x in report), default=0),
        "interpretation": (
            f"{with_ext} of {n_dead} resources that a 3-day activity dashboard would "
            "flag as idle still carry traffic from external (non-nasa.gov) clients over "
            "their history. Deleting on the dashboard signal alone would silently break "
            "those third-party dependents - the coordination gap, measured."),
        "top_offenders": report[:20],
    }
    save("tb3_summary.json", summ)
    import json
    print(json.dumps({k: v for k, v in summ.items() if k != "top_offenders"}, indent=1))


if __name__ == "__main__":
    main()
