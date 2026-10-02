# Test cards for a security expert

Each card says what to do, what RetireSafe should do, and why. The expected outcomes for cards 1–6 were recorded by running them through the API (`kit/EXPECTED.md`); cards 7–12 were checked against the running server the same way. Start the server with `retiresafe serve` and use **02 New check** unless a card says otherwise.

For every card that uses a settings file, drop `kit/02_add_real_traffic/settings.json` into **Settings file**, then add:
* `kit/01_proposed_change/plan.json`
* `kit/01_proposed_change/route53.json`
* the card's `app.zip`
* the traffic log `data\nasa-http\nasa_jul_aug_1995.log`

## A. Does it reason correctly?

**1 · Baseline (the proposed deletion).** Use the step-02 inputs as listed above, with `kit/01_proposed_change/app.zip`.
→ Gate **FAIL**. `rs-pilot-event-assets-2025` is BLOCK with 3 hijackable paths (CNAME, SSM parameter, unpinned `<script>` at `index.html:14`). Two paths are broken at C5: the SRI-pinned stylesheet (`index.html:7`) and the `ExpectedBucketOwner` upload (`tools/upload_assets.py:10`). The access-log path is *unverified*: "consumers seen only in logs; their integrity checks are unknown".

**2 · Pin the script with Subresource Integrity.** Use `kit/expert/A_pin_script_with_sri/app.zip`. It is identical except `index.html:14` now carries the real sha384 of `countdown.js`.
→ `index.html:14` changes from hijackable to **broken at C5**. The bucket stays BLOCK because the CNAME and the SSM parameter are still hijackable. *One fix does not clear a resource while other paths remain.*

**3 · Remove the bucket-owner check.** Use `kit/expert/B_drop_owner_check/app.zip`, where `upload_assets.py` loses `ExpectedBucketOwner`.
→ `tools/upload_assets.py:10` changes from broken to **hijackable**. Without the owner check, the SDK writes to whoever owns the name.

**4 · Comment out the script.** Use `kit/expert/C_comment_out_script/app.zip`.
→ `index.html:14` is still listed (context *comment*), but the path is **broken at C4**: "the reference is inside a code comment; nothing executes or follows it". The scanner separates live code from comments and prose.

**5 · Your own edit.** Unzip `kit/01_proposed_change/app.zip`, change anything (add a bucket URL to a new file, delete the CNAME from `route53.json`, rename the bucket in the code), zip it again and run it. Every path cites the file and line or DNS record it came from, so you can check each decision by hand.

**6 · Policy matters, evidence decides.** Run the step-02 inputs again with `kit/03_balanced_policy/settings.json`.
→ `rs-pilot-legacy-downloads` changes from TOMBSTONE to **RELEASE**. Its 87 real requests stopped 16.5 days before the end of the log, longer than the conservative quarantine of 3.9 days (shown with the formula on the resource page). Strict mode never releases a name someone else could claim; balanced releases it on evidence.

## B. Is the tool itself safe to run on sensitive inputs?

**7 · Hostile markup in a repository.** Use `kit/expert/D_hostile_markup/app.zip`. It adds `docs/notes.html` containing `<img src=x onerror=alert(document.domain)>` and `<script>alert(1)</script>` next to a bucket URL. The new reference `app::docs/notes.html:1` appears as a hijackable path. Open it, its raw JSON and the findings queue.
→ The markup is shown as text and **nothing executes**. All record text is HTML-escaped, and the page runs under `Content-Security-Policy: default-src 'none'; script-src 'self'; …` with no inline script allowed.

**8 · Zip-slip.** Upload `kit/expert/E_zip_slip/app.zip` (member `../../outside.txt`) as the repository.
→ **HTTP 400**: "archive member escapes the extraction directory". Nothing is written.

**9 · Archive bomb.** Stop the server and start it with a 1 MB extraction limit:
```bat
set RETIRESAFE_MAX_EXTRACT_MB=1
retiresafe serve
```
Upload `kit/expert/F_archive_bomb/app.zip` (5,223 bytes that expand to 5 MB).
→ **HTTP 413**: "archive expands to 5 MB; limit 1 MB". The limit is checked from the declared sizes and again while writing. Afterwards, run `set RETIRESAFE_MAX_EXTRACT_MB=` and restart.

**10 · Secrets do not leak into evidence.** Open any step-01 result and search the evidence JSON for `AKIA` or `wJalr`. `config/legacy.env` and `tools/mirror_legacy.sh` contain AWS's documented example keys.
→ Neither key string appears anywhere in the record. The line that carries one is stored as `AWS_SECRET_ACCESS_KEY=[REDACTED] aws s3 sync …`. Terraform-sensitive values (the SSM parameter) show as `[sensitive value; contains a reference to …]`.

**11 · Live probes are scoped.** Go to **04 Drift scan**.
→ It is disabled until the server is started with `RETIRESAFE_OWNED_DOMAINS`. With `set RETIRESAFE_OWNED_DOMAINS=yourdomain.com`, names outside that domain are refused (**HTTP 422**). Only read-only DNS lookups and unauthenticated S3 GETs are made. To test it for real, list hostnames under a domain you control.

**12 · Network exposure.** Run `retiresafe serve --host 0.0.0.0` without a key.
→ It refuses to start ("refusing to listen on a non-loopback address without RETIRESAFE_API_KEY set"). With `set RETIRESAFE_API_KEY=…`, every `/v1` call needs the `X-API-Key` header (401 otherwise), and the console asks for the key once per tab.

## C. Use it the way a pipeline would

```bat
retiresafe assess --plan demo\kit\01_proposed_change\plan.json --dns demo\kit\01_proposed_change\route53.json ^
  --repo app=<unzipped app folder> --org-account 123456789012 --as-of 1995-09-01T03:59:53Z ^
  --out evidence.json --markdown report.md --sarif findings.sarif
echo %ERRORLEVEL%
```
→ Exit code **2** (gate fails), **0** on a passing change, and **1** on bad input. `findings.sarif` is SARIF 2.1.0 for GitHub code scanning. Each assessment's **Evidence & provenance** tab shows the exact command, rebuilt from the record.

With your own infrastructure: `terraform plan -out p.out` and then `terraform show -json p.out > plan.json`, plus `aws route53 list-resource-record-sets --hosted-zone-id Z… > dns.json`. Both are read-only, and RetireSafe never calls your cloud account.

## Known limits (say them before they are found)

* Coverage is AWS S3, Elastic Beanstalk, EC2/Elastic IPs and the main Azure name-bearing types; CloudFront, Front Door and GCP are not covered yet. Unsupported deletions are listed under **Not checked** instead of passing silently.
* Consumers that never appear in the supplied logs (yearly jobs, offline clients) cannot be seen. Short or stale logs make C4 *unverified*, never *safe*.
* No real AWS organisation has run it yet; the infrastructure here is real Terraform output against an emulator.
