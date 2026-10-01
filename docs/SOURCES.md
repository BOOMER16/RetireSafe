# Source register

Numbers match the citations used in the dossier and in the original brief.

## Primary reports, research and provider documentation

| # | Source | What we use it for |
|---|---|---|
| [1] | Microsoft Learn, *Prevent dangling DNS entries and avoid subdomain takeover*. <https://learn.microsoft.com/en-us/azure/security/fundamentals/subdomain-takeover> | Definition of the failure mode; Azure protections (dangling-DNS detection, alias records, domain verification) |
| [2] | Infoblox, 10 Mar 2025, *How scammers hijack major brands* (CDC incident). <https://www.infoblox.com/blog/threat-intelligence/how-scammers-hijack-major-brands/> | Observed malicious takeover of an abandoned Azure endpoint under a CDC subdomain |
| [3] | Infoblox, 20 May 2025, *Cloudy with a chance of hijacking* (Hazy Hawk). <https://www.infoblox.com/blog/threat-intelligence/cloudy-with-a-chance-of-hijacking-forgotten-dns-records-enable-scam-actor/> | Campaign context: French Olympics site, oercommons S3 bucket, institutional subdomains |
| [4] | Guardio Labs, 26 Feb 2024, *SubdoMailing*. <https://guard.io/labs/subdomailing-thousands-of-hijacked-major-brand-subdomains-found-bombarding-users-with-millions> | SPF/CNAME email-trust abuse (MSN, Swatch); 8,000+ domains as reported by the vendor |
| [5] | USENIX NSDI 2024, Friess et al., *Cloudy with a Chance of Cyberattacks: Dangling Resources Abuse on Cloud Platforms*. <https://www.usenix.org/conference/nsdi24/presentation/friess> | Peer-reviewed scale: 20,904 hijacked resources, about ⅓ lasting more than 65 days, 75% used for blackhat SEO |
| [6] | watchTowr Labs, 4 Feb 2025, *8 Million Requests Later*. <https://labs.watchtowr.com/8-million-requests-later-we-made-the-solarwinds-supply-chain-attack-look-amateur/> | About 150 abandoned S3 buckets re-registered, 8M+ requests in 2 months; traffic outlives documentation |
| [7] | watchTowr Labs, 11 Sep 2024, *We Spent $20 To Achieve RCE And Accidentally Became The Admins Of .MOBI*. <https://labs.watchtowr.com/we-spent-20-to-achieve-rce-and-accidentally-became-the-admins-of-mobi/> | Moving a service does not move the trust in its old endpoint; CA validation accepted the replacement WHOIS |
| [8] | AWS Storage Blog, 24 Apr 2026, *Migrate to Amazon S3 account regional namespaces*. <https://aws.amazon.com/blogs/storage/migrate-to-amazon-s3-account-regional-namespaces/> | New S3 namespace that other accounts cannot reclaim; legacy global buckets still at risk |
| [9] | AWS docs, *Verifying bucket ownership with bucket owner condition*. <https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-owner-condition.html> | `ExpectedBucketOwner` control that downgrades risk when consumers enforce it |
| [10] | GitHub docs, *Verifying your custom domain for GitHub Pages*. <https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages> | Provider takeover protection for verified domains |
| [11] | HashiCorp docs, *Terraform lifecycle meta-argument* (`prevent_destroy`). <https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle> | Deletion guard; removed along with the resource config, so it is not a consumer inventory |

## Datasets and tools used in the test beds

| Name | Link | Used in |
|---|---|---|
| Cisco Umbrella top-1M | <https://s3-us-west-1.amazonaws.com/umbrella-static/top-1m.csv.zip> | TB1 |
| NASA-HTTP 1995 logs (Internet Traffic Archive; GitHub mirror) | <https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html> · mirror <https://github.com/greymd/NASA-HTTP> | TB2, TB3 |
| EdOverflow *can-i-take-over-xyz* | <https://github.com/EdOverflow/can-i-take-over-xyz> | TB1 |
| AWS S3 REST API (read-only `GET`) | <https://s3.amazonaws.com> | TB1 |
| dnspython, tldextract, requests, matplotlib, numpy, reportlab | PyPI | all |
