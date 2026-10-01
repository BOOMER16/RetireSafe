# 04 · Mathematics

Each item is labelled ✅ **run on real data** (a test bed in this repo) or 📐 **proposed** (engine design, not yet run).

## (a) Poisson quarantine window ✅ TB2

Model a resource's requests as a homogeneous Poisson process with rate λ (requests per day).

* MLE from n requests over T days: **λ̂ = n / T**
* If the resource is still live, the probability of seeing zero requests in a silent window of length D is **P₀(D) = e^(−λD)**
* For a miss tolerance α, the quarantine is the smallest D with P₀ ≤ α:

  **D\* = −ln(α) / λ̂**  (α = 0.01 gives D\* = 4.605 / λ̂)

TB2 on NASA-HTTP gives p50 = 42.3 d and p90 = 126.9 d. The ceiling is set by single-request resources, where λ̂ = 1/T and so D\* = 4.605 T.

## (b) Uncertainty on rare resources 📐

A point estimate λ̂ is fragile when n is small, and these are exactly the risky resources. Use the **upper** confidence bound of the rate so the quarantine is conservative:

* **Poisson / Gamma bound.** With a Jeffreys prior, λ | n ~ Gamma(n + ½, T). Take λ_lo as its β-quantile (for example β = 0.05). The *lower* bound is used because a *smaller* rate gives a *longer* quarantine: **D\*_safe = −ln(α) / λ_lo**.
* **Wilson interval** for proportions such as "share of days with ≥1 hit" or the external-client share:

  **[ p̂ + z²/2n ± z·√( p̂(1−p̂)/n + z²/4n² ) ] / (1 + z²/n)**

  This was used in [02](02_testbeds.md) for TB1's base rate: 5/16,000 = 0.031%, 95% CI 0.013–0.073%.
* **Window rule.** If T is shorter than a plausible client period (weekly, monthly or annual jobs), C4 is reported as **unknown** instead of producing a quarantine estimate. No amount of silence inside a short window rules out a client with a longer period.

## (c) Calibration ✅ check run (TB2) · 📐 recalibration proposed

* **Run:** a hold-out split (train on days 0–24, test on days 24–27.6). The model predicted 1,161.4 returns, 783 were observed, so predicted ÷ observed = **1.48**. Observed return rates generally rise across deciles of predicted probability, but every decile sits below the prediction (see the reliability plot, Fig. 3 in the dossier).
* **Proposed:** fit **isotonic regression** g: p_model → p_observed on the organization's own historical retirements, then report g(p). Measure with:
  * Brier score = (1/N) Σ (pᵢ − yᵢ)²
  * Expected calibration error = Σ_b (n_b/N) · |mean(p)_b − mean(y)_b|

## (d) Takeover risk score 📐

The conditions are a conjunction, so the score is a product:

**R = P(C1) · P(C2) · P(C3) · P(C4) · P(C5) · Impact**

* P(C1) is 0 or 1, from the plan.
* P(C2) comes from the probe and protection detectors: `NoSuchBucket` in the global namespace ≈ 1, account-regional namespace = 0.
* P(C3) is 1 if the reference survives the change.
* P(C4) = 1 − e^(−λ_up · H) over a horizon H (the probability that consumers return), using the upper rate bound and recalibrated with g.
* P(C5) is low if the consumer enforces an owner, integrity or signature check.
* Impact = f(blast radius, external share, consumer kind). For example, software update > script include > page view > image.

**Unknowns are not set to 0 or 1.** An unevaluable factor is treated as an interval [p_min, p_max], which widens the interval on R. The decision state becomes UNKNOWN unless some *other* factor is provably 0.

## (e) Blast radius ✅ TB3

For each resource over its history:

* C = distinct clients, N₂₄ = distinct /24 networks, C_ext = clients outside the organization
* external share **e = C_ext / C**
* feeds the Impact term and the "who breaks" summary (count, networks, how external, last seen)

## (f) Base-rate reasoning for triage ✅ TB1

Reclaimable references are rare: π ≈ 3×10⁻⁴ per live hostname overall, and about 2.5×10⁻³ for CNAME'd tail names. That means a scanner with even a small false-positive rate will mostly produce false alarms unless it confirms candidates. Bayes:

P(real | flagged) = sens·π / (sens·π + fpr·(1 − π))

With π = 3×10⁻⁴, sens = 0.95 and fpr = 0.01, the precision is only about 2.8%. This is why RetireSafe **requires a live confirmation probe** (the second rung of the ladder) before raising BLOCKED, and why it lists HTTP-fingerprint matches separately as "needs check".
