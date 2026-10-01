# 07 · Hackathon build plan, demo and pitch

## 7.1 Scope for the sprint (following the brief)

**In scope:** legacy S3 buckets, a supplied repository, a DNS export, access logs, and a proposed Terraform deletion, shown as a **controlled before/after** retirement.
**Out of scope for the demo:** SPF/email trust, Azure, GitHub Pages and continuous monitoring. These are on the roadmap and explain why the idea matters beyond the demo; the demo does not claim to cover them.

## 7.2 Build milestones

| # | Milestone | Reuses | Done when |
|---|---|---|---|
| M1 | **Demo fixture** in a team-owned AWS sandbox: a legacy-namespace bucket `rs-demo-event-assets`, a Route 53 record `assets.<testdomain>` → bucket, a small repo whose JS loads from the bucket, CloudFront/S3 access logs, and a `main.tf` | — | `terraform plan -destroy` shows the bucket deletion |
| M2 | **Collect**: DNS-zone parser, repo URL/bucket scanner, plan-JSON reader | `common.py` | lists every reference to the bucket, with file:line or record |
| M3 | **Probe**: S3 existence + namespace check, fingerprint match, `ExpectedBucketOwner` detector | `tb1_dns_cname.py` | each reference labelled reclaimable / protected / unknown |
| M4 | **Observe**: log ingestion → λ, D\*, blast radius, external share, window flag | `tb2_*.py`, `tb3_*.py` | per-resource consumer summary |
| M5 | **Decide**: five-condition evaluator + risk score R | [04](04_mathematics.md) | BLOCKED / CLEARED / RETAIN / UNKNOWN with reasons |
| M6 | **Act**: patch generator (DNS removal, URL rewrite, `ExpectedBucketOwner`, `prevent_destroy`) + evidence-record PDF | `make_pdf.py` | patch applies; PDF renders |
| M7 | **Interface**: CLI plus a one-page web view of the before/after; optional GitHub Action | — | demo runs end-to-end in under 2 minutes |

Suggested split for a team of four: (1) fixture + IaC, (2) collectors + probe, (3) traffic stats + decision engine, (4) UI, report and pitch.

## 7.3 Demo script (about 3 minutes)

1. **Before.** "The event is over, let's delete the assets bucket." Run `terraform plan -destroy` → RetireSafe → **BLOCKED**. On screen: the CNAME, the code reference at `app.js:118`, consumers in the logs, D\* and the release date, and the fact that the bucket is in the legacy global namespace and therefore reclaimable.
2. **Explain** in one sentence using the five conditions. All five are true for this path.
3. **Apply the patch.** Remove the CNAME, rewrite the URL to the new bucket, and add `prevent_destroy` until the quarantine ends.
4. **After.** Re-run → **CLEARED**, with the evidence record PDF showing what was checked and what could not be checked.
5. **Close with real data.** "On 16,000 real internet hostnames, 5 had exactly this flaw live today, and on real traffic, resources that look idle had thousands of hidden consumers."

## 7.4 Pitch sequence (as recommended in the brief)

1. **Concrete victim:** CDC Azure subdomain abused for scams [2].
2. **Measured scale:** NSDI 2024, 20,904 hijacked resources, about ⅓ lasting more than 65 days [5].
3. **Why DNS-only fails:** watchTowr, 8M+ requests to abandoned S3 buckets long after the docs were updated [6]. Add our TB3: thousands of hidden dependents behind "idle" resources.
4. **Our evidence:** TB1 base rate (0.031%, rare and buried, so it needs automation), TB2 quarantine (42–127 d, so no global timeout).
5. **The decision:** live demo, BLOCKED → patch → CLEARED with an evidence record.
6. **Honesty slide:** what we claim and what we don't ([06](06_ethics_and_limitations.md)).

## 7.5 Judging-criteria mapping

| Likely criterion | Our answer |
|---|---|
| Problem validity | Five public incidents/studies plus our own real-data base rate |
| Innovation | Coordinated, evidence-backed retirement across DNS + code + IaC + traffic, aware of provider protections. Not another subdomain scanner |
| Technical depth | Poisson quarantine, calibration check, Bayesian triage, five-condition decision logic |
| Feasibility | Probe and Observe stages already run on real data (TB1–TB3) |
| Responsibility | Read-only research, no published targets, disclosure plan |

## 7.6 Roadmap after the sprint

1. TB4 SPF dangling-include audit, then an SPF retirement check (SubdoMailing class).
2. TB5 scan of package and repository S3 references (watchTowr class).
3. Azure (`asuid` verification, alias records) and GitHub Pages detectors.
4. Isotonic recalibration on real organizational retirement history.
5. Continuous drift monitoring, plus migration helpers for S3 account-regional namespaces.
