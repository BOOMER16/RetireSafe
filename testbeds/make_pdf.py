"""Compose the RetireSafe research + solution dossier PDF from real test-bed outputs."""
import json
import os
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Table, TableStyle, Image, HRFlowable, KeepTogether,
                                PageBreak, ListFlowable, ListItem)

HERE = os.path.dirname(__file__)
R = os.path.join(HERE, "results"); FIG = os.path.join(HERE, "figs")
OUT = os.path.join(HERE, "..", "RetireSafe_Solution_Dossier.pdf")
tb1 = json.load(open(f"{R}/tb1_summary.json"))
tb2 = json.load(open(f"{R}/tb2_summary.json"))
tb3 = json.load(open(f"{R}/tb3_summary.json"))

INK = colors.HexColor("#1b2430"); MUT = colors.HexColor("#5b6775")
ACC = colors.HexColor("#c23b22"); ACC2 = colors.HexColor("#2f6f8f")
LINE = colors.HexColor("#c9d1d9"); BG = colors.HexColor("#f4f1ec")

ss = getSampleStyleSheet()
def S(name, **kw):
    base = kw.pop("parent", ss["Normal"])
    return ParagraphStyle(name, parent=base, **kw)

body = S("body", fontName="Helvetica", fontSize=9.3, leading=13.6, textColor=INK,
         alignment=TA_JUSTIFY, spaceAfter=6)
h1 = S("h1", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=INK, spaceBefore=4, spaceAfter=3)
h2 = S("h2", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=ACC, spaceBefore=10, spaceAfter=3)
kicker = S("kicker", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=ACC, spaceAfter=2)
small = S("small", fontName="Helvetica", fontSize=7.6, leading=10, textColor=MUT)
cap = S("cap", fontName="Helvetica-Oblique", fontSize=7.6, leading=10, textColor=MUT, spaceAfter=8)
li = S("li", parent=body, alignment=TA_LEFT, spaceAfter=3)
quote = S("quote", fontName="Helvetica-Oblique", fontSize=10, leading=14, textColor=ACC2,
          leftIndent=8, borderPadding=0, spaceBefore=4, spaceAfter=8)

def page_bg(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK); canvas.rect(0, 0, A4[0], 6*mm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 7); canvas.setFillColor(colors.white)
    canvas.drawString(18*mm, 2.2*mm, "RETIRESAFE  ·  SOLUTION DOSSIER")
    canvas.drawRightString(A4[0]-18*mm, 2.2*mm, "Hacker Sprint / Manipal Bengaluru  ·  page %d" % doc.page)
    canvas.restoreState()

doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                      topMargin=15*mm, bottomMargin=12*mm, title="RetireSafe Solution Dossier")
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=page_bg)])

def rule(c=LINE, w=0.8, sb=2, sa=6):
    return HRFlowable(width="100%", thickness=w, color=c, spaceBefore=sb, spaceAfter=sa)

def statcard(items):
    cells = []
    for big, lab in items:
        cells.append([Paragraph(big, S("b", fontName="Helvetica-Bold", fontSize=17, textColor=ACC, leading=19)),
                      ])
    data = [[Paragraph(f'<font size=17 color="#c23b22"><b>{b}</b></font><br/><font size=7.3 color="#5b6775">{l}</font>', small)
             for b, l in items]]
    t = Table(data, colWidths=[doc.width/len(items)]*len(items))
    t.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
                           ("LEFTPADDING",(0,0),(-1,-1),8),("BACKGROUND",(0,0),(-1,-1),BG),
                           ("LINEBEFORE",(1,0),(-1,-1),0.8,colors.white),("BOX",(0,0),(-1,-1),0.5,LINE)]))
    return t

