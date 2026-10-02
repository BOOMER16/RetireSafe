"""Consumer-evidence statistics for a retiring resource.

Model: requests to a resource form a Poisson process with rate lambda per day.

* MLE rate                 lambda_hat = n / T
* Jeffreys posterior       lambda | n ~ Gamma(n + 1/2, rate = T)
* conservative rate        lambda_lo = beta-quantile of that posterior
* quarantine (miss rate a) D* = -ln(a) / lambda      (MLE and conservative versions)

The conservative quarantine uses lambda_lo because a smaller rate means a longer
silence is needed before "no consumers" can be believed. Window and freshness
rules turn short or stale evidence into UNKNOWN instead of a false all-clear.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
import math
from dataclasses import dataclass, field
from datetime import datetime

from scipy.stats import gamma

from ..collectors.access_logs import Request
from ..models import TrafficSummary


@dataclass
class Policy:
    alpha: float = 0.01               # tolerated probability of missing a live consumer
    beta: float = 0.05                # one-sided credible level for the rate bound
    min_window_days: float = 31.0     # logs must cover at least one month of client periods
    max_staleness_days: float = 2.0   # logs must end within this many days of as_of
    horizon_days: float = 90.0        # horizon for "a consumer returns" probability in risk scores
    mode: str = "strict"              # strict: never release a reclaimable name; balanced: release on evidence
    enforcement: str = "enforce"      # enforce: failing gate exits 2; advisory: report only (for rollout)
    max_waiver_days: int = 90         # waivers may not run longer than this
    internal_domains: list[str] = field(default_factory=list)
    internal_cidrs: list[str] = field(default_factory=list)
    org_account_ids: list[str] = field(default_factory=list)


def rate_bounds(n: int, t_days: float, beta: float) -> tuple[float | None, float, float]:
    """(mle, lower, upper) daily rate. Lower/upper are beta and 1-beta Jeffreys quantiles."""
    if t_days <= 0:
        return None, 0.0, math.inf
    mle = n / t_days
    lo = float(gamma.ppf(beta, n + 0.5, scale=1.0 / t_days))
    hi = float(gamma.ppf(1 - beta, n + 0.5, scale=1.0 / t_days))
    return mle, lo, hi


def quarantine_days(rate: float | None, alpha: float) -> float | None:
    if rate is None or rate <= 0:
        return None
    return -math.log(alpha) / rate


_KEY = secrets.token_bytes(32)


def _pseudo(value: str) -> bytes:
    return hmac.new(_KEY, value.encode("utf-8", "replace"), hashlib.sha256).digest()


def network_of(client: str) -> str:
    """/24 for IPv4, /48 for IPv6, the hostname itself otherwise (matches research test bed TB3)."""
    try:
        ip = ipaddress.ip_address(client)
    except ValueError:
        return client.lower()
    return str(ipaddress.ip_network(f"{client}/{24 if ip.version == 4 else 48}", strict=False))


def is_internal(client: str, policy: Policy) -> bool:
    c = client.lower()
    if any(c == d.lower() or c.endswith("." + d.lower().lstrip(".")) for d in policy.internal_domains):
        return True
    try:
        ip = ipaddress.ip_address(c)
    except ValueError:
        return False
    return any(ip in ipaddress.ip_network(n, strict=False) for n in policy.internal_cidrs)


def summarise(source: str, window_start: datetime | None, window_end: datetime | None,
              rows: list[Request], as_of: datetime, policy: Policy) -> TrafficSummary:
    t_days = ((window_end - window_start).total_seconds() / 86400.0) if window_start and window_end else 0.0
    n = len(rows)
    mle, lo, _hi = rate_bounds(n, t_days, policy.beta)
    last = max((r.ts for r in rows), default=None)
    silence = (as_of - last).total_seconds() / 86400.0 if last else None
    # Pseudonymise as early as possible: only keyed hashes of client identifiers are kept, with a key
    # that exists for this process only. Internal/external and /24 network are derived first.
    raw = {r.client for r in rows}
    clients = {_pseudo(c) for c in raw}
    ext = {_pseudo(c) for c in raw if not is_internal(c, policy)}
    networks = {_pseudo(network_of(c)) for c in raw}
    del raw
    daily: list[int] = []
    if window_start and window_end:
        day0 = window_start.date()
        daily = [0] * ((window_end.date() - day0).days + 1)
        for r in rows:
            i = (r.ts.date() - day0).days
            if 0 <= i < len(daily):
                daily[i] += 1
    fresh = bool(window_end) and (as_of - window_end).total_seconds() / 86400.0 <= policy.max_staleness_days
    return TrafficSummary(
        source=source,
        window_start=window_start.isoformat() if window_start else None,
        window_end=window_end.isoformat() if window_end else None,
        window_days=round(t_days, 4), requests=n,
        last_seen=last.isoformat() if last else None,
        silence_days=round(silence, 4) if silence is not None else None,
        rate_mle_per_day=mle, rate_lower_per_day=lo if n else 0.0,
        quarantine_days_mle=quarantine_days(mle, policy.alpha),
        quarantine_days_conservative=quarantine_days(lo, policy.alpha),
        distinct_clients=len(clients), distinct_networks_24=len(networks),
        external_clients=len(ext), external_share=(len(ext) / len(clients)) if clients else None,
        fresh=fresh, window_sufficient=t_days >= policy.min_window_days, daily_requests=daily)
