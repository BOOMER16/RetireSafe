# 03 · Proposed architecture

> Status: **pilot backend built** ([`backend/`](../backend/README.md)). Collect, Probe, Observe, Decide and Act are implemented for S3, Elastic Beanstalk and Azure App Service; Fuse is the in-memory reference graph. Neo4j, tree-sitter parsing and the UI from the original design are not built; regex scanning and FastAPI/SQLite are used instead. SPF and continuous scheduling remain roadmap items.

## 3.1 What RetireSafe is

A **retirement pre-flight check**. Its input is a *proposed* deletion or migration. Its output is a decision with evidence:

* **CLEARED**: at least one takeover condition is provably false for every surviving reference. An evidence record is attached.
* **BLOCKED**: a named reference meets every condition the engine could evaluate. It comes with the precise reason and a migration patch.
* **RETAIN NAME**: consumers are still present, so keep a placeholder or redirect instead of releasing the name.
* **UNKNOWN**: one or more conditions could not be evaluated. The output says what evidence is missing and how to get it.

It never returns an unqualified "safe".

## 3.2 Pipeline

```
              ┌──────────────────────── inputs ────────────────────────┐
              │ terraform plan JSON · DNS zone export · git repo(s)      │
              │ access/CDN logs · SPF/TXT · provider account metadata    │
              └──────────────────────────────┬──────────────────────────┘
                                             ▼
 ① COLLECT   reference scanners ─────► candidate references to the target
                │  dns:   CNAME/ALIAS/A records whose chain reaches the resource
                │  code:  regex + AST for bucket URLs, s3://, *.azurewebsites.net, SRI
                │  iac:   resource graph from plan JSON (who references what)
                │  spf:   include:/redirect= chains (RFC 7208 lookup limit)
                ▼
 ② PROBE     reclaimability prober ──► per reference: reclaimable? protected?
                │  fingerprint catalogue (can-i-take-over-xyz)            ← TB1
                │  live existence probe (S3 NoSuchBucket, NXDOMAIN, …)    ← TB1
                │  protection detectors: account-regional S3, ExpectedBucketOwner,
                │  Azure domain verification, GitHub Pages verification, prevent_destroy
                ▼
 ③ OBSERVE   traffic analyser ───────► per resource: λ, quarantine D*, blast radius,
                │                         external share, "window too short" flag
                │                                                         ← TB2, TB3
                ▼
 ④ FUSE      evidence graph ─────────► Resource ─ Name ─ Reference ─ Consumer
                │                         every edge carries its evidence + confidence
                ▼
 ⑤ DECIDE    decision engine ────────► five-condition verdicts + risk score R (with interval)
                ▼
 ⑥ ACT       outputs ────────────────► blocked plan + reason · migration patch ·
                                          retain-name recommendation · evidence record
```

## 3.3 Data model (evidence graph)

```text
Resource  { id, provider, type, name, namespace: global|account-regional, owner_account,
            planned_action: delete|migrate, protections[] }
Name      { fqdn | bucket | url, reclaimable: true|false|unknown, probe_evidence }
Reference { kind: dns|code|iac|spf|config, location (file:line / record), points_to: Name,
            survives_deletion: bool }
Consumer  { kind: browser|software|mail|internal-service, seen_in: log-source,
            clients, networks_24, external_share, last_seen, lambda, D_star }
Protection{ kind, applies_to: condition#, configured: bool, evidence }
Evidence  { source, collected_at, scope, method, result, confidence }
```

The engine reasons over paths of the form **Resource → Name → Reference → Consumer**. Each path is checked against the five conditions.

## 3.4 Decision engine

For each path *p*:

| Condition | Evaluated from | Values |
|---|---|---|
| C1 released | planned action and namespace | true / false |
| C2 reassignable | probe + provider rules + protections | true / false / unknown |
| C3 reference survives | the reference is not removed by the same change | true / false |
| C4 consumer remains | traffic: silence < D\*, or window < plausible period | true / false / unknown |
| C5 controls permit | consumer-side checks (owner condition, SRI, signatures) | true / false / unknown |

* **Any false** → that path is cleared, and the evidence record names the condition that broke the chain.
* **All true** → **BLOCKED**, with a patch that makes one of them false. Removing the reference (C3) is cheapest; retaining the name (C1) is safest.
* **Any unknown, none false** → **UNKNOWN**, with a statement of what would resolve it.
* The risk score R (see [04](04_mathematics.md)) orders blocked and unknown paths for triage.

## 3.5 Outputs

1. **Blocked deletion with a precise reason** (for example as a failing CI check):
   ```
   BLOCKED  aws_s3_bucket.event_assets  (legacy global namespace → reclaimable)
     ← dns  assets.event.example.com CNAME event-assets.s3.amazonaws.com   [zone.txt:42]
     ← code static/js/app.js:118 "https://event-assets.s3.amazonaws.com/lib.js"
     consumers: 1,204 clients / 1,150 /24s in 30 d, 97% external, last seen 2 d ago
     D* (99%) = 63 d   →  release not before 2026-12-03, or migrate
   ```
2. **Migration patch**: delete or rewrite the CNAME, update code URLs to the new location, add `ExpectedBucketOwner`, remove the stale SPF `include:`, or add `lifecycle { prevent_destroy = true }` until the quarantine ends.
3. **Retain-name recommendation**: keep an empty, locked bucket or a placeholder app that you own, so the name cannot be reclaimed.
4. **Evidence record** (JSON and PDF): inspection scope, sources and timestamps, what was checked, and **what could not be checked**.

## 3.6 Provider protection matrix (encoded as detectors)

| Provider / mechanism | Detector | Condition affected |
|---|---|---|
| S3 account-regional namespace | bucket namespace attribute | C2 → false |
| S3 `ExpectedBucketOwner` | scan consumer code/SDK calls for the header | C5 → false for supported ops |
| Azure domain verification / alias records | `asuid` TXT, alias record type | C2 / C3 |
| GitHub Pages verified domain | org/user verified-domain status | C2 → false |
| Terraform `prevent_destroy` | presence in config *before* the plan | blocks C1 (temporary) |

## 3.7 Integration points

* **CLI**: `retiresafe check --plan tfplan.json --zone zone.txt --repo . --logs access.log`
* **CI gate**: a GitHub Action that fails a PR whose `terraform plan` deletes a resource with any BLOCKED path.
* **Continuous mode**: re-run the DNS and TB1-style probe on a schedule to catch drift, i.e. references that start dangling later.

## 3.8 Proposed tech stack

| Layer | Choice | Why |
|---|---|---|
| Core | Python 3.11 | Reuses the test-bed code (dnspython, tldextract, requests) |
| IaC parsing | `terraform show -json` + `python-hcl2` | Machine-readable plan and config |
| Code scan | regex + `tree-sitter` for JS/Python/HCL | High recall for URL and bucket literals |
| Graph | `networkx` (demo) → Neo4j (later) | Path queries over Resource→Consumer |
| Stats | numpy / scipy / scikit-learn `IsotonicRegression` | Quarantine, bounds, recalibration |
| UI | FastAPI + small React or Streamlit page | Show the before/after decision |
| Reports | ReportLab (already used for the dossier) | Evidence record PDF |
