# 02 · Test beds (run on real data)

Three test beds were built and run during the research phase. Each one answers a question the product has to answer. All of them use **real public data**; nothing was fabricated or simulated. All network activity was **read-only**.

| | Question | Data | Script | Output |
|---|---|---|---|---|
| TB1 | How common are reclaimable surviving references on the live internet? | Cisco Umbrella top-1M, can-i-take-over-xyz, live DNS, S3 API | `testbeds/tb1_dns_cname.py` | `results/tb1_summary.json` |
| TB2 | How long must an endpoint be silent before we can believe it is dead? | NASA-HTTP Jul 1995 (1.89M requests) | `testbeds/tb2_traffic_survival.py` | `results/tb2_summary.json`, `results/tb2_longtail.json` |
| TB3 | How much hidden dependence sits behind a resource that looks idle? | NASA-HTTP Jul 1995 | `testbeds/tb3_blast_radius.py` | `results/tb3_summary.json` |

---

## TB1 · Base rate of surviving, reclaimable references

### Question
Among real, actively resolved hostnames, how many have a DNS reference that survives to a cloud resource another party could claim? This sets the **base rate** the product works against, and it validates the scanner pipeline end to end on real infrastructure.

### Data
* **Cisco Umbrella top-1M** (2026-10-01 copy). These are FQDNs ranked by real DNS-resolver query volume. Unlike domain-only lists, it includes subdomains, which is where CNAMEs live.
* **Sample:** the top 8,000 names plus 8,000 drawn uniformly at random from ranks 8,001 to 1,000,000 (`random.Random(42)`). Total 16,000.
* **can-i-take-over-xyz** `fingerprints.json`: 76 services, of which 36 are marked vulnerable, 26 not vulnerable and 14 edge cases. For each it gives the CNAME suffixes, whether the takeover signal is NXDOMAIN or an HTTP body, and the vulnerability status.

### Method (per hostname)
1. Walk the **CNAME chain** with dnspython (system resolver, up to 8 hops, 3 s timeout per query).
2. Match each hop against the fingerprint CNAME suffixes (longest suffix first), plus a regex for S3 REST and website endpoints.
3. Resolve the **final target** (A, then AAAA). If it is NXDOMAIN, look up NS on the registrable domain (public-suffix aware via tldextract) to see whether the *whole domain* is unregistered.
4. **S3 probe:** derive the bucket name (from the `bucket.s3…amazonaws.com` label, or the hostname itself for website endpoints) and send `GET https://s3.amazonaws.com/<bucket>`. `404 NoSuchBucket` means the bucket does not exist and is reclaimable in the global namespace. `403` or `301` means it exists.
5. Classify onto the evidence ladder:

| Class | Rule |
|---|---|
| `no_cname` | No CNAME; out of scope for this test |
| `cname_resolves` | Chain resolves normally |
| `provider_needs_http_fingerprint` | Matches a vulnerable provider whose signal is in the HTTP body. **Not verifiable here** because the egress proxy blocks arbitrary hosts |
| `stale_cname_target_missing` | Final target is NXDOMAIN but no vulnerable fingerprint matched |
| `reclaimable_candidate` | S3 `NoSuchBucket`, **or** an NXDOMAIN-type vulnerable fingerprint (for example Azure or Elastic Beanstalk) with an NXDOMAIN target |
| `dangling_unregistered_domain` | The target's registrable domain itself returns NXDOMAIN |

### Results (16,000 names, 407 s)

| Class | Top 8k | Random 8k | Total |
|---|---:|---:|---:|
| no CNAME | 6,061 | 6,421 | 12,482 |
| CNAME resolves | 1,934 | 1,570 | 3,504 |
| provider match, needs HTTP check | 1 | 3 | 4 |
| stale, target NXDOMAIN | 3 | 2 | 5 |
| **reclaimable candidate** | **1** (Azure) | **4** (all S3 `NoSuchBucket`) | **5** |
| dangling to unregistered domain | 0 | 0 | 0 |

Provider hits along CNAME chains: Azure 82 / 42, AWS ELB 40 / 64, S3 1 / 7, Elastic Beanstalk 1 / 3 (top / random).
S3 probes: top 1 exists (301); random 3 exist (301) and 4 return `NoSuchBucket`.

**Rates with Wilson 95% confidence intervals**