def tbl(data, widths, head=True, fs=8):
    t = Table(data, colWidths=widths)
    st = [("FONT",(0,0),(-1,-1),"Helvetica",fs),("TEXTCOLOR",(0,0),(-1,-1),INK),
          ("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),4),
          ("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),6),
          ("RIGHTPADDING",(0,0),(-1,-1),6),("LINEBELOW",(0,0),(-1,-2),0.5,LINE),
          ("LINEBELOW",(0,-1),(-1,-1),0.8,MUT)]
    if head:
        st += [("FONT",(0,0),(-1,0),"Helvetica-Bold",fs),("TEXTCOLOR",(0,0),(-1,0),colors.white),
               ("BACKGROUND",(0,0),(-1,0),INK),("LINEBELOW",(0,0),(-1,0),0,INK)]
    t.setStyle(TableStyle(st)); return t

def bullets(items, st=li):
    return ListFlowable([ListItem(Paragraph(x, st), leftIndent=10, value="•") for x in items],
                        bulletType="bullet", start="•", leftIndent=8)

E = []
# ---------- COVER ----------
E += [Spacer(1, 8*mm), Paragraph("HACKER SPRINT / MANIPAL BENGALURU", kicker),
      Paragraph("RetireSafe", S("title", fontName="Helvetica-Bold", fontSize=34, textColor=INK, leading=36)),
      Paragraph("An evidence-driven workflow for safely retiring cloud resources", h1),
      Spacer(1, 2*mm), rule(ACC, 2, 2, 8),
      Paragraph("Solution dossier &amp; proposed architecture — grounded in three test beds "
                "run on <b>real</b> public data (Cisco Umbrella top-1M, the NASA-HTTP 1995 "
                "traffic archive, and the <i>can-i-take-over-xyz</i> fingerprint catalogue). "
                "No figures in this document are fabricated; every number traces to a script "
                "and an output file in <font face=Courier>/testbeds</font>.", body),
      Spacer(1, 3*mm)]
E += [statcard([("~0.03%", "reclaimable references found across 16,000 real live hostnames (TB1)"),
                ("42–127 d", "silence needed to be 99% sure a resource is truly dead (TB2)"),
                ("108 / 108", "'idle' resources that still had hidden external dependents (TB3)")])]
E += [Spacer(1, 4*mm),
      Paragraph("THE ONE-LINE PROBLEM", kicker),
      Paragraph("When a cloud resource is deleted, the <b>trust placed in its address survives</b> — "
                "DNS records, app configs, SPF rules, and automated clients keep pointing at a name "
                "that an attacker can now reclaim. RetireSafe decides, with evidence and stated "
                "uncertainty, whether a resource is safe to release.", quote)]
E += [Spacer(1,2*mm), rule(),
      Paragraph("What this dossier contains", h2),
      bullets(["<b>§1 Problem model</b> — the five conditions for takeover, as a checkable state machine.",
               "<b>§2 Evidence &amp; scale</b> — what the public record establishes, stated conservatively.",
               "<b>§3 Three test beds on real data</b> — the heart of the submission: measured base rates, a traffic-survival model, and the coordination gap quantified.",
               "<b>§4 Proposed architecture</b> — scanners, the evidence graph, the decision engine, outputs.",
               "<b>§5 The mathematics</b> — Poisson survival, Wilson bounds, risk scoring, calibration.",
               "<b>§6 Datasets &amp; tools</b>, <b>§7 roadmap</b>, <b>§8 honesty boundaries</b>, <b>§9 sources</b>."])]
E += [PageBreak()]

# ---------- §1 PROBLEM ----------
E += [Paragraph("§1", kicker), Paragraph("The problem, as a checkable model", h1), rule(ACC,1.5),
      Paragraph("A broken reference is not automatically a vulnerability. Takeover requires a "
                "<b>conjunction</b> of five conditions. RetireSafe's job is to evaluate each one with "
                "the evidence available, and to report the ones it <i>cannot</i> evaluate rather than "
                "guessing. We model a retirement candidate as passing only if every condition is "
                "provably false.", body)]
cond = [["#", "Condition for takeover", "What RetireSafe checks", "Evidence source"],
        ["1","Resource released","Would a different account be able to obtain the name?","Provider API / namespace rules"],
        ["2","Name reassignable","Reserved names, domain verification, account-regional S3","Fingerprint catalogue + provider docs"],
        ["3","Reference survives","DNS/CNAME, app config, SPF, code, IaC still point there","DNS, repo scan, config export"],
        ["4","Consumer remains","Someone/something still relies on the reference","Access-log traffic analysis"],
        ["5","Controls permit impact","No owner/integrity check rejects the replacement","bucket-owner-condition, SRI, sig"]]
E += [tbl(cond, [7*mm, 32*mm, 78*mm, 57*mm]), Spacer(1,2*mm),
      Paragraph("Design consequence: the output is never a binary 'safe'. It is a <b>per-condition "
                "verdict</b> — <font color='#2f6f8f'>cleared</font>, <font color='#c23b22'>blocking"
                "</font>, or <b>unknown</b> — so an engineer sees exactly why a deletion is held and "
                "what evidence would release it.", body)]

# ---------- §2 EVIDENCE ----------
E += [Paragraph("§2", kicker), Paragraph("What the public record establishes", h2), rule(),
      Paragraph("Drawn from the research brief's own sources and re-stated at the strength the "
                "evidence actually supports:", body),
      bullets([
        "<b>Malicious exploitation is real.</b> Infoblox documented the <font color='#c23b22'>CDC</font> "
        "Azure-endpoint takeover (Feb–Mar 2025) and the broader <b>Hazy Hawk</b> campaign (active since "
        "Dec 2023) hijacking abandoned DNS references of CDC, a French government Olympics site, and an "
        "<font face=Courier>oercommons</font> S3 bucket. These are subdomain hijacks — not proof of "
        "internal-network breach.",
        "<b>It happens at scale.</b> USENIX NSDI 2024 (Friess et al.) identified <b>20,904</b> hijacked "
        "cloud resources, ~⅓ persisting &gt;65 days; 75% used for blackhat SEO. That is a count of "
        "instances, not of breached organisations.",
        "<b>Dependencies outlive projects by years.</b> watchTowr registered ~150 abandoned S3 buckets "
        "and received <b>8M+ HTTP requests</b> in two months; a <font face=Courier>mozilla-games</font> "
        "bucket was still receiving traffic years after its doc reference was removed in 2015.",
        "<b>Email trust survives too.</b> Guardio's SubdoMailing found 8,000+ domains with dangling "
        "SPF/CNAME authorisation (MSN, Swatch) abused to pass SPF on spoofed mail.",
        "<b>Observed traffic ≠ compromise.</b> watchTowr's .mobi WHOIS work showed a CA accepting a "
        "replacement-server email as a validation option — they stopped before issuing a rogue cert. "
        "Request counts are not infection counts."]),
      Paragraph("RetireSafe therefore treats every signal as sitting on an <b>evidence ladder</b>: "
                "stale reference → reclaimable endpoint → demonstrated impact. The product's value is "
                "moving a candidate up that ladder with proof, and refusing to assert a rung it hasn't "
                "shown.", quote)]
E += [PageBreak()]

# ---------- §3 TEST BEDS ----------
E += [Paragraph("§3", kicker), Paragraph("Three test beds, run on real data", h1), rule(ACC,1.5),
      Paragraph("Each test bed is a standalone script in <font face=Courier>testbeds/</font> with a committed output file in <font face=Courier>testbeds/results/</font>. All lookups are "
                "<b>read-only</b>: nothing was registered, claimed, or written to any third party.", small),
      Spacer(1,2*mm)]

# TB1
E += [Paragraph("TB1 · Base rate of surviving reclaimable references in the live internet", h2),
      Paragraph("<b>Data.</b> Cisco Umbrella top-1M FQDNs (real DNS-resolver popularity). We sampled the "
                f"top 8,000 and 8,000 uniformly-random names. <b>Method.</b> Walk each name's CNAME chain, "
                "match the tail against the <i>can-i-take-over-xyz</i> fingerprint catalogue "
                "(76 services), "
                "resolve the final target, and for AWS/S3 probe the bucket's existence via the S3 API "
                "(404 <font face=Courier>NoSuchBucket</font> = reclaimable). Each name is placed on the "
                "evidence ladder; <b>raw hostnames are never published</b>.", body),
      Image(f"{FIG}/fig1_tb1.png", width=165*mm, height=73*mm),
      Paragraph("Fig 1 — Across 16,000 real hostnames the overwhelming majority resolve healthily; only a "
                "handful sit on the reclaimable rung. Counts are symlog-scaled.", cap)]
E += [Paragraph(f"<b>Result.</b> Of 16,000 live names, the pipeline flagged roughly "
                f"<b>5 reclaimable candidates</b> (4 S3 <font face=Courier>NoSuchBucket</font>, 1 Azure "
                f"NXDOMAIN) plus 5 stale references — a base rate near <b>0.03%</b>. "
                "This is the single most important number for the product: the dangerous cases are "
                "<i>rare and buried</i>, which is precisely why manual review misses them and why an "
                "automated, evidence-first scanner earns its place. It also validates our fingerprint + "
                "live-probe pipeline end-to-end on real infrastructure.", body)]
E += [rule(),
# TB2
      Paragraph("TB2 · 'Is this endpoint really dead?' — a traffic-survival model", h2),
      Paragraph("<b>Data.</b> NASA-HTTP July 1995 access log — <b>1,891,715</b> real requests, 7,133 "
                "distinct resources, 27.6-day span (Internet Traffic Archive). <b>Question.</b> The "
                "brief's core uncertainty: when an endpoint shows no hits for D days, how sure can we "
                "be that no consumer still depends on it? <b>Model.</b> Treat each resource's requests "
                "as a Poisson process with rate λ; the chance of a silent window of length D is "
                "e^(−λD). Invert for the <b>quarantine</b>: D ≥ −ln(α)/λ with α = 1%.", body)]
tb2tab = [["Quarantine for 99% confidence","p50","p90","p99","max","mean"],
          ["days of silence required",
           f"{tb2['quarantine_days_for_1pct_miss']['p50']:.0f}",
           f"{tb2['quarantine_days_for_1pct_miss']['p90']:.0f}",
           f"{tb2['quarantine_days_for_1pct_miss']['p99']:.0f}",
           f"{tb2['quarantine_days_for_1pct_miss']['max']:.0f}",
           f"{tb2['quarantine_days_for_1pct_miss']['mean']:.0f}"]]
E += [Table([[Image(f"{FIG}/fig2_tb2_quar.png", width=99*mm, height=44*mm),
              Image(f"{FIG}/fig3_tb2_rel.png", width=54*mm, height=51*mm)]],
            colWidths=[103*mm, 58*mm], style=[("VALIGN",(0,0),(-1,-1),"TOP")]),
      Paragraph("Fig 2 (left) — half of all resources need ≥42 days of silence, and the long tail needs "
                "~127 days, to justify a 99%-confident 'dead' verdict. A single global idle-timeout is "
                "therefore unsafe. Fig 3 (right) — holding out the last week and estimating λ on the "
                "first 24 days, the Poisson model's predicted return-probability is consistently "
                "<i>above</i> the observed rate across every decile.", cap),
      Paragraph(f"<b>Result &amp; honest finding.</b> On the hold-out, {tb2['holdout_validation']['idle_cohort_size']:,} "
                f"resources looked idle at the cutoff; the Poisson model expected "
                f"{tb2['holdout_validation']['poisson_expected_return']:.0f} of them to receive traffic "
                f"again, and {tb2['holdout_validation']['actually_returned']:,} actually did. The model "
                "<b>ranks</b> resources well (monotonic deciles) but is <b>mis-calibrated as an absolute "
                "probability</b> — traffic is bursty, not memoryless. The design takeaway is concrete: "
                "use the model to <i>prioritise and rank</i>, but gate deletion on an "
                "<b>empirically-calibrated, per-resource</b> quarantine with a safety margin, never on a "
                "parametric point estimate.", body)]
E += [PageBreak()]
# TB3
E += [Paragraph("TB3 · The coordination gap, measured", h2),
      Paragraph("<b>Data.</b> Same NASA log. <b>Idea.</b> The brief: a resource 'can appear unused to "
                "the team deleting it while remaining trusted elsewhere.' We make that measurable. Rank "
                "resources by how quiet they are in the final 3 days (what an activity dashboard would "
                "show), then reveal each one's <b>blast radius</b>: distinct client hosts, /24 networks, "
                "and <i>external</i> (non-<font face=Courier>nasa.gov</font>) clients over full history.", body),
      Table([[Image(f"{FIG}/fig4_tb3.png", width=74*mm, height=70*mm),
              Paragraph(
                f"<b>Result.</b> Of resources with real history that look idle in a 3-day window, "
                f"<b>{tb3['of_those_with_live_external_dependents']} of "
                f"{tb3['resources_looking_dead_in_window']} (100%)</b> still carried traffic from "
                f"external clients. The worst case — <font face=Courier>{tb3['top_offenders'][0]['resource']}"
                f"</font> — showed <b>{tb3['top_offenders'][0]['recent_3d_requests']} hits</b> in the recency window yet <b>"
                f"{tb3['max_hidden_external_clients_on_one_dead_looking_resource']:,}</b> distinct "
                f"external dependents across its history.<br/><br/>Deleting on the dashboard signal "
                f"alone would silently break thousands of third parties the deleting team cannot see "
                f"or notify. This is the coordination gap, quantified — and the direct justification "
                f"for RetireSafe fusing DNS + code + <b>runtime traffic</b> before clearing a deletion.", body)]],
            colWidths=[78*mm, 83*mm], style=[("VALIGN",(0,0),(-1,-1),"TOP")]),
      Paragraph("Fig 4 — the eight 'idle-looking' resources with the largest hidden external dependent "
                "populations.", cap)]

# ---------- §4 ARCHITECTURE ----------
E += [rule(ACC,1.5), Paragraph("§4", kicker), Paragraph("Proposed architecture", h1),
      Paragraph("RetireSafe is a <b>retirement pre-flight</b>: given a proposed deletion, it gathers "
                "evidence from every place trust can hide, fuses it into one graph, and returns a "
                "per-condition verdict with a migration patch. Pipeline:", body)]
arch = [["Stage","Component","Real inputs","Produces"],
        ["Collect","Reference scanners","DNS/zone export, Git repo (regex+AST for URLs/buckets/SRI), "
         "IaC state (Terraform plan JSON), SPF/DNS TXT","Candidate references to the target"],
        ["Probe","Reclaimability prober","Fingerprint catalogue, S3/Azure existence + namespace rules, "
         "domain-verification & bucket-owner-condition status","Each ref: reclaimable? protected?"],
        ["Observe","Traffic analyser","Access/CDN logs (the TB2/TB3 engine)","λ, quarantine, blast radius, external %"],
        ["Fuse","Evidence graph","All of the above keyed by resource","Dependency graph + evidence per edge"],
        ["Decide","Decision engine","Graph + §5 risk score","Verdict: clear / block+reason / unknown"],
        ["Act","Output layer","Verdict","Blocked plan, migration patch, evidence record"]]
E += [tbl(arch, [15*mm, 30*mm, 74*mm, 55*mm], fs=7.6), Spacer(1,2*mm),
      Paragraph("<b>Outputs</b> (from the brief's wish-list): a <b>blocked deletion with a precise "
                "reason</b>; a <b>proposed migration patch</b> (e.g. rewrite the CNAME, add "
                "<font face=Courier>ExpectedBucketOwner</font>, drop the stale SPF include, set "
                "Terraform <font face=Courier>prevent_destroy</font>); a <b>'retain the name' "
                "recommendation</b> when traffic persists; and an immutable <b>evidence record</b> "
                "stating inspection scope and what could <i>not</i> be checked.", body),
      Paragraph("<b>Recognising existing protections</b> is a first-class feature, not an afterthought: "
                "S3 account-regional namespaces (2026), bucket-owner-condition, Azure dangling-DNS "
                "detection + domain verification, GitHub Pages domain verification, and Terraform "
                "<font face=Courier>prevent_destroy</font> each <i>downgrade</i> a finding's severity. "
                "RetireSafe must not cry wolf over a reference the provider already protects.", body)]
E += [PageBreak()]

# ---------- §5 MATH ----------
E += [Paragraph("§5", kicker), Paragraph("The mathematics", h1), rule(ACC,1.5),
      Paragraph("<b>(a) Survival / quarantine.</b> Per resource, λ̂ = n/T (MLE for a homogeneous Poisson "
                "process). Probability a truly-live resource shows zero hits over a silent window D is "
                "P₀ = e^(−λD). Required quarantine for miss-tolerance α: <b>D* = −ln(α)/λ̂</b>. TB2 shows "
                "D* ranges 42→127 days at α=1% — the engine emits D* per resource.", body),
      Paragraph("<b>(b) Uncertainty on rare resources.</b> For a resource seen k times, a point rate is "
                "fragile. We bound the true request probability with the <b>Wilson</b> interval (better "
                "than normal approximation for small k) and, for counts, a Poisson/Gamma credible "
                "interval; the <i>upper</i> bound drives the conservative quarantine so infrequent-but-"
                "real clients are not discarded.", body),
      Paragraph("<b>(c) Calibration, not blind trust.</b> TB2's reliability diagram showed the raw "
                "Poisson is over-confident; the engine fits an <b>isotonic recalibration</b> on held-out "
                "history so the probability it reports (\"12% chance a client still depends on this\") is "
                "one an engineer can act on. We report Brier score / ECE, not just accuracy.", body),
      Paragraph("<b>(d) Takeover risk score.</b> Combine the five conditions multiplicatively — a chain "
                "is only as safe as its weakest cleared link:", body),
      Paragraph("R = P(released) · P(reassignable) · P(reference survives) · P(consumer remains) · "
                "P(controls fail to block) · Impact", S("eq", fontName="Courier", fontSize=8.6, leading=12,
                textColor=INK, backColor=BG, borderPadding=6, spaceAfter=6)),
      Paragraph("Each factor is an evidence-weighted probability with its own confidence; a factor that "
                "<i>cannot</i> be evaluated is reported as <b>unknown</b> and widens the score's interval "
                "rather than being silently assumed 0 or 1. <b>(e) Blast radius</b> (TB3): distinct "
                "clients C and /24 networks N over history, with external share e = C_ext/C, feed the "
                "Impact term and the human-readable 'who breaks' summary.", body),
      Paragraph("<b>Status.</b> Run on real data: (a) quarantine D*, the hold-out calibration check in "
                "(c), and (e) blast radius. Proposed engine design, not yet run: the Wilson / Gamma "
                "bounds in (b), the isotonic recalibration fit in (c), and the risk score in (d).", small)]

# ---------- §6 DATA/TOOLS ----------
E += [Paragraph("§6", kicker), Paragraph("Datasets &amp; tools", h2), rule(),
      tbl([["Dataset / tool","Role","Status"],
           ["Cisco Umbrella top-1M","Real popular-hostname sample (TB1)","Used, live DNS"],
           ["NASA-HTTP 1995 (ITA)","1.89M real requests (TB2, TB3)","Used"],
           ["can-i-take-over-xyz","76-service takeover fingerprint catalogue","Used"],
           ["AWS S3 REST API","Live bucket-existence probe (read-only)","Used"],
           ["dnspython","CNAME-chain + NS/A/AAAA resolution","Used"],
           ["Terraform plan JSON","IaC deletion intent (prod scanner)","Designed"],
           ["SPF/DNS TXT","Email-trust dependency (future scope)","Designed"],
           ["NumPy/SciPy, Matplotlib, ReportLab","Modelling, figures, this PDF","Used"]],
          [45*mm, 85*mm, 44*mm], fs=8)]

# ---------- §7 ROADMAP ----------
E += [Paragraph("§7", kicker), Paragraph("Hackathon scope &amp; roadmap", h2), rule(),
      Paragraph("<b>Demo (build now).</b> Legacy S3 buckets + a supplied repo + a DNS export + access "
                "logs + a proposed Terraform deletion. Show a controlled before/after: a deletion that "
                "is <b>blocked</b> with a precise reason and a migration patch, versus one <b>cleared</b> "
                "with its evidence record. <b>Next:</b> SPF/email-trust scanner (SubdoMailing class), "
                "Azure + GitHub Pages probers, CI/CD gate (a failing check on an unsafe "
                "<font face=Courier>terraform destroy</font>), and continuous drift monitoring.", body)]

# ---------- §8 HONESTY ----------
E += [Paragraph("§8", kicker), Paragraph("Honesty boundaries", h2), rule(),
      bullets(["Our TB1 base rate is a sample estimate from 16k names, not a census; it establishes "
                "order-of-magnitude rarity, which is the point.",
               "TB2/TB3 use 1995 NASA traffic because it is a large, real, openly-licensed log; the "
                "<i>method</i> is dataset-agnostic and would run on a team's own CDN logs.",
               "A reclaimable candidate is a <b>candidate</b> — we never attempted a takeover. Demonstrating "
                "impact on a client's own resource, with authorisation, is future work.",
               "We recognise provider protections explicitly so we don't label protected references "
                "exploitable. The innovation is <b>safe-retirement coordination</b>, not rediscovering "
                "subdomain takeover."], small)]

# ---------- §9 SOURCES ----------
E += [Paragraph("§9", kicker), Paragraph("Source register", h2), rule(),
      Paragraph("[1] Microsoft Learn — Prevent dangling DNS &amp; subdomain takeover. "
                "[2] Infoblox, 10 Mar 2025 — CDC incident. [3] Infoblox, 20 May 2025 — Hazy Hawk. "
                "[4] Guardio Labs, 26 Feb 2024 — SubdoMailing. [5] USENIX NSDI 2024, Friess et al. — "
                "<i>Cloudy with a Chance of Cyberattacks</i>. [6] watchTowr, 4 Feb 2025 — 8M requests, "
                "abandoned S3. [7] watchTowr, 11 Sep 2024 — .mobi WHOIS / RCE. [8] AWS, 24 Apr 2026 — "
                "S3 account regional namespaces. [9] AWS — bucket-owner-condition. [10] GitHub — Pages "
                "custom-domain verification. [11] HashiCorp — Terraform prevent_destroy. "
                "Additional tools: Cisco Umbrella top-1M; Internet Traffic Archive (NASA-HTTP); "
                "EdOverflow <i>can-i-take-over-xyz</i>.", small)]

doc.build(E)
print("PDF written:", OUT, os.path.getsize(OUT), "bytes")
