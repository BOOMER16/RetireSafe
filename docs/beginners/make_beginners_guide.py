"""Build the RetireSafe Beginner's Guide PDF (fundamentals + core concepts).

Run:  python3 docs/beginners/make_beginners_guide.py
Out:  RetireSafe_Beginners_Guide.pdf at the repo root.
"""
import os

import matplotlib
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, Image, KeepTogether,
                                ListFlowable, ListItem, PageBreak, PageTemplate, Paragraph,
                                Preformatted, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FIG = os.path.join(ROOT, "testbeds", "figs")
OUT = os.path.join(ROOT, "RetireSafe_Beginners_Guide.pdf")

# ---------- fonts (DejaVu ships with matplotlib, so this works anywhere) ----------
FD = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
for name, f in [("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"),
                ("DV-I", "DejaVuSans-Oblique.ttf"), ("DV-BI", "DejaVuSans-BoldOblique.ttf"),
                ("DVM", "DejaVuSansMono.ttf")]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FD, f)))
addMapping("DV", 0, 0, "DV"); addMapping("DV", 1, 0, "DV-B")
addMapping("DV", 0, 1, "DV-I"); addMapping("DV", 1, 1, "DV-BI")

INK = colors.HexColor("#1b2430"); MUT = colors.HexColor("#5b6775")
ACC = colors.HexColor("#c23b22"); ACC2 = colors.HexColor("#2f6f8f")
LINE = colors.HexColor("#c9d1d9"); BG = colors.HexColor("#f4f1ec")
TIP = colors.HexColor("#e8f1f5"); WARN = colors.HexColor("#fbeae6"); OK = colors.HexColor("#e9f3ea")


def S(name, **kw):
    base = dict(fontName="DV", fontSize=9.4, leading=14, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)


body = S("body", alignment=TA_JUSTIFY, spaceAfter=6)
bl = S("bl", alignment=TA_LEFT, spaceAfter=2)
H1 = S("H1", fontName="DV-B", fontSize=17, leading=21, spaceBefore=2, spaceAfter=4)
H2 = S("H2", fontName="DV-B", fontSize=11.5, leading=15, textColor=ACC, spaceBefore=9, spaceAfter=3)
H3 = S("H3", fontName="DV-B", fontSize=9.8, leading=13, textColor=ACC2, spaceBefore=6, spaceAfter=2)
kick = S("kick", fontName="DV-B", fontSize=7.5, leading=10, textColor=ACC, spaceAfter=1)
small = S("small", fontSize=7.8, leading=10.5, textColor=MUT)
cap = S("cap", fontName="DV-I", fontSize=7.6, leading=10, textColor=MUT, spaceAfter=8)
cell = S("cell", fontSize=8, leading=10.6)
cellb = S("cellb", fontName="DV-B", fontSize=8, leading=10.6, textColor=colors.white)
code = S("code", fontName="DVM", fontSize=7.8, leading=10.4, textColor=INK)
toc1 = S("toc1", fontName="DV-B", fontSize=9.5, leading=14, leftIndent=0)
toc2 = S("toc2", fontSize=8.8, leading=12.5, leftIndent=12, textColor=MUT)


class Doc(BaseDocTemplate):
    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("H1", "H2"):
            lvl = 0 if f.style.name == "H1" else 1
            key = "h%d" % id(f)
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (lvl, f.getPlainText(), self.page, key))


def page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK); canvas.rect(0, 0, A4[0], 6 * mm, fill=1, stroke=0)
    canvas.setFont("DV", 7); canvas.setFillColor(colors.white)
    canvas.drawString(18 * mm, 2.2 * mm, "RETIRESAFE  ·  BEGINNER'S GUIDE")
    canvas.drawRightString(A4[0] - 18 * mm, 2.2 * mm, "page %d" % doc.page)
    canvas.restoreState()


doc = Doc(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm,
          bottomMargin=12 * mm, title="RetireSafe Beginner's Guide",
          author="RetireSafe team", subject="Fundamentals and core concepts")
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin,
                                                         doc.width, doc.height)], onPage=page)])
W = doc.width


# ---------- building blocks ----------
def P(t, st=body):
    return Paragraph(t, st)


def rule(c=LINE, w=0.8):
    return HRFlowable(width="100%", thickness=w, color=c, spaceBefore=2, spaceAfter=6)


def bullets(items):
    return ListFlowable([ListItem(P(x, bl), leftIndent=10, value="•") for x in items],
                        bulletType="bullet", start="•", leftIndent=8, spaceAfter=4)


def box(title, text, bg=TIP, edge=ACC2):
    inner = [P(f"<b>{title}</b>", S("bt", fontName="DV-B", fontSize=8.6, leading=12, textColor=edge))]
    inner += [P(x, S("bx", fontSize=8.8, leading=12.8, spaceAfter=2)) for x in
              (text if isinstance(text, list) else [text])]
    t = Table([[inner]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg),
                           ("LINEBEFORE", (0, 0), (0, -1), 3, edge),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([Spacer(1, 2), t, Spacer(1, 6)])


def key(text):
    return box("Key idea", text, TIP, ACC2)


def warn(text):
    return box("Watch out", text, WARN, ACC)


def example(text):
    return box("Example", text, OK, colors.HexColor("#3c7a46"))


def tbl(rows, widths, fs=8):
    data = [[P(c, cellb) for c in rows[0]]] + [[P(c, cell) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), INK), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINE),
                           ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]))
    return KeepTogether([t, Spacer(1, 6)])