| Population | Reclaimable | Rate | 95% CI |
|---|---:|---:|---|
| All 16,000 | 5 | 0.031% | 0.013% – 0.073% |
| Top 8k | 1 | 0.013% | 0.002% – 0.071% |
| Random 8k | 4 | 0.050% | 0.019% – 0.129% |
| Top, CNAME'd only (1,939) | 1 | 0.052% | 0.009% – 0.292% |
| Random, CNAME'd only (1,579) | 4 | 0.253% | 0.099% – 0.650% |

### Interpretation
* The dangerous cases are **rare and buried**: about 3 in 10,000 live names. Nobody finds those by hand, which is the argument for an automated scanner.
* The **long tail is worse than the head**. Among names that have a CNAME, the random-tail rate (0.25%) is about 5× the top-8k rate. The intervals overlap, so this is suggestive rather than conclusive. Popular properties get more operational attention, and less-visible subdomains are where retirement goes wrong. That matches the "temporary event site" pattern in the brief.
* Every S3 candidate was a CNAME to a bucket that no longer exists. Under the legacy global namespace, anyone could create that bucket. This is exactly the case account-regional namespaces [8] were introduced to stop.
* The pipeline (CNAME walk → fingerprint → live probe → ladder) worked end to end on real infrastructure. That is the core of RetireSafe's *Probe* stage.

### Limitations
* This is a sample of 16,000, not a census. It establishes order of magnitude.
* HTTP-body fingerprints could not be checked because the sandbox egress policy blocks arbitrary hosts. Those 4 names are left as "needs HTTP check" and are not counted as reclaimable.
* An NXDOMAIN Azure target is a *candidate*: Azure may hold some names, and we did not attempt to claim it.
* DNS timeouts and SERVFAIL are treated as not dangling, so the count is a conservative undercount.
* Running it again on another day will give different numbers, because this is live infrastructure.
* Per-hostname results are deliberately **not published** (see [06](06_ethics_and_limitations.md)).

---

## TB2 · "Is this endpoint really dead?" (traffic-survival model)

### Question
The brief says to *"observe runtime traffic and retain uncertainty about offline or infrequent clients."* When an endpoint has had no hits for D days, how confident can an engineer be that no consumer still depends on it? And is a simple statistical model trustworthy enough to gate a deletion?

### Data
**NASA-HTTP, July 1995** (Internet Traffic Archive, via the `greymd/NASA-HTTP` mirror):
* 1,891,715 log lines, of which 1,958 could not be parsed
* **7,133 distinct resources** (URL paths with query strings removed)
* a 27.56-day span
* 2,387 resources (33%) were requested exactly once, and 4,104 (58%) five times or fewer

It is a large, real, openly available access log from a public site with an external audience. The month includes the STS-70 shuttle mission, so traffic rises and falls around an event, much like the event-site scenario in the brief.

### Method
1. **Per-resource rate.** Model each resource as a homogeneous Poisson process. The maximum-likelihood rate is λ̂ = n / T.
2. **Quarantine window.** If a resource is still live, the probability of seeing zero hits over D days is e^(−λD). Setting that equal to the miss tolerance α = 1% gives **D\* = −ln(α) / λ̂ = 4.605 / λ̂**.
3. **Hold-out calibration.** Estimate λ̂ on days 0–24. The *idle cohort* is every resource seen during training but silent during days 21–24, i.e. one that looks dead at the cutoff. The model predicts P(return in days 24–27.6) = 1 − e^(−λ̂·3.56). Compare that with what actually happened, overall and by decile.

### Results

**Silence needed for 99% confidence that a resource is dead (D\*)**

| p50 | p90 | p99 | max | mean |
|---:|---:|---:|---:|---:|
| 42.3 d | 126.9 d | 126.9 d | 126.9 d | 56.5 d |

The p90, p99 and max are all 126.9 d because 33% of resources were seen only once (λ̂ = 1/T gives D\* = 4.605 × 27.56). See the limitations below.

**Hold-out**

| Idle cohort | Actually returned | Poisson predicted | Predicted ÷ observed |
|---:|---:|---:|---:|
| 3,973 | **783** (19.7%) | **1,161.4** (29.2%) | **1.48** |

Reliability by decile of predicted probability, predicted → observed: 0.14 → 0.055, 0.14 → 0.098, 0.14 → 0.058, 0.14 → 0.060, 0.14 → 0.038, 0.23 → 0.14, 0.26 → 0.13, 0.38 → 0.30, 0.53 → 0.39, **0.83 → 0.71**. The observed rate generally rises with the predicted one, but every decile falls below the predicted value.

