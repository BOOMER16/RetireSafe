# RetireSafe backend (pilot)

A pre-flight gate for cloud-resource retirement. It reads a proposed Terraform change, finds every reference that would survive the deletion, checks whether another party could re-register the released name, and measures whether consumers remain. The result is a per-resource verdict, a set of patches, and an auditable evidence record. It also runs a live drift scan to catch references left dangling by deletions made outside the gate.

* **Status:** pilot. Single node, SQLite storage, synchronous assessments. 83 automated tests (81 run offline; 2 live network tests run in CI). Validated against the research test beds on the same real data (see [Validation](#validation)).
* **Never executes changes.** It reads inputs and proposes patches. All network probes are read-only.

---

## What it guarantees, and what it doesn't

**Strict mode (the default) closes the takeover window for gated deletions.** For every covered resource type, a name the rules classify as reclaimable is **never released**. The gate fails until either the plan stops deleting the resource (it is kept as a *tombstone*) or the name is shown to be non-reclaimable (an S3 account-regional namespace, or an Azure scoped hostname). No attacker can claim a name the organisation still holds. That stays true even for references RetireSafe cannot see, such as third-party websites, offline clients and printed URLs. The evidence then decides *how to clean up*: which references to remove and what to migrate. It never decides *whether the name may be released*.

**Balanced mode** releases a reclaimable name only when no surviving reference is hijackable **and** fresh access logs covering at least `min_window_days` show silence past a conservative quarantine. That is a probabilistic judgement (miss tolerance `alpha`, default 1%), not a guarantee.

**Residual risk it does not remove:**

| Gap | How the pilot handles it |
|---|---|
| Deletions made outside Terraform/the gate (console, scripts) | `retiresafe scan` / `POST /v1/drift-scans` detects the dangling DNS afterwards. This is detection, not prevention |
| Resource types outside the pilot rules (for example Elastic IPs, CloudFront alternate domains) | Reported as `not_name_bearing` and listed under *outside coverage* in every evidence record. They do not block the gate |
| Domain expiry at the registrar; SPF `include:` of an expiring domain | Not covered yet (roadmap) |
| An attacker who already controls a name before retirement | Out of scope: RetireSafe prevents release, it does not audit existing ownership |

---

## Hardening features (see `docs/08_negatives_and_mitigations.md`)

| Feature | How to use |
|---|---|
| Secret redaction (Terraform masks, attribute minimisation, gitleaks rules) | automatic |
| Low-noise code scan (bucket-position rule, context, provider check) | automatic; every hit records `method` and `context` |
| Advisory rollout | `--enforcement advisory` (exit 0, `gate.would_pass` shows the real result) |
| Expiring, attributable waivers | `--waivers waivers.json` (format in `retiresafe/waivers.py`) |
| GitHub pull-request annotations | `--sarif out.sarif [--sarif-anchor infra/main.tf]` |
| Controls against out-of-gate deletion | `retiresafe guardrails --pipeline-role arn:aws:iam::<acct>:role/ci-*` |
| Email trust and registration | `retiresafe scan --owned-domain corp.example --spf --expiry` |
| Service hardening | API key required off-loopback; `--ssl-certfile/--ssl-keyfile`; `RETIRESAFE_OWNED_DOMAINS`; `RETIRESAFE_RETENTION_DAYS` |

## Install

```bash
cd backend
python3 -m venv ../.venv && ../.venv/bin/pip install -e ".[dev]"
../.venv/bin/retiresafe --version
```

Python ≥ 3.11. Runtime dependencies: dnspython, tldextract, requests, scipy, fastapi, uvicorn, python-multipart.

## CLI

```bash
# 1. Assess a proposed change (CI gate). Exit 0 = pass, 2 = fail, 1 = input error.
terraform show -json plan.out > plan.json
aws route53 list-resource-record-sets --hosted-zone-id Z123 > zone.json
retiresafe assess --plan plan.json \
  --dns zone.json --dns legacy.zone@example.com. \
  --repo web=./web-app --repo infra=./infra \
  --log s3-access.log,format=s3 \
  --log cloudfront.log,format=cloudfront \
  --log access.log,format=clf,host=www.example.com,path_prefix=/assets/ \
  --org-account 111122223333 --internal-domain example.com --internal-cidr 10.0.0.0/8 \
  --mode strict --migrate old-bucket=new-bucket-111122223333-us-east-1-an \
  --out evidence.json --markdown report.md

# 2. Live drift scan of names you own (exit 3 if anything is reclaimable)
retiresafe scan --dns zone.json --out drift.json

# 3. REST API
retiresafe serve --host 0.0.0.0 --port 8080

# 4. Print the source behind every rule
retiresafe sources
```

### Inputs

| Input | Format | Used for |
|---|---|---|
| `--plan` | `terraform show -json` (plan format 1.x) | what is being deleted (`delete` / `replace`), attributes such as `bucket_namespace`, and other resources in state that reference it |
| `--dns` | Route 53 `list-resource-record-sets` JSON, or a BIND zone file (`path@origin`; origin is inferred from the SOA if omitted) | CNAME / alias records pointing at the resource, followed through chains inside the inventory |
| `--repo` | directory | URLs, `s3://`, ARNs, `Bucket=` arguments, bare bucket literals and custom hostnames, plus SRI and `ExpectedBucketOwner` controls |
| `--log` | `clf` (Common/Combined), `s3` (server access logs), `cloudfront` (standard logs) | consumers: rate, quarantine, clients, /24 networks, external share |

## Policy

| Field | Default | Meaning / justification |
|---|---|---|
| `mode` | `strict` | `strict` never releases a reclaimable name; `balanced` releases on evidence |
| `alpha` | 0.01 | tolerated chance of missing a live consumer when declaring silence sufficient |
| `beta` | 0.05 | one-sided credible level; the quarantine uses the *lower* Jeffreys rate bound (longer wait) |
| `min_window_days` | 31 | logs must span at least a month, so daily, weekly and monthly clients are visible |
| `max_staleness_days` | 2 | logs must end within 2 days of `as_of`, otherwise the evidence is stale and C4 is UNKNOWN |
| `horizon_days` | 90 | horizon for the "consumer returns" probability used in the risk interval |
| `internal_domains`, `internal_cidrs` | `[]` | clients counted as internal for the external share |
| `org_account_ids` | `[]` | used in patches (owner checks, account-regional names) |

Supply it as JSON with `--policy policy.json`, or via the API `config.policy`.

## Decision rules

A takeover through one reference needs all five conditions:

| | Condition | TRUE when | FALSE when |
|---|---|---|---|
| C1 | released | the plan deletes or replaces the resource | — |
| C2 | reassignable | provider rule says another party can obtain the name | account-regional S3, or Azure scoped hostname |
| C3 | reference survives | the change does not remove the reference | the same plan deletes it, or (for a custom-hostname code link) its DNS record |
| C4 | consumer remains | requests seen and silence < conservative quarantine | fresh, ≥ `min_window_days` logs, silent past the quarantine |
| C5 | controls permit | no integrity or owner check on the consumer side | `<script/link integrity=…>` (SRI) or `ExpectedBucketOwner` |

Missing evidence makes a condition **UNKNOWN**, never FALSE. A path is *safe* if any condition is FALSE, *hijackable* if all are TRUE, and *unknown* otherwise.

| Verdict | Rule | Gate |
|---|---|---|
| `release` | C2 FALSE; or balanced mode with no hijackable/unknown path and C4 FALSE | pass |
| `block` | C2 TRUE and at least one hijackable path | fail |
| `tombstone` | C2 TRUE, no hijackable path, and (strict mode, or consumers / paths not ruled out) | fail until the plan keeps the resource |
| `review` | C2 UNKNOWN (for example a namespace not recorded) | fail |
| `not_name_bearing` | type outside pilot coverage (listed in the record) | pass |

**Quarantine.** λ̂ = n/T. λ_lo = β-quantile of Gamma(n + ½, rate T), the Jeffreys posterior. D\* = −ln(α)/λ. Both MLE and conservative D\* are reported, and the decision uses the conservative one.
**Risk interval.** The product of per-condition probabilities over paths, with UNKNOWN = [0, 1] and C4 = P(≥1 request within `horizon_days`) from the rate interval. It is used for ordering; it does not change the verdict.

## Coverage and sources

| Resource type | Reclaimable when | Verified from |
|---|---|---|
| `aws_s3_bucket` | `bucket_namespace = global` (or not recorded and the name is not in account-regional format) | AWS SDK S3 model (global uniqueness; account-regional namespace and its `prefix-<account>-<region>-an` format); Terraform AWS provider 6.67.0 schema (`bucket_namespace`); real re-registrations (watchTowr 2025, Hazy Hawk 2025) |
| `aws_elastic_beanstalk_environment` | always (shared CNAME prefix pool) | AWS SDK `CheckDNSAvailability`; can-i-take-over-xyz |
| `aws_eip`, `aws_instance` (public IP) | the address returns to AWS's pool; instance IPs cannot be held | Assetnote Ghostbuster research |
| `azurerm_storage_account`, `azurerm_cdn_endpoint`, `azurerm_api_management`, `azurerm_traffic_manager_profile`, `azurerm_container_registry` | the name is embedded in a shared suffix | Microsoft dangling-DNS table (article source); can-i-take-over-xyz |
| `azurerm_container_group`, `azurerm_public_ip` | DNS label without a reuse scope (`Unsecure` / unset) | Azure SDK enums (azure-mgmt-containerinstance 10.1.0, azure-mgmt-network 33.0.0) |
| `azurerm_*web_app`, `azurerm_app_service`, `azurerm_*function_app` | classic `<name>.azurewebsites.net` | Microsoft dangling-DNS guidance; CDC incident (Infoblox 2025); can-i-take-over-xyz. A scoped hostname (`autoGeneratedDomainNameLabelScope`, from the Azure SDK) is **not** reclaimable |

Full quotes are in `retiresafe/knowledge/sources.py` (`retiresafe sources`). The fingerprint catalogue is vendored at commit `5bd4e128…` (CC BY 4.0), and its SHA-256 is recorded.

## REST API

| Method | Path | Body / result |
|---|---|---|
| GET | `/healthz` | status |
| GET | `/v1/knowledge` | rules version, coverage, sources |
| POST | `/v1/assessments` | multipart: `plan` (file), `dns` (files), `logs` (files), `repo` (zip or tar.gz), `config` (JSON string). Returns the evidence record |
| GET | `/v1/assessments` · `/v1/assessments/{id}` · `/v1/assessments/{id}/report.md` | list / record / Markdown report |
| POST | `/v1/drift-scans` | `{"hostnames": [...]}` (max 2,000). Live read-only checks |
| GET | `/v1/drift-scans/{id}` | stored scan |
| POST | `/v1/demo/pilot` | import the recorded pilot assessments from `pilot/results` (repository checkout only; idempotent) |
| GET | `/` → `/ui/` | web console (static files in `retiresafe/web`) |

### Web console

`retiresafe/web/` holds plain HTML, CSS and ES modules, with no build step and no dependencies. It is served under
`Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; ... frame-ancestors 'none'`, so it
loads nothing from third parties and runs no inline code. Every value taken from a record is HTML-escaped by the
`html` template helper (`js/util.js`). Record text includes code lines and DNS data from the inputs, so this escaping matters.
The traffic chart uses `traffic[].daily_requests` (requests per UTC day for each log view) and
`parse_stats[log].daily_lines` (parsed lines per day for the whole file). A day with zero lines is a gap in logging,
not silence. Both are counts only. `tests/test_web.py` checks the CSP, that the assets are self-contained, that there is
no inline code, the pilot import, and that the daily counts add up to the totals they illustrate.

`config` example:

```json
{
  "policy": {"mode": "strict", "org_account_ids": ["111122223333"], "internal_domains": ["example.com"]},
  "logs": [{"filename": "access.log", "format": "clf", "host": "www.example.com", "path_prefix": "/assets/"}],
  "dns_origins": {"legacy.zone": "example.com."},
  "repo_label": "web",
  "as_of": "2026-10-01T00:00:00Z",
  "migrate_to": {"old-bucket": "new-bucket-111122223333-us-east-1-an"}
}
```

Environment: `RETIRESAFE_DB` (SQLite path, default `retiresafe.db`), `RETIRESAFE_API_KEY` (require an `X-API-Key` header), `RETIRESAFE_MAX_UPLOAD_MB` (default 512). Uploaded archives are extracted with path-traversal checks; links and devices are rejected.

## Evidence record (`retiresafe.evidence/v1`)

`assessment_id`, `created_at`, `as_of`, `tool` (version, rules version, catalogue commit), `policy`, `inputs` (SHA-256 of every file, a tree hash for repositories), `plan`, `gate` (`passed`, verdict counts), `resources[]` (resource, C2 result, references, traffic summaries, paths with all five conditions and their evidence ids, verdict, reasons, risk interval, patches, `not_checked`), `evidence[]`, `parse_stats`, `scan_stats`, `not_checked` (outside coverage), and `sources` (the exact quotes behind every rule that was cited).

## Validation

| Check | Data | Result |
|---|---|---|
| Quarantine maths and CLF parser vs research TB2 | NASA-HTTP Jul 1995, 1,891,715 lines | **exact match**: lines, parse failures (1,958), resources (7,133), span, and every D\* percentile |
| Traffic summaries vs research TB3 | same | **exact match**: 108 / 108 / 15,054, and clients, /24s and external counts for the top 5 |
| Drift scanner vs research TB1 | 3,518 live CNAME'd hostnames (Umbrella sample) | **99.26 % agreement**. All 5 reclaimable and all 5 stale reproduced, with no new false positives. 20 names reported as `lookup_error` (resolver timeouts after retries), 2 newly stale |
| Rate bounds | — | equal to the independent χ² identity λ = χ²(2n+1)/2T |
| Log parsers | AWS-published S3 and CloudFront example records; NASA sample | field-by-field match |
| Terraform reader | real Terraform 1.16.4 / AWS 6.67.0 plans (pilot) | — |

Run with `python validation/cross_check.py tb2 tb3 [tb1]` (`tb1` needs live DNS and the private TB1 results). Outputs are in `validation/results/`.

**Defects the validation found and fixed:** (1) a timed-out CNAME lookup was classified as "no CNAME", a silent false all-clear; it is now `lookup_error` with retries. (2) A CNAME to a bare S3 endpoint did not resolve the bucket name; S3 takes it from the Host header, and that is now the rule. (3) The research TB1 script had misfiled 4 *existing* S3 buckets as "needs HTTP check"; the research summary was corrected.

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest -q        # 83 tests, about 1.5 minutes with the real data present
```

Tests marked `realdata` need the NASA logs in `/home/user/data/nasa-http` (see `../scripts/fetch_data.sh`) and skip cleanly without them.

## Performance (pilot hardware, single process)

The full pilot runs three assessments, each parsing 3.46 M real log lines once, in 78 s. Parsing is streaming, and each log file is read once per assessment however many resources it covers.

## Layout

```
retiresafe/
  models.py              data model (three-valued conditions, evidence, verdicts)
  names.py               resource-name extraction from text
  config.py              policy / log configuration validation
  knowledge/             provider rules, source register, vendored fingerprint catalogue
  collectors/            terraform_plan, dns_zone, repo_scan, access_logs
  analysis/traffic.py    rates, Jeffreys bounds, quarantine, blast radius
  engine/                assess (orchestration), decide (five conditions), remediate (patches)
  probes/live.py         drift scanner (DNS chain walk, fingerprints, S3 existence)
  report/evidence.py     evidence record and Markdown report
  api/                   FastAPI app and SQLite store
  cli.py                 command line
validation/              cross-checks against the research test beds
tests/                   pytest suite and fixtures (see tests/fixtures/README.md)
```