def pre(text):
    t = Table([[Preformatted(text.strip("\n"), code)]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BG), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([t, Spacer(1, 6)])


def flow(steps, h=34, fills=None, fs=7.2):
    """Horizontal box-and-arrow diagram. steps: list of 'TITLE\\nline2\\nline3'."""
    n = len(steps); gap = 14; bw = (W - gap * (n - 1)) / n
    d = Drawing(W, h + 6)
    for i, s in enumerate(steps):
        x = i * (bw + gap)
        fill = (fills[i] if fills else BG)
        d.add(Rect(x, 3, bw, h, fillColor=fill, strokeColor=MUT, strokeWidth=0.6, rx=3, ry=3))
        lines = s.split("\n")
        top = 3 + h / 2 + (len(lines) - 1) * (fs + 1.5) / 2 - fs / 3
        for j, ln in enumerate(lines):
            d.add(String(x + bw / 2, top - j * (fs + 1.5), ln, fontName="DV-B" if j == 0 else "DV",
                         fontSize=fs, fillColor=INK, textAnchor="middle"))
        if i < n - 1:
            ax = x + bw + 2; ay = 3 + h / 2
            d.add(Line(ax, ay, ax + gap - 5, ay, strokeColor=ACC, strokeWidth=1.2))
            d.add(Polygon([ax + gap - 4, ay, ax + gap - 8, ay + 3, ax + gap - 8, ay - 3],
                          fillColor=ACC, strokeColor=ACC))
    return KeepTogether([d, Spacer(1, 4)])


def fig(name, w, h, caption):
    return KeepTogether([Image(os.path.join(FIG, name), width=w, height=h), P(caption, cap)])


E = []
# =====================================================================================
# COVER
# =====================================================================================
E += [Spacer(1, 22 * mm), P("HACKER SPRINT / MANIPAL BENGALURU", kick),
      P("RetireSafe", S("t", fontName="DV-B", fontSize=36, leading=40)),
      P("The Beginner's Guide", S("t2", fontName="DV-B", fontSize=20, leading=24, textColor=ACC)),
      Spacer(1, 3 * mm),
      P("Everything you need to understand the project from zero: how the internet finds things, "
        "how cloud resources get their names, how a deleted resource can be taken over, how email "
        "trust works, what Terraform and access logs are, the statistics we use, what our "
        "research found, and how RetireSafe fits it all together.",
        S("lead", fontSize=11, leading=16, textColor=MUT)),
      Spacer(1, 6 * mm), rule(ACC, 2),
      tbl([["If you are…", "Read these first"],
           ["New to networking", "Part B (fundamentals), then the glossary at the end"],
           ["Comfortable with DNS / cloud", "Part C (core concepts) and Part D (the maths)"],
           ["Preparing the pitch", "§1, §10–12, Part E (our findings), the FAQ"],
           ["Writing code for the demo", "§12 (architecture), §21 (running the code)"]],
          [55 * mm, W - 55 * mm]),
      Spacer(1, 4 * mm),
      P("No prior security knowledge is assumed. Every technical term is explained when it first "
        "appears and again in the glossary. Numbers quoted from our own research come from real "
        "data and are reproducible from the project repository.", small),
      PageBreak()]

toc = TableOfContents(); toc.levelStyles = [toc1, toc2]; toc.dotsMinLevel = 0
E += [P("Contents", S("ct", fontName="DV-B", fontSize=17, leading=21, spaceAfter=8)), toc, PageBreak()]

# =====================================================================================
# PART A
# =====================================================================================
E += [P("PART A · THE BIG PICTURE", kick), P("1. The project in one page", H1), rule(ACC, 1.5),
      P("<b>The problem.</b> Companies constantly create and delete things in the cloud: storage "
        "buckets, web apps, temporary event websites. Deleting the <i>thing</i> is easy. But other "
        "systems still hold the thing's <i>address</i>: a DNS record, a link in some code, a line in "
        "an email-security setting. If that address can be re-registered by a stranger after the "
        "deletion, the stranger inherits all the trust and traffic that still flows to it, often "
        "under the original company's own domain name."),
      P("<b>The user.</b> A platform or cloud engineer who is about to delete or migrate a resource, "
        "supported by the security team."),
      P("<b>The decision we help with.</b> <i>What must be removed, migrated or protected before "
        "this resource can safely be released?</i>"),
      P("<b>What RetireSafe does.</b> Before a deletion happens, it gathers evidence from every "
        "place that trust can hide (DNS, code, infrastructure files, email settings, traffic logs), "
        "checks whether anyone else could re-claim the name, and gives a clear verdict with "
        "reasons: <b>cleared</b>, <b>blocked</b> (plus a fix), <b>retain the name</b>, or "
        "<b>unknown</b> (plus what evidence is missing). It never just says “safe”."),
      key("Deleting infrastructure does not automatically delete the trust placed in its address. "
          "RetireSafe makes retirement an evidence-based decision instead of a guess."),
      P("<b>Why it matters (real incidents).</b> Attackers have taken over abandoned addresses "
        "belonging to the US CDC, a French government Olympics website, big consulting firms and "
        "universities. One peer-reviewed study (NSDI 2024) counted 20,904 hijacked cloud "
        "resources. These cases are summarised in §19."),
      P("<b>One-sentence pitch.</b> <i>“RetireSafe is a pre-flight check for deleting cloud "
        "resources: it finds the references that would survive the deletion, tells you whether "
        "someone could hijack them, and blocks the deletion with a precise fix until it is "
        "safe.”</i>"),
      PageBreak()]

E += [P("2. A story: the event website", H1), rule(ACC, 1.5),
      P("This invented example (it is <i>not</i> a real incident) shows the whole problem. Keep it "
        "in mind; every later concept maps back onto it."),
      flow(["01 CREATE\nteam builds an app\nfor an event",
            "02 CONNECT\nevent.example.com\npoints to the app",
            "03 RETIRE\napp deleted after\nthe event",
            "04 RECLAIM\nstranger registers\nthe freed app name",
            "05 INHERIT\nvisitors to event.example.com\nnow see stranger's content"],
           h=46, fills=[BG, BG, BG, WARN, WARN], fs=7),
      P("Step by step:"),
      bullets(["<b>Create.</b> The team creates a cloud web app. The cloud provider gives it a name "
               "like <font face='DVM'>event-app.azurewebsites.net</font>.",
               "<b>Connect.</b> To get a nice address, they add a DNS record saying "
               "<font face='DVM'>event.example.com</font> is an alias of "
               "<font face='DVM'>event-app.azurewebsites.net</font>. Posters, emails and "
               "partner websites start linking to <font face='DVM'>event.example.com</font>.",
               "<b>Retire.</b> After the event, someone deletes the app to save money. Nobody "
               "deletes the DNS alias, because a different team manages DNS.",
               "<b>Reclaim.</b> The name <font face='DVM'>event-app</font> is now free in the "
               "provider's system. An attacker creates a new app with exactly that name in "
               "<i>their own</i> account.",
               "<b>Inherit.</b> The alias still points to that name, so everyone visiting "
               "<font face='DVM'>event.example.com</font> now gets the attacker's site, under "
               "<font face='DVM'>example.com</font>'s trusted name."]),
      warn("The company still owns example.com. What it lost is control of the thing "
           "event.example.com points to. That gap between the trusted name and the resource is "
           "the vulnerability."),
      P("The same pattern happens without any custom domain: an old app or script can contain a "
        "direct URL to a storage bucket that was deleted. If the bucket name is re-created by a "
        "stranger, the old app downloads the stranger's files."),
      PageBreak()]

# =====================================================================================
# PART B
# =====================================================================================
E += [P("PART B · FUNDAMENTALS", kick), P("3. How the internet finds things: DNS", H1), rule(ACC, 1.5),
      P("Computers talk to each other using numeric <b>IP addresses</b> (like "
        "<font face='DVM'>93.184.215.14</font>). Humans use names (like "
        "<font face='DVM'>example.com</font>). The <b>Domain Name System (DNS)</b> is the "
        "internet's phone book that turns names into addresses."),
      P("Names are hierarchical", H2),
      P("Read a name right to left: <font face='DVM'>shop.event.example.com</font> → top-level "
        "domain (TLD) <font face='DVM'>com</font> → domain <font face='DVM'>example.com</font> → "
        "subdomain <font face='DVM'>event.example.com</font> → sub-subdomain "
        "<font face='DVM'>shop.event.example.com</font>. Whoever controls "
        "<font face='DVM'>example.com</font>'s DNS can create any number of subdomains for free."),
      P("DNS record types you need", H2),
      tbl([["Type", "What it says", "Example"],
           ["A / AAAA", "This name lives at this IPv4 / IPv6 address", "example.com → 93.184.215.14"],
           ["CNAME", "This name is an <b>alias</b> of another name; go look that one up instead",
            "event.example.com → event-app.azurewebsites.net"],
           ["NS", "Which servers are in charge of this domain's records", "example.com → ns1.dnshost.net"],
           ["TXT", "Free text; used for SPF email rules and ownership proofs",
            "v=spf1 include:_spf.mailer.com -all"]],
          [17 * mm, 80 * mm, W - 97 * mm]),
      P("How a lookup works", H2),
      P("Your computer asks a <b>resolver</b> (usually run by your ISP, company or a service like "
        "Cisco Umbrella). The resolver asks the <b>authoritative</b> servers for the domain and "
        "follows any aliases until it reaches an address:"),
      flow(["Browser\nwants event.example.com", "Resolver\nasks example.com's DNS",
            "CNAME\n→ event-app.azurewebsites.net", "Provider DNS\n→ IP of the app",
            "Browser\nconnects to that IP"], h=32, fs=6.9),
      P("Following alias after alias is called walking the <b>CNAME chain</b>. Our first test bed "
        "(TB1) does exactly this for 16,000 real names."),
      P("NXDOMAIN, TTL and friends", H2),
      tbl([["Term", "Meaning"],
           ["NXDOMAIN", "“Non-existent domain”: the DNS answer for a name that does not exist. A "
            "CNAME whose target returns NXDOMAIN is a <b>dangling</b> (broken) alias."],
           ["TTL", "Time-to-live: how many seconds resolvers may cache an answer. Old answers can "
            "linger for that long after you change a record."],
           ["Registrar / registry", "You rent a domain like example.com from a registrar for a "
            "period. If you stop paying, it <b>expires</b> and anyone can register it."],
           ["Zone / zone export", "All the DNS records of a domain. A zone export is a file "
            "listing them; RetireSafe reads it to find references."]],
          [32 * mm, W - 32 * mm]),
      P("Registrable domain and the Public Suffix List", H2),
      P("Some suffixes are shared by many owners: <font face='DVM'>co.uk</font>, "
        "<font face='DVM'>github.io</font>, <font face='DVM'>s3.amazonaws.com</font>. The "
        "<b>Public Suffix List</b> records these. The part a single owner can actually register is "
        "the <b>registrable domain</b> (also called eTLD+1): for "
        "<font face='DVM'>a.b.example.co.uk</font> it is <font face='DVM'>example.co.uk</font>. We "
        "use it to ask “is the <i>whole domain</i> unregistered?” (the worst case, because anyone "
        "can buy it)."),
      key("DNS records are just pointers. Nothing in DNS checks that the thing being pointed at "
          "still belongs to you."),
      PageBreak()]

E += [P("4. Cloud resources and their names", H1), rule(ACC, 1.5),
      P("A <b>cloud resource</b> is anything you rent from a cloud provider: a storage bucket, a "
        "web app, a load balancer, a database. Many of them get a <b>public name</b> inside the "
        "provider's own domain, and that name is what DNS aliases and code point to."),
      tbl([["Service", "Name looks like", "Who can own that name"],
           ["AWS S3 bucket (storage)", "my-bucket.s3.amazonaws.com", "Historically: any AWS account, "
            "first come first served, across all of AWS (a <b>global namespace</b>)"],
           ["AWS S3 static website", "my-bucket.s3-website-us-east-1.amazonaws.com", "Same. For a "
            "custom domain, the bucket name must equal the hostname, e.g. bucket "
            "<font face='DVM'>assets.example.com</font>"],
           ["Azure App Service", "my-app.azurewebsites.net", "Any Azure customer, while the name "
            "is free"],
           ["AWS Elastic Beanstalk", "my-env.us-east-1.elasticbeanstalk.com", "Any AWS customer, while "
            "the name is free"],
           ["GitHub Pages", "user.github.io + custom domain", "Protected if you verify the domain"]],
          [36 * mm, 58 * mm, W - 94 * mm]),
      P("What “released” and “reassignable” mean", H2),
      P("When you delete a resource, its name is <b>released</b>. If the provider lets someone else "
        "create a resource with the same name, the name is <b>reassignable</b> (or "
        "<b>reclaimable</b>). That is the attacker's entry point. Some names are reserved for a "
        "while or protected by verification; others become available to anyone."),
      P("How we check whether an S3 bucket exists", H2),
      P("We ask the S3 web API for the bucket and read the answer. This is read-only: it does not "
        "create anything."),
      tbl([["S3 answer (HTTP status)", "Meaning for us"],
           ["404 with error code <b>NoSuchBucket</b>", "The bucket does not exist. In the global "
            "namespace anyone could create it, so it is <b>reclaimable</b>"],
           ["403 Forbidden", "It exists but is private (someone owns it)"],
           ["301 Moved Permanently", "It exists, in a different AWS region"],
           ["200 OK", "It exists and is publicly readable"]],
          [55 * mm, W - 55 * mm]),
      P("New protection: account regional namespaces (2026)", H2),
      P("According to AWS (April 2026), buckets can now be created in an <b>account regional "
        "namespace</b> that other AWS accounts cannot reclaim. This removes the takeover risk for "
        "<i>new</i> buckets in that namespace. Older buckets in the global namespace remain at risk "
        "and cannot simply be renamed, so they need careful migration. RetireSafe must recognise "
        "which namespace a bucket is in."),
      warn("“The bucket is gone” and “the name is safe” are different statements. A deleted "
           "global-namespace bucket is exactly what an attacker wants."),
      PageBreak()]

E += [P("5. Subdomain takeover and dangling references", H1), rule(ACC, 1.5),
      P("<b>Dangling reference:</b> any pointer (DNS record, URL in code, email rule, config) that "
        "still points at a resource you no longer control. <b>Subdomain takeover:</b> an attacker "
        "claims the resource behind a dangling DNS record and so controls what is served on your "
        "subdomain."),
      P("Why this is so powerful for an attacker", H2),
      bullets(["<b>Borrowed reputation.</b> Content appears under <font face='DVM'>"
               "something.yourcompany.com</font>, which people, spam filters and search engines trust.",
               "<b>Phishing and scams.</b> Fake login pages and fake CAPTCHAs on a real company "
               "domain. In the CDC case, visitors were sent to scams and scareware.",
               "<b>Valid HTTPS.</b> Certificate authorities that use domain validation issue a "
               "certificate to whoever can serve a challenge file on that hostname. The hijacker "
               "controls that content, so the browser can show the padlock.",
               "<b>Cookies.</b> Cookies a site sets for the whole parent domain are also sent to "
               "every subdomain, so a hijacked subdomain may receive visitors' session cookies. "
               "The NSDI study reported stolen cookies among the abuses.",
               "<b>Search-engine spam (SEO).</b> In the NSDI study, 75% of the observed abuse was "
               "blackhat SEO: using the trusted domain to push spam pages up in search results.",
               "<b>Malware delivery.</b> If software downloads scripts, updates or packages from "
               "the reclaimed address, it may fetch the attacker's files."]),
      P("References are not only DNS", H2),
      tbl([["Where", "Dangling reference looks like"],
           ["DNS", "CNAME to a deleted app or bucket"],
           ["Web page / JS code", "&lt;script src=\"https://old-assets.s3.amazonaws.com/lib.js\"&gt;"],
           ["Package / update config", "an APT source or download URL pointing at a deleted bucket"],
           ["Email (SPF)", "include: of a domain that has expired (see §6)"],
           ["Identity / validation", "an old WHOIS or validation server name that clients still use"]],
          [42 * mm, W - 42 * mm]),
      P("watchTowr's 2025 research re-registered about 150 abandoned S3 buckets and received more "
        "than 8 million requests in two months, including for a file whose documentation link had "
        "been removed in 2015. <b>Fixing the documentation did not stop the clients.</b>"),
      warn("Integrity checks can still save you. If the consumer verifies a signature, a hash "
           "(Subresource Integrity), or the bucket's owner account, the attacker's replacement is "
           "rejected even if the name was reclaimed. That is condition 5 in §10."),
      PageBreak()]

E += [P("6. Email trust: SPF in five minutes", H1), rule(ACC, 1.5),
      P("Anyone can write any “From” address on an email, so receivers check whether the sending "
        "server is authorised. <b>SPF (Sender Policy Framework)</b> is a TXT record in DNS listing "
        "which servers may send mail for a domain:"),
      pre("example.com.  TXT  \"v=spf1 include:_spf.mailer-co.com ip4:203.0.113.5 -all\"\n\n"
          "v=spf1                   this is an SPF record\n"
          "include:_spf.mailer-co.com   also trust every server mailer-co.com lists\n"
          "ip4:203.0.113.5          trust this one address\n"
          "-all                     reject everything else"),
      P("The danger is in <b>include:</b>. It hands part of your authority to <i>another</i> "
        "domain. If that other domain expires and an attacker registers it, the attacker can list "
        "their own servers, and mail they send “from” you can pass SPF."),
      example("Guardio's SubdoMailing research (2024) found exactly this: an SPF rule at Swatch "
              "still included a long-abandoned domain that had been re-registered, and an MSN "
              "subdomain aliased to a domain re-registered in 2022. Spoofed email passed SPF. "
              "Guardio (vendor figure) reported more than 8,000 affected domains."),
      P("SPF is one of three related checks. <b>DKIM</b> adds a cryptographic signature to messages, "
        "and <b>DMARC</b> tells receivers what to do when checks fail and requires them to align "
        "with the visible From domain. So an SPF pass alone does not defeat every check, but it "
        "helps an attacker a lot. SPF also has a limit of 10 DNS lookups per evaluation."),
      key("Retiring a domain or a mail service must include cleaning up every SPF include: that "
          "points at it. This is on RetireSafe's roadmap, not in the first demo."),
      Spacer(1, 4),
      P("7. Infrastructure as Code: Terraform basics", H1), rule(ACC, 1.5),
      P("Modern teams describe their cloud resources in text files instead of clicking in a "
        "console. <b>Terraform</b> is the most common tool. You write what you want; Terraform "
        "works out what to create, change or delete."),
      pre('resource "aws_s3_bucket" "event_assets" {\n'
          '  bucket = "event-assets-2026"\n\n'
          '  lifecycle {\n'
          '    prevent_destroy = true   # refuse any plan that would delete this\n'
          '  }\n'
          '}'),
      tbl([["Concept", "Meaning"],
           ["state", "Terraform's record of which real resources it manages"],
           ["terraform plan", "Shows what would change: create (+), update (~), destroy (−)"],
           ["terraform apply / destroy", "Makes the changes / deletes resources"],
           ["terraform show -json", "Machine-readable plan. RetireSafe reads this to learn what is "
            "about to be deleted"],
           ["prevent_destroy", "Guard that blocks destructive plans <i>while configured</i>. If "
            "someone deletes the whole resource block, the guard goes with it, and it knows "
            "nothing about outside consumers"]],
          [40 * mm, W - 40 * mm]),
      PageBreak()]

E += [P("8. Web access logs", H1), rule(ACC, 1.5),
      P("Every time a web server answers a request it can write one line to an <b>access log</b>. "
        "Logs are how we learn whether anyone is still using a resource. Here is a real line from "
        "the NASA 1995 log we used:"),
      pre('199.72.81.55 - - [01/Jul/1995:00:00:01 -0400] "GET /history/apollo/ HTTP/1.0" 200 6245'),
      tbl([["Piece", "Value", "Meaning"],
           ["client", "199.72.81.55", "Who asked (an IP address or hostname)"],
           ["ident, user", "- -", "Usually empty"],
           ["timestamp", "01/Jul/1995:00:00:01 -0400", "When (with time-zone offset)"],
           ["request", "GET /history/apollo/ HTTP/1.0", "Method, <b>resource path</b>, protocol"],
           ["status", "200", "HTTP result: 200 OK, 304 not modified, 404 not found…"],
           ["bytes", "6245", "Size of the response"]],
          [24 * mm, 56 * mm, W - 80 * mm]),
      P("Words we use about traffic", H2),
      tbl([["Term", "Meaning"],
           ["resource", "One URL path, e.g. /shuttle/countdown/count.gif"],
           ["consumer / client", "A person or program that requests a resource"],
           ["distinct clients", "How many different requesters, not how many requests"],
           ["/24 network", "IPv4 addresses sharing their first three numbers (e.g. 199.72.81.x). "
            "A rough proxy for “same organisation or ISP block”"],
           ["external client", "A client from outside the organisation (here: not ending in "
            "nasa.gov). The deleting team usually cannot contact them"],
           ["recency window", "The last few days of activity, which is what a dashboard shows"]],
          [34 * mm, W - 34 * mm]),
      warn("Request counts are not victim counts. 8 million requests to a reclaimed bucket prove "
           "that a dependency survives; they do not prove 8 million infections."),
      P("9. Protections that already exist", H1), rule(ACC, 1.5),
      P("This problem is well known, and providers have built defences. RetireSafe's job is to "
        "<b>recognise</b> them, not ignore them, so it does not raise false alarms."),
      tbl([["Protection", "What it does", "Limit"],
           ["S3 account regional namespace", "Other accounts cannot reclaim those bucket names",
            "Only for buckets created there; legacy buckets need migration"],
           ["S3 bucket owner condition", "Requests can say “only if owned by account X”; a "
            "stranger's bucket is rejected", "Only helps if the <i>consumer</i> sends it"],
           ["Azure protections", "Dangling-DNS detection, alias records, domain verification",
            "Must be configured"],
           ["GitHub Pages verification", "Verified custom domains are protected from takeover",
            "Within GitHub's documented scope"],
           ["Terraform prevent_destroy", "Blocks deletion plans", "Lost if the resource block "
            "is removed; no knowledge of consumers"]],
          [38 * mm, 70 * mm, W - 108 * mm]),
      key("The innovation is not discovering subdomain takeover (that's known). It is "
          "coordinating a safe retirement across DNS, code, infrastructure, traffic and these "
          "protections, with evidence."),
      PageBreak()]

# =====================================================================================
# PART C
# =====================================================================================
E += [P("PART C · CORE CONCEPTS OF RETIRESAFE", kick), P("10. The five conditions for a takeover", H1),
      rule(ACC, 1.5),
      P("A broken link alone is <b>not</b> a vulnerability. A takeover needs <b>all five</b> of these "
        "to be true at once. If we can prove even one is false, that path is safe."),
      tbl([["#", "Condition", "Question to ask", "In the event-website story"],
           ["1", "Resource released", "Will the resource be deleted?", "Yes, the app is deleted"],
           ["2", "Name reassignable", "Can someone else then create a resource with that name?",
            "Yes, azurewebsites.net names are first come, first served"],
           ["3", "Reference survives", "Does a DNS record, code link or rule still point there?",
            "Yes, the CNAME was never removed"],
           ["4", "Consumer remains", "Does anyone or anything still use the reference?",
            "Yes, posters and partner sites still link to it"],
           ["5", "Controls permit impact", "Would the consumer accept a stranger's content?",
            "Yes, browsers just load whatever is served"]],
          [7 * mm, 31 * mm, 64 * mm, W - 102 * mm]),
      pre("takeover possible  =  C1  AND  C2  AND  C3  AND  C4  AND  C5"),
      P("This turns a vague worry into a checklist. To make a deletion safe you only need to break "
        "<b>one</b> condition, and RetireSafe picks the cheapest or safest one: remove the reference "
        "(C3), keep the name (C1), move to a protected namespace (C2), or add an owner/integrity "
        "check (C5)."),
      P("11. The evidence ladder and the four verdicts", H1), rule(ACC, 1.5),
      P("Not every finding is equally serious. We place each one on a ladder and never claim a rung "
        "we have not shown:"),
      flow(["STALE REFERENCE\npoints at something\nthat no longer exists",
            "RECLAIMABLE ENDPOINT\nsomeone else could\nclaim that name",
            "DEMONSTRATED IMPACT\na consumer would\naccept the replacement"],
           h=40, fills=[BG, WARN, colors.HexColor("#f3c9c0")], fs=7.4),
      tbl([["Verdict", "When", "What the engineer gets"],
           ["CLEARED", "At least one condition is provably false for every surviving reference",
            "An evidence record saying what was checked"],
           ["BLOCKED", "Every condition that could be checked is true",
            "The exact reference(s), the reason, and a fix (patch)"],
           ["RETAIN NAME", "People or software still depend on it",
            "Advice to keep owning the name (a placeholder) instead of releasing it"],
           ["UNKNOWN", "Some condition could not be evaluated",
            "Which evidence is missing and how to get it"]],
          [26 * mm, 70 * mm, W - 96 * mm]),
      key("Saying “unknown” honestly is a feature. A tool that always answers “safe” or “unsafe” "
          "will be wrong in ways nobody notices."),
      PageBreak()]

E += [P("12. How RetireSafe works (architecture in plain words)", H1), rule(ACC, 1.5),
      P("Think of an airline pre-flight checklist: before take-off, several independent checks "
        "must pass, and any failure stops the plane with a specific reason. RetireSafe does the "
        "same before a deletion."),
      flow(["① COLLECT\nfind every\nreference", "② PROBE\ncould the name\nbe reclaimed?",
            "③ OBSERVE\nwho still uses it?\n(logs)", "④ FUSE\none evidence\ngraph",
            "⑤ DECIDE\nfive conditions\n+ risk score", "⑥ ACT\nblock / patch /\nretain / record"],
           h=44, fs=6.8),
      tbl([["Stage", "Inputs", "What it does", "Built on"],
           ["① Collect", "Terraform plan, DNS zone export, code repository, SPF records",
            "Lists every place that points to the resource being deleted", "new code"],
           ["② Probe", "Fingerprint catalogue, live checks", "Asks: does the target still exist? Could "
            "someone else claim it? Is a protection switched on?", "<b>TB1</b>"],
           ["③ Observe", "Access / CDN logs", "Measures how often it's used, how long a silence "
            "proves it's dead, how many outsiders depend on it", "<b>TB2, TB3</b>"],
           ["④ Fuse", "Everything above", "Builds a graph: Resource → Name → Reference → Consumer, "
            "each link with its evidence", "new code"],
           ["⑤ Decide", "The graph", "Evaluates the five conditions; scores risk; picks a verdict",
            "maths in Part D"],
           ["⑥ Act", "The verdict", "Blocks the deletion with a reason, proposes a patch, writes an "
            "evidence record", "new code"]],
          [18 * mm, 42 * mm, 82 * mm, W - 142 * mm]),
      P("What a blocked result could look like", H2),
      pre("BLOCKED  aws_s3_bucket.event_assets   (legacy global namespace -> reclaimable)\n"
          "  <- dns   assets.event.example.com CNAME event-assets.s3.amazonaws.com  [zone.txt:42]\n"
          "  <- code  static/js/app.js:118  \"https://event-assets.s3.amazonaws.com/lib.js\"\n"
          "  consumers: 1,204 clients in 30 days, 97% external, last seen 2 days ago\n"
          "  fix: remove CNAME, rewrite URL, keep bucket (prevent_destroy) for 63 more days"),
      P("<i>This output is an illustration of the planned format, not a real scan.</i>", small),
      P("The fingerprint catalogue", H2),
      P("To know which provider a CNAME points to and how that provider behaves after deletion, we "
        "use the community catalogue <b>can-i-take-over-xyz</b>. It lists 76 services with the "
        "name pattern to match (e.g. <font face='DVM'>azurewebsites.net</font>), the tell-tale sign "
        "of an unclaimed resource (NXDOMAIN or a specific error page), and whether takeover is "
        "possible (36 vulnerable, 26 not vulnerable, 14 edge cases)."),
      PageBreak()]

# =====================================================================================
# PART D
# =====================================================================================
E += [P("PART D · THE MATHS, GENTLY", kick), P("13. Rates, silence and the Poisson idea", H1),
      rule(ACC, 1.5),
      P("The hardest question in retirement is: <i>“Nobody has used this for a while. Is it really "
        "dead, or just quiet?”</i> Statistics lets us answer with a number instead of a feeling."),
      P("Rate", H2),
      P("The <b>rate</b> λ (lambda) is the average number of requests per day. If a resource got "
        "n = 30 requests in T = 60 days, our best estimate is <b>λ = n / T = 0.5 per day</b>. "
        "(This simple estimate is called the maximum-likelihood estimate.)"),
      P("The Poisson model", H2),
      P("A <b>Poisson process</b> is the simplest model of random events that happen independently "
        "at a steady average rate, like raindrops on a window. Under that model, the probability "
        "of seeing <b>zero</b> events in a window of D days is:"),
      pre("P(no requests in D days)  =  e^(−λ·D)          (e ≈ 2.718)"),
      example("A resource with λ = 0.5 requests/day stays silent for 10 days. "
              "P = e^(−0.5×10) = e^(−5) ≈ 0.0067, about 0.7%. So 10 days of silence is strong "
              "evidence that its users are really gone. For a resource with λ = 0.05/day, "
              "e^(−0.5) ≈ 0.61: a 61% chance of 10 silent days even if it is alive, so that "
              "silence proves almost nothing."),
      P("The quarantine window D*", H2),
      P("Turn it around: how long must we wait so that silence would only happen by chance 1% of "
        "the time (α = 0.01)? Solve e^(−λD) = α:"),
      pre("D*  =  −ln(α) / λ   =   4.605 / λ      (for α = 1%)"),
      tbl([["Rate λ", "Means", "D* (99% sure it's dead)"],
           ["10 / day", "busy", "0.46 days (≈ 11 hours)"],
           ["1 / day", "daily", "4.6 days"],
           ["0.25 / day", "about weekly-ish", "18 days"],
           ["0.1 / day", "every 10 days", "46 days"],
           ["1 / 30 days", "monthly", "138 days"]],
          [32 * mm, 50 * mm, W - 82 * mm]),
      key("Rare resources need long quarantines. One global rule such as “delete after 30 idle days” "
          "is far too short for anything used about once a month."),
      warn("You can't measure what your window can't see. If your log covers 27 days, a yearly "
           "job is invisible. RetireSafe reports this as UNKNOWN instead of guessing."),
      PageBreak()]

E += [P("14. Uncertainty and confidence intervals", H1), rule(ACC, 1.5),
      P("Any number estimated from data is uncertain, especially when it is based on few events. "
        "A <b>95% confidence interval</b> gives a range that, by a standard statistical procedure, "
        "contains the true value in 95% of repeated experiments."),
      P("Wilson interval (for proportions)", H2),
      P("For “k successes out of n” the naive interval p ± 1.96·√(p(1−p)/n) behaves badly when k is "
        "small (it can even go below zero). The <b>Wilson interval</b> fixes this:"),
      pre("[ p + z²/2n  ±  z·√( p(1−p)/n + z²/4n² ) ]  /  (1 + z²/n)        z = 1.96 for 95%"),
      example("TB1 found 5 reclaimable hostnames out of 16,000. p = 0.031%. Wilson 95% interval = "
              "0.013% to 0.073%. So we report “roughly 1 to 7 in 10,000”, not a falsely precise "
              "0.03125%."),
      P("For rates, RetireSafe will use the <i>pessimistic</i> end of the range (a lower rate gives "
        "a longer, safer quarantine). That is how uncertainty makes the tool more careful rather "
        "than less."),
      P("15. Base rates: why we confirm before we alarm", H1), rule(ACC, 1.5),
      P("When something is rare, even a good detector produces mostly false alarms. This is "
        "<b>Bayes' rule</b>:"),
      pre("P(real | flagged) = sens·π / ( sens·π + fpr·(1−π) )\n\n"
          "π    = base rate (how common the real thing is)\n"
          "sens = sensitivity (share of real cases the detector catches)\n"
          "fpr  = false-positive rate (share of harmless cases it wrongly flags)"),
      example(["Our measured base rate is about π = 0.0003 (3 in 10,000). Take a decent detector "
               "with sens = 95% and fpr = 1%:",
               "P(real | flagged) = 0.95×0.0003 / (0.95×0.0003 + 0.01×0.9997) ≈ <b>2.8%</b>. "
               "About 35 out of 36 alarms would be false!",
               "Add a live confirmation probe that lowers fpr to 0.01%: the same formula gives "
               "≈ <b>74%</b>. This is why RetireSafe always confirms (e.g. checks “NoSuchBucket” "
               "live) before blocking."]),
      PageBreak()]

E += [P("16. Calibration: can we trust the probabilities?", H1), rule(ACC, 1.5),
      P("A model is <b>calibrated</b> if, among all the times it says “30% chance”, the event "
        "really happens about 30% of the time. A model can rank things correctly and still be "
        "badly calibrated."),
      P("How we test it: hold-out validation", H2),
      P("Hide the end of the data. Fit the model on the beginning (days 0–24), make predictions "
        "for the hidden part (days 24–27.6), then compare with what really happened. Never test on "
        "the data you trained on."),
      P("Reliability diagram", H2),
      P("Group predictions into bins (deciles), and plot the average predicted probability against "
        "the observed frequency. A perfectly calibrated model sits on the diagonal."),
      fig("fig3_tb2_rel.png", 62 * mm, 58 * mm,
          "Our real result (TB2): every point lies below the diagonal, so the simple Poisson model "
          "predicted more returns than actually happened (1,161 vs 783, a factor of 1.48). The "
          "points still go up, so the model ranks resources well."),
      P("Scores", H2),
      bullets(["<b>Brier score</b>: average of (predicted − actual)², where actual is 1 or 0. "
               "Lower is better. Predicting 0.8 for something that happened costs (0.8−1)² = 0.04; "
               "predicting 0.8 for something that didn't costs 0.64.",
               "<b>Expected calibration error (ECE)</b>: the average gap between the reliability "
               "points and the diagonal, weighted by bin size.",
               "<b>Isotonic regression</b>: a simple fix that learns a monotone mapping from the "
               "model's raw probability to an honest one using past data (proposed for RetireSafe)."]),
      P("17. Blast radius and the risk score", H1), rule(ACC, 1.5),
      P("<b>Blast radius</b> = who would break if we deleted this: the number of distinct clients, "
        "the number of /24 networks, and the <b>external share</b> e = external clients ÷ all "
        "clients. A resource used by 3 internal machines is very different from one used by 15,000 "
        "strangers."),
      P("RetireSafe combines everything into one score that mirrors the five conditions. Because "
        "all five must hold, the probabilities are <b>multiplied</b>:"),
      pre("R = P(C1) × P(C2) × P(C3) × P(C4) × P(C5) × Impact"),
      P("If any factor is 0 (provably false), R is 0 and that path is cleared. If a factor is "
        "unknown, it is kept as a range rather than guessed, which widens the range of R. The "
        "score is used to sort findings so the most dangerous are fixed first. The score and the "
        "isotonic fix are <i>proposed</i>; the quarantine, the calibration check and the blast "
        "radius were run on real data."),
      PageBreak()]

# =====================================================================================
# PART E
# =====================================================================================
E += [P("PART E · WHAT OUR RESEARCH FOUND", kick), P("18. Our three test beds in plain words", H1),
      rule(ACC, 1.5),
      P("A <b>test bed</b> is a small experiment that tries an idea on real data before building the "
        "product. All three used real public data, made only read-only requests, and published no "
        "third-party hostnames."),
      P("TB1: How common are hijackable leftovers?", H2),
      P("<b>What we did:</b> took 16,000 real hostnames from Cisco Umbrella's top-1M list (the 8,000 "
        "most popular plus 8,000 random ones), followed their CNAME chains, matched the targets "
        "against the fingerprint catalogue, and asked S3 whether matching buckets exist. "
        "<b>What we found:</b> <b>5 reclaimable hostnames, 0.031%</b> (95% CI 0.013–0.073%): 4 "
        "pointing at S3 buckets that no longer exist, 1 at a missing Azure endpoint. Less-popular "
        "sites looked worse than the top sites (0.25% vs 0.05% of hostnames with an alias), "
        "though the intervals overlap. <b>So what:</b> the danger is rare and buried, which is why "
        "it needs an automated tool, and that tool must confirm findings (see §15)."),

      P("TB2: How long is long enough?", H2),
      P("<b>What we did:</b> used NASA's real July 1995 web log (1.89 million requests, 7,133 "
        "resources) and computed each resource's quarantine D*. <b>What we found:</b> to be 99% "
        "sure, half the resources need <b>42 days</b> of silence and a third need <b>127 days</b>; "
        "33% were requested only once all month. The Poisson model ranked resources well but "
        "over-predicted returns by 1.48×. <b>So what:</b> no single idle timeout is safe; use "
        "per-resource quarantines, recalibrate, and say UNKNOWN when the log is too short."),

      KeepTogether([Table([[Image(os.path.join(FIG, "fig1_tb1.png"), width=W * 0.52, height=W * 0.52 * 73 / 165),
                            Image(os.path.join(FIG, "fig2_tb2_quar.png"), width=W * 0.46, height=W * 0.46 * 44 / 99)]],
                          colWidths=[W * 0.53, W * 0.47], style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE")]),
                    P("Left (TB1): almost every hostname resolves normally; only a handful reach the "
                      "reclaimable rung (log scale). Right (TB2): days of silence needed for 99% "
                      "confidence, by percentile.", cap)]),
      P("TB3: How much hidden dependence is behind an “idle” resource?", H2),
      P("<b>What we did:</b> looked at the NASA log the way a dashboard would, through the last 3 "
        "days only, and found 108 busy resources that looked dead. Then we counted everyone who had "
        "used them over the whole month. <b>What we found:</b> all 108 had outside users; "
        "<font face='DVM'>/shuttle/countdown/count.gif</font> had <b>0</b> recent hits but "
        "<b>15,054</b> distinct outside clients. (On a public site nearly everyone is external, so "
        "the striking part is the size, not the 100%.) <b>So what:</b> “looks unused to us” and "
        "“nobody depends on it” are very different; RetireSafe must look at history and outsiders, "
        "not just recent activity."),
      fig("fig4_tb3.png", 56 * mm, 53 * mm, "TB3: idle-looking resources and their hidden external users."),
      P("Planned but not yet run: an SPF dangling-include audit (TB4) and a scan of published "
        "software packages for S3 links (TB5).", small),
      PageBreak()]

E += [P("19. The real-world incidents: cheat sheet", H1), rule(ACC, 1.5),
      tbl([["Case", "When", "What happened", "Type of evidence"],
           ["CDC Azure endpoint", "Feb–Mar 2025", "A CDC subdomain aliased to an abandoned Azure app "
            "was used to send visitors to scams and scareware", "Observed malicious abuse "
            "(Infoblox)"],
           ["Hazy Hawk campaign", "Dec 2023 onward", "French government Olympics site (DNS left after "
            "the event), an oercommons S3 bucket, subdomains under Deloitte, EY, PwC, UC Berkeley, "
            "UCL and others", "Observed abuse, one campaign (Infoblox)"],
           ["SubdoMailing", "Disclosed Feb 2024", "Expired domains still referenced by MSN and Swatch "
            "DNS/SPF; spoofed mail passed SPF", "Observed campaign; 8,000+ domains is a vendor "
            "figure (Guardio)"],
           ["NSDI 2024 study", "Published 2024", "20,904 hijacked cloud resources; about ⅓ lasted more "
            "than 65 days; 75% blackhat SEO", "Peer-reviewed measurement"],
           ["Abandoned S3 buckets", "Feb 2025", "About 150 buckets re-registered by researchers; 8M+ "
            "requests in 2 months", "Researcher demonstration (watchTowr)"],
           [".mobi WHOIS", "Sep 2024", "Old WHOIS domain re-registered; 2.5M queries from 135,000+ "
            "systems; a CA accepted its answers for validation (stopped before a certificate was "
            "issued)", "Researcher demonstration (watchTowr)"]],
          [30 * mm, 24 * mm, 76 * mm, W - 130 * mm]),
      P("How to talk about the evidence honestly", H2),
      tbl([["Say", "Don't say"],
           ["Attackers have exploited forgotten references", "Every stale reference is exploitable"],
           ["A subdomain was hijacked", "The organisation was breached"],
           ["8 million requests reached reclaimed buckets", "8 million infections"],
           ["20,904 hijacked resources were found", "20,904 organisations were attacked"],
           ["Several examples belong to one campaign", "These are many independent campaigns"]],
          [W / 2, W / 2]),
      P("Suggested pitch order (from the brief): CDC (a concrete victim) → NSDI (scale) → watchTowr "
        "S3 (why DNS-only checks miss application dependencies) → our test beds → live demo of a "
        "blocked-then-cleared deletion.", small),
      PageBreak()]

# =====================================================================================
# PART F
# =====================================================================================
E += [P("PART F · PRACTICAL", kick), P("20. Ethics and responsible disclosure", H1), rule(ACC, 1.5),
      bullets(["<b>Read-only research.</b> Only look things up (DNS queries, reading public "
               "responses). Never create, claim or register a resource you found dangling.",
               "<b>Don't publish targets.</b> Report aggregate counts. Keep any list of real "
               "vulnerable hostnames private.",
               "<b>Disclose responsibly.</b> Tell the owner privately, using their "
               "<font face='DVM'>/.well-known/security.txt</font> contact or bug-bounty programme, "
               "and give them time to fix it.",
               "<b>Demo only on what you own.</b> The hackathon demo uses the team's own sandbox "
               "account and test domain.",
               "<b>Be precise about claims.</b> Candidate ≠ confirmed; traffic ≠ compromise."]),
      warn("Taking over someone else's subdomain “just to prove it”, even harmlessly, can be "
           "illegal without permission. The research for this project never did."),
      P("21. Running the project code", H1), rule(ACC, 1.5),
      pre("git clone https://github.com/BOOMER16/RetireSafe.git && cd RetireSafe\n"
          "pip install -r requirements.txt\n"
          "./scripts/fetch_data.sh                 # downloads the real datasets into ./data\n\n"
          "cd testbeds\n"
          "python3 tb1_dns_cname.py                # live DNS + S3 probe (~7 min for 16k names)\n"
          "python3 tb2_traffic_survival.py         # quarantine + calibration (~1 min)\n"
          "python3 tb3_blast_radius.py             # blast radius (~1 min)\n"
          "python3 make_figs.py && python3 make_pdf.py\n\n"
          "N_TOP=500 N_RAND=500 python3 tb1_dns_cname.py   # quick, smaller TB1 run"),
      tbl([["File", "What it is"],
           ["README.md", "Overview and headline results"],
           ["RetireSafe_Solution_Dossier.pdf", "The 7-page research and solution report"],
           ["docs/01 … 07", "Problem, test beds, architecture, maths, data, ethics, hackathon plan"],
           ["testbeds/results/*.json", "Exact numbers behind every claim"],
           ["docs/RESEARCH_LOG.md", "How the research was done, including corrections"]],
          [62 * mm, W - 62 * mm]),
      PageBreak()]

E += [P("22. FAQ: questions judges may ask", H1), rule(ACC, 1.5)]
faq = [
    ("Isn't this just a subdomain-takeover scanner?",
     "No. Scanners find problems after they exist. RetireSafe works <i>before</i> the deletion, "
     "across DNS, code, infrastructure and traffic, recognises provider protections, and produces "
     "a decision, a fix and an evidence record."),
    ("Why not just delete the DNS record too?",
     "That fixes one reference. Code, package configs, SPF rules and outside consumers can still "
     "point at the name, and DNS is often managed by a different team. RetireSafe finds them all."),
    ("Why not keep every name forever?",
     "That costs money and clutter. RetireSafe tells you which names really need retaining and for "
     "how long (the quarantine D*)."),
    ("Doesn't AWS's new namespace solve it?",
     "For new buckets in that namespace, yes. Legacy global buckets still exist and can't be renamed; "
     "other providers, DNS, SPF and code references remain. RetireSafe treats the namespace as "
     "evidence that clears condition 2."),
    ("How do you know a resource is unused?",
     "We never “know”; we measure. Per-resource silence windows, calibrated probabilities, the "
     "number of outside users, and an explicit UNKNOWN when the logs are too short."),
    ("Your data is from 1995?",
     "It's a large, real, public traffic log, which is rare. The method works on any access log, "
     "including a team's own CloudFront logs in the demo."),
    ("How accurate is TB1?",
     "It's a 16,000-name sample of live infrastructure; it gives the order of magnitude (about 3 in "
     "10,000), reported with a confidence interval."),
    ("Did you hack anything?",
     "No. Only DNS lookups and public, read-only S3 queries. Nothing was claimed or registered, "
     "and no vulnerable hostnames were published."),
]
for q, a in faq:
    E += [KeepTogether([P(q, H3), P(a)])]
E += [PageBreak()]

E += [P("23. Glossary", H1), rule(ACC, 1.5)]
gl = [
    ("A / AAAA record", "DNS record mapping a name to an IPv4 / IPv6 address."),
    ("Access log", "A file where a web server writes one line per request."),
    ("Blast radius", "Who would be affected if a resource disappeared or was hijacked."),
    ("Base rate (π)", "How common something is in the population before any test."),
    ("Brier score", "Average squared error of probability predictions; lower is better."),
    ("Calibration", "Whether predicted probabilities match real frequencies."),
    ("CNAME", "DNS alias: “this name is really that other name”."),
    ("CNAME chain", "A series of aliases followed one after another."),
    ("Confidence interval", "A range that expresses uncertainty around an estimate."),
    ("Consumer", "A person or program that uses a resource or reference."),
    ("D* (quarantine)", "Days of silence needed before believing a resource is unused, at a chosen confidence."),
    ("Dangling reference", "A pointer to something you no longer control."),
    ("DKIM / DMARC", "Email signature and email-policy standards that work alongside SPF."),
    ("DNS", "Domain Name System: turns names into addresses."),
    ("eTLD+1 / registrable domain", "The part of a name one owner can register (e.g. example.co.uk)."),
    ("Evidence ladder", "Stale reference → reclaimable endpoint → demonstrated impact."),
    ("Evidence record", "RetireSafe's report of what was checked, how, and what couldn't be checked."),
    ("Fingerprint", "The tell-tale sign that a provider resource is unclaimed (NXDOMAIN or an error page)."),
    ("Global namespace", "A pool of names shared by all customers of a provider; first come, first served."),
    ("Hold-out validation", "Testing a model on data it was not trained on."),
    ("IaC", "Infrastructure as Code: describing cloud resources in files (e.g. Terraform)."),
    ("Isotonic regression", "A method for correcting badly calibrated probabilities."),
    ("λ (lambda)", "Rate: average events (requests) per unit of time."),
    ("NoSuchBucket", "S3's error when a bucket name doesn't exist (so it may be claimable)."),
    ("NXDOMAIN", "DNS answer meaning “this name does not exist”."),
    ("Poisson process", "Model of independent random events at a constant average rate."),
    ("prevent_destroy", "Terraform setting that blocks plans deleting a resource."),
    ("Public Suffix List", "List of shared suffixes like co.uk and github.io."),
    ("Reclaimable / reassignable", "A released name that someone else can now claim."),
    ("Resolver", "The DNS server that looks names up on your behalf."),
    ("S3 bucket", "An AWS storage container with a name used in URLs."),
    ("SPF", "DNS TXT record listing servers allowed to send email for a domain."),
    ("Subdomain takeover", "An attacker controls content on your subdomain via a dangling record."),
    ("Test bed", "A small real-data experiment run before building the product."),
    ("TTL", "How long DNS answers may be cached."),
    ("Wilson interval", "A confidence interval for proportions that works well with small counts."),
]
E += [tbl([["Term", "Meaning"]] + [[f"<b>{a}</b>", b] for a, b in gl], [46 * mm, W - 46 * mm])]
E += [PageBreak()]

E += [P("24. Learning path and self-check", H1), rule(ACC, 1.5),
      P("Read in this order (about 3 hours)", H2),
      tbl([["#", "Read", "Why"],
           ["1", "Microsoft Learn: Prevent dangling DNS entries and avoid subdomain takeover",
            "Clear definition of the problem and Azure's defences"],
           ["2", "Infoblox (Mar 2025): the CDC incident", "A concrete, recent victim"],
           ["3", "watchTowr (Feb 2025): 8 Million Requests Later", "Why code and traffic matter, "
            "not just DNS"],
           ["4", "Guardio (Feb 2024): SubdoMailing", "Email/SPF version of the problem"],
           ["5", "NSDI 2024, Friess et al.: Cloudy with a Chance of Cyberattacks", "Measured scale "
            "(skim intro and results)"],
           ["6", "AWS: account regional namespaces; bucket owner condition", "The newest "
            "protections"],
           ["7", "EdOverflow/can-i-take-over-xyz README", "How each provider behaves"],
           ["8", "This repo: docs/02_testbeds.md and docs/04_mathematics.md", "Our evidence and "
            "maths in detail"]],
          [7 * mm, 92 * mm, W - 99 * mm]),
      P("Links for all of these are in docs/SOURCES.md.", small),
      P("Can you explain these? (self-check)", H2),
      bullets(["What a CNAME is, and what it means when its target returns NXDOMAIN.",
               "Why a deleted S3 bucket in the global namespace is dangerous, and what NoSuchBucket "
               "tells you.",
               "The five takeover conditions, and why breaking just one is enough.",
               "The difference between a stale reference, a reclaimable endpoint and demonstrated "
               "impact.",
               "How an SPF include: can hand email authority to an attacker.",
               "Why Terraform prevent_destroy is not enough on its own.",
               "What e^(−λD) means, and why rare resources need long quarantines.",
               "Why a rare problem plus an imperfect detector means mostly false alarms.",
               "What it means for a model to be calibrated, and what our reliability diagram showed.",
               "Our three headline numbers: 0.031% reclaimable; 42–127 days of quarantine; "
               "15,054 hidden external users of an idle-looking file.",
               "The four verdicts, and why UNKNOWN is a feature."]),
      Spacer(1, 6), rule(ACC, 1.5),
      P("<i>You now know enough to explain RetireSafe to a judge, contribute to the build, and "
        "defend every number in the pitch.</i>", S("end", fontName="DV-I", fontSize=10, leading=14,
                                                     textColor=ACC2, alignment=TA_CENTER))]

doc.multiBuild(E)
print("written", OUT)