### Interpretation
1. **One global idle timeout is unsafe.** Half the resources need at least 42 days of silence and a third need at least 127 days, while the log only covers 27.6 days. A rule like "delete after 30 idle days" would be over-confident for most of the catalogue.
2. **The Poisson model ranks well but is mis-calibrated.** It over-predicts returns by 48%, because real traffic is bursty and decays after events rather than being memoryless. For deletion that error is in the safe direction, since it keeps too much. Still, a probability like "29% chance it returns" cannot be shown to an engineer as-is.
3. **Design consequence:** use the model to *rank and prioritize*. Gate deletion on a **per-resource quarantine taken from the upper confidence bound of the rate**, recalibrated on the organization's own history (isotonic regression, scored with Brier/ECE). See [04](04_mathematics.md).

### Limitations
* **The observation window caps what can be known.** A resource seen once in 27.6 days could be a monthly or yearly job. No log shorter than a client's period can rule that client out. The engine should report this as **unknown** ("window shorter than plausible client period"), not as a long quarantine.
* The log is from 1995. The *method* does not depend on the dataset, and the hackathon demo will run it on the team's own logs.
* The idle-cohort definition (silent 3 days before the cutoff) is one reasonable choice. Other windows would shift the absolute numbers.

---

## TB3 · The coordination gap, measured

### Question
The brief says *"A resource can appear unused to the team deleting it while remaining trusted elsewhere."* How big is that gap in real traffic?

### Data
NASA-HTTP, July 1995 (as in TB2).

### Method
1. Use a **3-day recency window** at the end of the log. That is roughly what an activity dashboard shows the engineer who is about to delete something.
2. **Looks dead** means at least 30 requests over the full history and at most 1 request in the window.
3. For each such resource, measure the **blast radius** over the full history: distinct client hosts, distinct /24 networks, and distinct **external** clients (any host not ending in `nasa.gov`).

### Results

| Metric | Value |
|---|---:|
| Resources that look dead in the 3-day window | 108 |
| …with external clients in their history | **108 (100%)** |
| Largest external dependent population on one of them | **15,054** |

Top examples:

| Resource | Total requests | Last 3 days | Distinct clients | External clients |
|---|---:|---:|---:|---:|
| `/shuttle/countdown/count.gif` | 22,216 | 0 | 15,319 | 15,054 |
| `/cgi-bin/imagemap/countdown` | 16,983 | 1 | 8,138 | 7,996 |
| `/shuttle/countdown/video/livevideo.gif` | 10,150 | 0 | 4,358 | 4,221 |
| `/shuttle/countdown/images/cdtclock.gif` | 8,662 | 0 | 2,228 | 2,087 |
| `/shuttle/countdown/video/landing.gif` | 1,365 | 0 | 875 | 847 |

### Interpretation
* The 100% share is **expected** for a public site, since almost every client was external, so on its own it says little. The informative number is the **size**: resources a recency dashboard shows as dead had thousands of distinct third-party consumers who had been using them for weeks. The deleting team cannot see or notify any of them.
* These are mission-countdown assets. Traffic collapsed after the event, which is the brief's event-website lifecycle (create → connect → retire) seen in real data.
* **Design consequence:** RetireSafe joins recency (TB2's quarantine) with **historical breadth** (TB3's blast radius) and the share of external clients. A small, internal-only population can follow a "notify then retire" path. A large external population should lead to **"retain the name"** (keep a placeholder or redirect) instead of releasing it.

### Limitations
* Past clients are not necessarily future clients. TB3 measures exposure, and TB2 answers whether they come back.
* The "external" test is a hostname heuristic. Raw IP clients are counted as external, so some NASA-internal IP traffic may be miscounted.

---

## Test beds designed but not run

| Test bed | Plan | Why it was not run |
|---|---|---|
| **TB4: SPF dangling-include audit** (SubdoMailing class [4]) | For registrable domains in the Umbrella sample, expand `v=spf1` `include:`/`redirect=` chains (RFC 7208, 10-lookup limit) and flag included domains whose registrable domain returns NXDOMAIN, meaning anyone could register it | DNS-over-HTTPS and RDAP hosts were blocked by the sandbox egress policy, some large TXT lookups timed out over UDP, and the session had a fixed research budget. It can run with the existing `common.py` DNS helper using TCP for TXT |
| **TB5: package S3-reference scan** (watchTowr class [6]) | Download sdists of the top PyPI packages (the 2026-10-01 top-15k list was fetched), extract `*.s3.amazonaws.com` and `s3://` references, and probe whether each bucket exists | Budget. PyPI and S3 are both reachable, so this is the quickest one to add |
