"""Pick which real NASA-HTTP (Jul+Aug 1995) traffic stands in for each pilot resource.

Rules, fixed before looking at the outcome:
  event_site        -> /shuttle/countdown/  (the event's live countdown pages)
  event_assets      -> /images/             (shared static images)
  legacy_downloads  -> the two-level path prefix with the MOST requests whose last request
                       is at least 14 days before the end of the log (a once-busy area gone quiet)
The log lines are used unmodified; only the host they are attributed to is a scenario choice.
"""
import collections
import sys
from datetime import datetime, timezone

sys.path.insert(0, __file__.rsplit("/pilot/", 1)[0] + "/backend")
from retiresafe.collectors.access_logs import ParseStats, read_clf  # noqa: E402

log = sys.argv[1]
st = ParseStats()
n = collections.Counter()
last: dict[str, datetime] = {}
end = datetime.min.replace(tzinfo=timezone.utc)
for r in read_clf(log, None, st):
    end = max(end, r.ts)
    parts = r.path.split("/")
    pre = "/".join(parts[:3]) + "/" if len(parts) > 3 else None
    for key in {pre, "/shuttle/countdown/" if r.path.startswith("/shuttle/countdown/") else None,
                "/images/" if r.path.startswith("/images/") else None} - {None}:
        n[key] += 1
        last[key] = max(last.get(key, r.ts), r.ts)
print(f"lines={st.lines} parsed={st.parsed} failed={st.failed} log_end={end.isoformat()}")
for k in ("/shuttle/countdown/", "/images/"):
    print(f"{k:32} n={n[k]:>8} last={last[k].isoformat()} quiet_days={(end - last[k]).total_seconds()/86400:.2f}")
quiet = [(k, c) for k, c in n.items() if (end - last[k]).total_seconds() / 86400 >= 14]
quiet.sort(key=lambda x: -x[1])
print("legacy_downloads candidates (top 5):")
for k, c in quiet[:5]:
    print(f"  {k:40} n={c:>6} last={last[k].isoformat()} quiet_days={(end - last[k]).total_seconds()/86400:.2f}")
