# 05 · Datasets and tools

The research rule was **real data first**. Fabricated data was to be used only if nothing real existed, and in the end **no fabricated data was needed**.

## 5.1 Datasets used

| Dataset | What it is | Size / version | Licence / terms | Used in | How to get it |
|---|---|---|---|---|---|
| **Cisco Umbrella top-1M** | FQDNs ranked by real query volume on Cisco's resolvers; includes subdomains | 1,000,000 rows; copy from 2026-10-01 (updated daily) | Free public list from Cisco | TB1 | `scripts/fetch_data.sh` |
| **NASA-HTTP Jul 1995** | Real HTTP access log of the NASA Kennedy Space Center web server | 1,891,715 lines, 27.6 days | Freely redistributable (Internet Traffic Archive) | TB2, TB3 | `scripts/fetch_data.sh` (GitHub mirror `greymd/NASA-HTTP`) |
| NASA-HTTP Aug 1995 | Second month of the same log | 1,569,898 lines | as above | downloaded, **not used** (reserved for an out-of-sample re-run) | as above |
| **can-i-take-over-xyz** | Community catalogue of takeover fingerprints per service | 76 services (36 vulnerable / 26 not / 14 edge) | CC BY 4.0 | TB1 | `scripts/fetch_data.sh` |
| **Live DNS** | System resolver queries (CNAME, A, AAAA, NS) | 16,000 hostnames (CNAME walk + A/AAAA/NS follow-ups) | public DNS | TB1 | dnspython |
| **Live S3 REST API** | `GET https://s3.amazonaws.com/<bucket>` existence probe | 8 probes (1 top, 7 random) | AWS public API | TB1 | requests |
| Top PyPI packages | 15,000 most-downloaded packages (2026-10-01) | 787 KB JSON | public | fetched for TB5, **not used** | `hugovk/top-pypi-packages` |

## 5.2 Tools and libraries

| Tool | Version used | Purpose |
|---|---|---|
| Python | 3.11.15 | everything |
| dnspython | 2.8.0 | CNAME-chain walking, NXDOMAIN/NS checks |
| tldextract | 5.3.2, bundled PSL (offline) | registrable-domain extraction |
| requests | 2.34.2 | S3 existence probe |
| numpy / math | 2.4.6 | statistics |
| matplotlib | 3.11.2 | figures |
| reportlab | 5.0.1 | dossier PDF |
| pdftotext / pypdf | — | reading the brief and extracting its links |

## 5.3 Sources that were unreachable from the research sandbox

The research ran in a sandbox whose egress proxy only allows certain hosts. Connections to these hosts were **refused by the proxy** (the CONNECT tunnel failed; HTTP 403 where the status was shown). That shaped which test beds were run:

| Host | Would have been used for | Workaround / status |
|---|---|---|
| `dns.google`, `cloudflare-dns.com` (DoH) | DNS queries | the system resolver worked, so it was used instead |
| `crt.sh` | subdomain discovery via Certificate Transparency | Umbrella top-1M used for hostnames instead |
| `rdap.org` | domain registration status | NS lookup on the registrable domain used as a proxy |
| `api.npmjs.org`, `pypistats.org` | download time-series of deprecated packages (consumer persistence) | NASA logs used for consumer persistence instead |
| `tranco-list.eu` | research-grade domain ranking | Umbrella used instead |
| `ita.ee.lbl.gov` | original NASA log host | GitHub mirror used |
| arbitrary hosts (HTTP fingerprints) | HTTP-body takeover fingerprints | would be "needs HTTP check"; after the TB1 correction no sampled name required it |

Running the code on an ordinary machine with open internet removes all of these limits.

## 5.4 Datasets recommended for the hackathon build

| Need | Recommended source |
|---|---|
| Demo infrastructure | A **team-owned** AWS sandbox account: legacy-namespace bucket, Route 53 zone, a small static site, CloudFront logs |
| Realistic access logs | the team's own CloudFront/S3 server-access logs, or NASA-HTTP for an offline demo |
| Subdomain inventory | the org's own DNS zone export (`aws route53 list-resource-record-sets`) |
| Takeover fingerprints | can-i-take-over-xyz (keep it pinned to a commit) |
| SPF evidence | the org's own TXT records via dnspython (TCP for large TXT) |
