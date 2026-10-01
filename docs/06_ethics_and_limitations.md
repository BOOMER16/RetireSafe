# 06 · Ethics, responsible disclosure and honesty boundaries

## 6.1 Rules followed during the research

1. **Read-only.** Only DNS lookups and unauthenticated `GET` requests to the public S3 API were made. Nothing was registered, created, claimed or written anywhere.
2. **No takeover attempts.** A *reclaimable candidate* means the evidence says another party *could* claim the name. It was never tested by trying to claim it.
3. **No third-party hostnames are published.** TB1's per-hostname output (`testbeds/results/tb1_raw.private.jsonl`) is git-ignored. The repo, the docs and the PDF contain only aggregate counts. The named examples (CDC, Hazy Hawk, MSN, Swatch, …) come from already-public reports and are described as historical.
4. **Real data only.** No synthetic or fabricated data was used. Where a source was unreachable, a different real source was substituted and the substitution is documented ([05](05_datasets_and_tools.md)).

## 6.2 Responsible disclosure: action item

TB1 found **5 live reclaimable candidates** on real hostnames (4 S3, 1 Azure). If the team keeps these results, the right next step is to **notify the owners** through each site's `security.txt` or bug-bounty channel before any public demo. They should be told which hostname is affected and that the CNAME should be removed, or the name retained.
*The per-hostname file was produced in an ephemeral research container and is not in this repo. Re-running `tb1_dns_cname.py` regenerates it locally.*

## 6.3 For the hackathon demo

* Run the before/after demo **only against infrastructure the team owns** (a sandbox AWS account and a test domain).
* Never point the scanner's *probe* stage at third-party assets during the live demo.
* Show TB1 only as aggregate counts.

## 6.4 Honesty boundaries for the pitch

| Claim we **can** make | Claim we must **not** make |
|---|---|
| About 0.03% of 16k sampled live hostnames have reclaimable dangling references (95% CI 0.013–0.073%) | "X% of the internet is vulnerable" |
| On NASA traffic, 99%-confident retirement needs 42–127 days of silence per resource | "Wait 127 days before deleting anything" |
| A naive Poisson model over-predicted returns by 1.48× on a hold-out | "Our model predicts consumer behaviour accurately" |
| Resources that look idle on a 3-day dashboard had thousands of historical external clients | "Deleting them would have breached N users" |
| Public reports document malicious takeovers (CDC, Hazy Hawk, SubdoMailing) and 20,904 hijacks (NSDI '24) | "20,904 organizations were breached" or "8M infections" |
| RetireSafe *proposes* blocked deletions, patches and evidence records | "RetireSafe guarantees safe deletion" |
