# 01 · Problem model and public evidence

## 1.1 The problem

Organizations routinely retire cloud storage buckets, web apps, temporary event sites and third-party services. The resource disappears, but **references to its name survive**:

| Where trust hides | Example surviving reference |
|---|---|
| DNS | `event.example.com CNAME event-app.azurewebsites.net` remains after the app is deleted |
| Application config / code | A JS bundle loads `https://old-assets.s3.amazonaws.com/lib.js` |
| Software update / package config | An APT source or installer fetches from a deleted bucket |
| Email authorization | An SPF record keeps `include:` for a domain that has since expired |
| Identity / validation | A WHOIS server or validation endpoint that moved, while clients still use the old one (.mobi case [7]) |

If the released name can be obtained by another owner, those references deliver users, software or mail-authorization to the new owner. That often happens **under the original organization's legitimate domain**.

**Primary user:** a platform or cloud engineer reviewing a deletion or migration, supported by security.
**Decision they need help with:** *what must be removed, migrated or protected before this resource can be released?*

## 1.2 Takeover is a conjunction of five conditions

A broken link is not a vulnerability on its own. All five of these must hold:

| # | Condition | Why it matters | RetireSafe evidence |
|---|---|---|---|
| 1 | **Resource released** | A different account must be able to obtain control | Planned deletion (Terraform plan, console action) |
| 2 | **Name reassignable** | Reserved names, account-regional namespaces and domain verification can prevent reclaim | Provider rules + fingerprint catalogue + live existence probe |
| 3 | **Reference survives** | DNS, config, code or SPF still points there | DNS export, repository scan, IaC graph, TXT/SPF |
| 4 | **Consumer remains** | Someone or something still relies on the reference | Access/CDN logs (TB2/TB3 engine) |
| 5 | **Controls permit impact** | Ownership or integrity checks may reject the replacement | `ExpectedBucketOwner`, SRI hashes, package signatures, domain verification |

`takeover possible = C1 ∧ C2 ∧ C3 ∧ C4 ∧ C5`

**Consequence for the design:** a deletion is **cleared** only when at least one condition is *provably false*, and the engine can say which one. Any condition that cannot be evaluated is reported as **unknown** rather than guessed.

## 1.3 The evidence ladder

Every finding sits on one rung. RetireSafe never claims a rung it has not shown.

```
stale reference  ──►  reclaimable endpoint  ──►  demonstrated impact
(points at nothing)   (another party could       (a consumer would accept
                       claim the name)            the replacement)
```

## 1.4 What the public record establishes

Stated at the strength the sources support.

1. **Malicious exploitation is real.**
   * *CDC (Feb–Mar 2025)* [2]: `ahbazuretestapp.cdc.gov` was a CNAME to an abandoned Azure app. The replacement owner served scams and scareware. This was abuse of a subdomain, not a breach of the CDC network. *(Our live check on 2026-10-01: that name now returns NXDOMAIN, so the record has been removed.)*
   * *Hazy Hawk (since Dec 2023)* [3]: a French government Olympics site (DNS left behind after the event), the `oercommons` S3 bucket, and subdomains under Deloitte, EY, PwC, UC Berkeley, UCL, Alabama and Australian health parent domains. These are historical observations, not current vulnerabilities.
2. **It happens at scale.** NSDI 2024 [5] found **20,904** hijacked resources. About ⅓ persisted for more than 65 days, there were about 1,800 attacker infrastructures, and 75% of the abuse was blackhat SEO. These are counts of instances, not of victims.
3. **Dependencies outlive projects by years.** watchTowr [6] re-registered about 150 abandoned S3 buckets and received **8M+ requests in 2 months**. That included Emscripten/`mozilla-games` binaries whose documentation reference had been removed in 2015.
4. **Email trust survives too.** SubdoMailing [4] reported 8,000+ domains (a vendor figure) where dangling CNAME/SPF let spoofed mail pass SPF (the MSN and Swatch examples).
5. **Observed traffic is not compromise.** In the .mobi case [7], a CA accepted an email address from the replacement WHOIS server as a validation option. The researchers stopped before issuing a certificate.

### What the evidence does not establish
* Not every deleted resource can be reclaimed.
* Not every stale reference is exploitable.
* A subdomain hijack does not prove an internal network breach.
* Request counts are not infection counts.
* Several of the examples come from the same campaign and should not be counted as independent.

## 1.5 Existing protections that RetireSafe must recognize

| Protection | Effect on a finding |
|---|---|
| S3 account-regional namespaces (2026) [8] | Other accounts cannot reclaim these names, so condition 2 is false for such buckets. Legacy global buckets remain at risk, and existing buckets cannot be renamed |
| S3 bucket-owner condition [9] | When the *consumer* sends `ExpectedBucketOwner`, condition 5 is false for supported operations |
| Azure dangling-DNS detection, alias records, domain verification [1] | Reduces conditions 2 and 3, but only if it is configured |
| GitHub Pages verified domains [10] | Takeover protection within the documented scope |
| Terraform `prevent_destroy` [11] | Blocks destructive plans while it is configured. Removing the resource block also removes the guard, and it does not list consumers |

**The opportunity:** these protections exist but are fragmented across providers and are frequently not configured. Dependency information is spread across teams. The innovation is **coordinated, evidence-backed safe retirement**, not rediscovering subdomain takeover.
