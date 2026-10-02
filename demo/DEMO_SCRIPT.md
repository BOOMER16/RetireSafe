# Presenter script (about 8 minutes, then hand over to the judge)

Every number below was produced by the system on these exact inputs (`kit/EXPECTED.md`), and the browser run of this script was checked end to end. Steps 02–04 each take about 25–45 s while the 373 MB traffic log is read. Use that time to talk.

## Before the judges arrive

- [ ] `conda activate retiresafe`, then `cd C:\Users\Barenyam\RetireSafe`
- [ ] Empty database: `del retiresafe.db retiresafe.db-wal retiresafe.db-shm 2>nul`
- [ ] `retiresafe serve`, then open http://127.0.0.1:8080/ and press **Ctrl+F5**. The review list should be **empty**.
- [ ] `data\nasa-http\nasa_jul_aug_1995.log` exists (if not: `python scripts\get_data.py`)
- [ ] Open File Explorer at `demo\kit` so the files are one drag away
- [ ] Second Anaconda Prompt ready with `python demo\run_steps.py 02 03 04` as a fallback

## 0 · The problem (30 s)

> "When a team deletes a cloud resource such as an S3 bucket, its *name* goes back into a public pool. DNS records, code and clients often still point at it. Anyone who re-registers the name inherits that traffic and that trust. In 2025 watchTowr re-registered about 150 abandoned bucket names and received more than 8 million requests in two months. RetireSafe checks a deletion **before** it runs and blocks it while a takeover path exists."

Point at the empty console: "Nothing is pre-loaded. Everything you'll see comes from files I upload now."

## 1 · The proposed change, without traffic (1 min)

**02 New check**, then:

| Field | File in `demo\kit` |
|---|---|
| Settings file | `01_proposed_change\settings.json` (the form fills itself in) |
| Terraform plan | `01_proposed_change\plan.json` |
| DNS records | `01_proposed_change\route53.json` |
| Code | `01_proposed_change\app.zip` |

**Run the check.** The result is instant: **FAIL** with 3 TOMBSTONE, 1 RELEASE and 2 *no name at risk*.

> "The plan deletes four buckets, a website configuration and an SSM parameter. These are real Terraform 1.16.4 plans. The `archive` bucket is in AWS's new **account-regional** namespace, where nobody else can claim the name, so it is released. The other three are global names. Without traffic evidence RetireSafe cannot prove whether anyone still uses them, and **unknown is never treated as safe**, so strict policy keeps the names as tombstones."

## 2 · Add real traffic (2 min)

**02 New check** with settings `02_add_real_traffic\settings.json`, the same plan, DNS and app, plus **Access logs**: `data\nasa-http\nasa_jul_aug_1995.log`. The three log views fill in automatically. **Run** (about 40 s).

While it runs: "This is the real NASA web server log from July–August 1995, 3.46 million requests, unmodified. Fixed path rules map parts of it to our three hosts."

Result: **FAIL** with **2 BLOCK**, 1 TOMBSTONE and 1 RELEASE. Read the **What to do** list out loud, then open `rs-pilot-event-assets-2025`:

- **Takeover paths.** Three rows are fully red (the CNAME, the SSM parameter and the unpinned `<script>` at `index.html:14`) and two are struck through:
  - Click **C5** on `index.html:7`. The stylesheet is pinned with Subresource Integrity, so a swapped file would be refused.
  - Click **C5** on `tools/upload_assets.py:10`. `ExpectedBucketOwner` makes the SDK refuse a stranger's bucket.
  - "It doesn't just grep for the name. It decides, condition by condition, whether a reference can actually be abused."
- Click **C2** on the CNAME. The source quote from the AWS SDK model appears: global names are unique across all accounts.
- **Is anyone still using it?** 1,206,043 requests from 116,125 clients, 97% external, last request at the very end of the log. That is a live dependency.
- **Fixes.** A Route 53 change batch, a code diff that moves the assets to an account-regional bucket, and a tombstone in Terraform.

## 3 · Same evidence, balanced policy (1 min)

Settings `03_balanced_policy\settings.json`, with the same files and log. **Run.**

`rs-pilot-legacy-downloads` changes from TOMBSTONE to **RELEASE**. Open it:

> "87 real requests from 22 clients, the last on 15 August. Silent for **16.5 days**. With a conservative Poisson bound, a consumer at even the lower-bound rate would have shown up within **3.9 days** with 99% probability. The formula is on screen with the numbers filled in. Strict mode would still keep the name; balanced releases it, *on evidence*."

## 4 · The corrected change passes (1 min)

Settings `04_corrected_change\settings.json`, then **plan, DNS and app from `04_corrected_change`**, plus the same log. **Run.**

Result: **PASS**. "The fixed plan keeps the three live names as tombstones, the DNS records are gone, and the app was rewritten by RetireSafe's own patch to the account-regional bucket. Only the safe deletions remain."

Open **03 Before / after**. Pick step 02 as *before* and step 04 as *after*: **FAIL → PASS**, resource by resource. The input fingerprints show what changed (plan, DNS, code) and what didn't (the traffic log).

## 5 · Built for operators (1 min)

- **01 Reviews**: the findings queue across every run. Filter *Hijackable*, type `index.html`, then **Export CSV**.
- Press **Ctrl+K**, type `legacy` and press Enter. Press `?` for shortcuts and `j`/`k` to move between rows.
- On an assessment, open **Evidence & provenance**:
  - **Reproduce** shows the exact `retiresafe assess …` command for CI. The exit code is 2 here, 0 on pass, and SARIF output feeds GitHub code scanning.
  - Every input is SHA-256 fingerprinted, and every rule cites its source.

## 6 · Hand over

> "Please try to break it." Give the judge [`EXPERT_TESTS.md`](EXPERT_TESTS.md): hostile markup, zip-slip, archive bomb, secret redaction, scope guard, or their own edits to the app.

## Likely questions (honest answers)

| Question | Answer |
|---|---|
| Why not a firewall or WAF? | The attacker isn't coming *in*. Your own users and systems go *out* to a name you gave away, and the content is served from the attacker's account. There is nothing to filter at your edge. The fix is not to give the name away while something still points at it. |
| False positives? | Measured on six real repositories (TensorFlow Datasets, Airflow, Transformers and others): 18,290 bare-word false matches cut to 0, and all 60 hand-labelled real references still blocking. |
| What if there are no logs? | Then C4 is *unverified*, and strict policy keeps the name (step 1). It never guesses "safe". |
| Does keeping names cost money? | An empty S3 bucket has no storage charge, though it counts toward the bucket quota (fee only beyond 2,000 buckets). Held Elastic IPs (USD 0.005/hour), Elastic Beanstalk and API Management tombstones do cost money. Every tombstone states its cost and a review date. |
| Coverage? | AWS S3, Elastic Beanstalk, EC2/EIP and the main Azure name-bearing types. CloudFront, Front Door and GCP are not covered yet, and unsupported deletions are listed under *Not checked*, never passed silently. |
| Is the data real? | The plans and DNS exports are real Terraform/AWS-provider output against an emulator. The traffic is real NASA logs. The app and names are invented (`.example`), on purpose. |

## If something goes wrong

| Problem | Do this |
|---|---|
| Browser upload of the log is slow | In the second prompt: `python demo\run_steps.py 02 03 04` (same uploads, results appear in the console) |
| Port in use | `retiresafe serve --port 8090` |
| Old results showing | Stop the server, delete `retiresafe.db*`, start again |
| `'retiresafe' is not recognized` | `conda activate retiresafe` |
