# Pilot scenario

An end-to-end demonstration of the backend: a proposed deletion that RetireSafe blocks, the fixes it proposes, and the corrected change that passes.

## What is real and what is constructed

| Part | Status |
|---|---|
| Terraform plans (`generated/plan_*.json`) | **Real tool output**: Terraform 1.16.4 and hashicorp/aws 6.67.0 (checksums verified against HashiCorp's SHA256SUMS), run against a local **moto 5.2.3** AWS emulator |
| Route 53 exports (`generated/route53_*.json`), BIND zone | **Real tool output**: boto3 `list_resource_record_sets` against moto; zone written by dnspython |
| Traffic | **Real**: NASA-HTTP Jul+Aug 1995 (3,461,612 lines, unmodified), attributed to the scenario hosts by the fixed rules in `scenario.json` / `scripts/select_traffic.py` |
| Organisation, bucket names, app code (`app/`) | **Constructed**. Uses the reserved `.example` TLD (RFC 2606), so it cannot collide with real infrastructure. The SRI hash in `app/index.html` is the real hash of `app/css/site.css` |

Known emulator quirk: moto returns the Route 53 SOA value as a Python dict repr. RetireSafe does not use SOA records.

## The story

* **DNS root** (`terraform/dns`): `event.` CNAME → S3 website endpoint, `cdn.` CNAME → S3 REST endpoint, plus unrelated `www` and SPF records. It is owned by another team, so the app plan cannot see it.
* **App root** (`terraform/app`): four buckets. `event_site` (website), `event_assets`, and `legacy_downloads` are in the **global** namespace; `archive` is in the **account-regional** namespace. There is also an SSM parameter holding the assets URL.
* **v2** proposes deleting all four buckets after the event.

## Results (`results/`)

| Run | Gate | event_site | event_assets | legacy_downloads | archive |
|---|---|---|---|---|---|
| before, strict | **FAIL** | BLOCK (CNAME + custom-domain link) | BLOCK (CNAME, unpinned `<script>`, SSM parameter) | TOMBSTONE (strict) | RELEASE (account-regional) |
| before, balanced | **FAIL** | BLOCK | BLOCK | RELEASE (87 real requests, silent 16.5 d > conservative quarantine 3.9 d) | RELEASE |
| after, strict | **PASS** | kept as tombstone | kept, content moved to an account-regional bucket | kept as tombstone | RELEASE |

What separates safe from unsafe references, as found in the scan: the SRI-pinned stylesheet (C5 false), the upload script that uses `ExpectedBucketOwner` (C5 false), and the website configuration deleted in the same plan (C3 false).

"After" applies RetireSafe's own outputs: the Route 53 change batch (DNS v2), the code diff (`results/applied_code.patch`, applied with `git apply`), and the tombstone HCL (app v3).

## Reproduce

```bash
# prerequisites: terraform 1.16.x + hashicorp/aws 6.67.0 in a filesystem mirror (see build_scenario.py),
# moto, and a loopback entry because S3 Control prefixes the account id to the endpoint host:
echo '127.0.0.1 s3control.pilot.internal 123456789012.s3control.pilot.internal' | sudo tee -a /etc/hosts
python pilot/scripts/build_scenario.py      # regenerates pilot/generated/ (with manifest.json hashes)
python pilot/scripts/run_pilot.py [path/to/nasa_jul_aug_1995.log]
```

The committed `generated/` files are enough to run `run_pilot.py`; the build step is only needed to regenerate them. During development the first build ran before the S3 Control endpoint was redirected, so the provider sent a few tag-listing requests to real AWS endpoints with the dummy key `pilot`; AWS refused them (403). The harness now routes every service it uses to the emulator.
