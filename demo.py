"""RetireSafe guided demo: watch the backend decide, step by step.

    python demo.py              run the whole walkthrough
    python demo.py --pause      stop after each step (press Enter to continue)
    python demo.py --mode balanced
    python demo.py --no-traffic run without access logs (shows what changes when evidence is missing)
    python demo.py --drift www.example.com other.example.org   live read-only DNS check of names you own

Scenario: an invented organisation (retiresafe-pilot.example) wants to delete four S3 buckets
after an event. Terraform plans and DNS exports are real tool output (pilot/generated/);
traffic is the real NASA-HTTP Jul+Aug 1995 log (get it with: python scripts/get_data.py).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

from retiresafe.analysis.traffic import Policy  # noqa: E402
from retiresafe.engine import apply_patch  # noqa: E402
from retiresafe.engine.assess import AssessmentInput, LogInput, run  # noqa: E402
from retiresafe.knowledge.sources import SOURCES  # noqa: E402
from retiresafe.models import Tri  # noqa: E402
from retiresafe.paths import nasa_log  # noqa: E402
from retiresafe.report import evidence  # noqa: E402

PILOT = ROOT / "pilot"
GEN = PILOT / "generated"
OUT = ROOT / "demo_output"
SCEN = json.loads((PILOT / "scenario.json").read_text(encoding="utf-8"))
W = 100
PAUSE = False
MARK = {Tri.TRUE: "yes", Tri.FALSE: "NO", Tri.UNKNOWN: "?"}


def say(text: str = "", indent: int = 0) -> None:
    for para in text.split("\n"):
        print(textwrap.fill(para, W, initial_indent=" " * indent, subsequent_indent=" " * indent) if para else "")


def step(n: int | str, title: str) -> None:
    if PAUSE and n != 0:
        input("\n[press Enter for the next step] ")
    print("\n" + "=" * W)
    print(f"STEP {n}  {title}".upper())
    print("=" * W)


def table(rows: list[list[str]], head: list[str]) -> None:
    widths = [max(len(str(r[i])) for r in rows + [head]) for i in range(len(head))]
    widths = [min(w, 60) for w in widths]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print("  " + fmt.format(*head))
    print("  " + fmt.format(*["-" * w for w in widths]))
    for r in rows:
        print("  " + fmt.format(*[str(c)[:60] for c in r]))


def dur(days: float | None) -> str:
    if days is None:
        return "-"
    secs = days * 86400
    if secs < 120:
        return f"{secs:.0f} seconds"
    if secs < 7200:
        return f"{secs / 60:.0f} minutes"
    if days < 2:
        return f"{days * 24:.1f} hours"
    return f"{days:.1f} days"


def assess(plan: str, dns: str, repo: Path, logs: list[LogInput], policy: Policy):
    t0 = time.time()
    res = run(AssessmentInput(str(GEN / plan), [(str(GEN / dns), None)], {"app": str(repo)}, logs, policy,
                              datetime.fromisoformat(SCEN["as_of"].replace("Z", "+00:00")), SCEN["migrate_to"]))
    return res, time.time() - t0


def main() -> int:
    global PAUSE
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pause", action="store_true")
    ap.add_argument("--mode", choices=["strict", "balanced"], default="strict")
    ap.add_argument("--no-traffic", action="store_true")
    ap.add_argument("--log", help="path to nasa_jul_aug_1995.log (default: data/nasa-http/)")
    ap.add_argument("--drift", nargs="*", help="also run a live drift scan on these hostnames (names you own)")
    a = ap.parse_args()
    PAUSE = a.pause
    OUT.mkdir(exist_ok=True)

    # ------------------------------------------------------------------ 0
    step(0, "What RetireSafe checks")
    say("Deleting a cloud resource frees its name. If someone else can register that name while DNS records, "
        "code or configuration still point at it, they inherit the traffic. A takeover needs ALL FIVE:")
    table([["C1", "released", "the change deletes the resource"],
           ["C2", "reassignable", "another account could register the freed name"],
           ["C3", "reference survives", "a DNS record / code line / config still points at it"],
           ["C4", "consumer remains", "somebody is still sending requests"],
           ["C5", "controls permit", "the consumer accepts whatever the name now serves"]],
          ["", "condition", "meaning"])
    say("\nIf any one is provably false, that path is safe. Missing evidence counts as UNKNOWN, never as safe.")

    log_path = Path(a.log) if a.log else nasa_log()
    logs: list[LogInput] = []
    if a.no_traffic:
        say("\n(--no-traffic: running without access logs.)")
    elif log_path.exists():
        logs = [LogInput(str(log_path), "clf", t["host"], [], t["path_prefix"]) for t in SCEN["traffic"]]
    else:
        say(f"\nNOTE: traffic log not found at {log_path}. Continuing WITHOUT traffic evidence.\n"
            "To include the real NASA traffic: python scripts/get_data.py   (downloads ~37 MB)")
    policy = Policy(mode=a.mode, org_account_ids=[SCEN["org_account_id"]], internal_domains=[SCEN["internal_domain"]])

    # ------------------------------------------------------------------ 1
    step(1, "Read the proposed change (Terraform plan)")
    say(f"Input: {GEN / 'plan_before.json'}\n(real `terraform show -json` output, Terraform 1.16.4 + AWS provider "
        "6.67.0). The app team wants to delete everything below after the event:")
    if logs:
        say(f"\nAnalysing {log_path.name} as well ({log_path.stat().st_size / 1e6:.0f} MB, 3.46 million real "
            "requests). This takes 20-60 seconds ...")
    before, secs = assess("plan_before.json", "route53_before.json", PILOT / "app", logs, policy)
    table([[a_.resource.action, a_.resource.address, a_.resource.name or "-",
            "covered" if a_.verdict.value != "not_name_bearing" else "no public name (outside scope)"]
           for a_ in before.resources], ["action", "resource", "name", "pilot rules"])
    say(f"\n(assessment took {secs:.1f} s)")
    named = [x for x in before.resources if x.verdict.value != "not_name_bearing"]

    # ------------------------------------------------------------------ 2
    step(2, "Could someone else claim each freed name? (condition C2)")
    for x in named:
        c2 = x.reclaimable
        say(f"\n{x.resource.address}  ->  reclaimable: {MARK[c2.value]}", 0)
        say(c2.reason, 4)
        for sid in c2.evidence_ids[:1]:
            src = SOURCES.get(sid[4:], {})
            if src.get("quote"):
                say(f'source: {src["title"]}', 4)
                say(f'"{src["quote"][:300]}"', 6)

    # ------------------------------------------------------------------ 3
    step(3, "Where is each name still referenced? (condition C3)")
    say("Searched: the Route 53 export (DNS team), the app repository (pilot/app) and other resources in the "
        "Terraform state.")
    for x in named:
        refs = [r for r in x.references if r.kind.value != "traffic"]
        say(f"\n{x.resource.address}: {len(refs)} reference(s)")
        if refs:
            table([[r.kind.value, r.location.replace('route53_before.json#', ''),
                    "removed by this change" if r.removed_in_change else "survives",
                    r.integrity_control or "-", r.text[:50]] for r in refs],
                  ["kind", "where", "after deletion", "integrity check", "text"])

    # ------------------------------------------------------------------ 4
    step(4, "Is anybody still using it? (condition C4, from access logs)")
    if not logs:
        say("No access logs supplied, so C4 is UNKNOWN for every resource: RetireSafe cannot rule out "
            "remaining consumers, and will not treat that as safe.")
    for x in named:
        for t in x.traffic:
            say(f"\n{x.resource.address}  (log view: {t.source})")
            table([["requests", f"{t.requests:,}"], ["distinct clients", f"{t.distinct_clients:,}"],
                   ["external clients", f"{t.external_clients:,}"],
                   ["log window", f"{t.window_days:.1f} days"], ["last request", t.last_seen or "-"],
                   ["silent for (since last request)", dur(t.silence_days)],
                   ["quiet time needed to be 99% sure it is unused", dur(t.quarantine_days_conservative)]],
                  ["measure", "value"])
            if t.silence_days is not None and t.quarantine_days_conservative:
                quiet = t.silence_days >= t.quarantine_days_conservative
                say("-> silent longer than the quarantine: consumers have gone (C4 = NO)" if quiet else
                    "-> still in use: silence is shorter than the quarantine (C4 = yes)", 2)

    # ------------------------------------------------------------------ 5
    step(5, "Five-condition check for every reference path")
    say("yes = condition holds, NO = condition is false (breaks the attack), ? = unknown.\n"
        "A path is HIJACKABLE only if all five hold; one NO makes it SAFE. The 'access logs' row stands for "
        "consumers seen in traffic whose own integrity checks we cannot see (C5 = ?).")
    for x in named:
        if not x.paths:
            continue
        say(f"\n{x.resource.address}")
        rows = []
        for r, p in zip(x.references, x.paths):
            c = p.conditions
            rows.append([r.location.replace("route53_before.json#", "")[:44]] +
                        [MARK[c[k].value] for k in ("c1", "c2", "c3", "c4", "c5")] + [p.status.upper()])
        table(rows, ["reference", "C1", "C2", "C3", "C4", "C5", "path"])

    # ------------------------------------------------------------------ 6
    step(6, f"Verdicts and the gate ({a.mode} mode)")
    rec_b = evidence.record(before, {**policy.__dict__})
    for x in before.resources:
        say(f"\n{x.verdict.value.upper():<17}{x.resource.address}")
        for reason in x.reasons:
            say(reason, 4)
    g = rec_b["gate"]
    say(f"\nGATE: {'PASS' if g['passed'] else 'FAIL'}  ->  CLI exit code {0 if g['passed'] else 2}. "
        "In CI this stops `terraform apply` from running.")
    (OUT / "before_evidence.json").write_text(json.dumps(rec_b, indent=2), encoding="utf-8")
    (OUT / "before_report.md").write_text(evidence.markdown(rec_b), encoding="utf-8")

    # ------------------------------------------------------------------ 7
    step(7, "The fixes RetireSafe proposes")
    diffs = []
    for x in before.resources:
        for p in x.patches:
            say(f"- [{x.resource.address}] {p.title}")
            if p.kind == "code_diff":
                diffs.append(p.content)
    if diffs:
        say("\nExample: the code diff (moves the unpinned script and the stylesheet to an account-regional "
            "bucket nobody else can claim):\n")
        print(textwrap.indent("".join(diffs).rstrip(), "    "))
    route = next((p for x in before.resources for p in x.patches if p.kind == "route53_change_batch"), None)
    if route:
        say("\nExample: Route 53 change batch to remove a surviving CNAME:\n")
        print(textwrap.indent(route.content.split("\n\n# apply")[0], "    "))

    # ------------------------------------------------------------------ 8
    step(8, "Apply the fixes and check again")
    after_app = OUT / "app_after_fix"
    shutil.rmtree(after_app, ignore_errors=True)
    shutil.copytree(PILOT / "app", after_app)
    ops = [p.operation for x in before.resources for p in x.patches if p.kind == "code_diff" and p.operation]
    changed = sorted({f for op in ops for f in apply_patch.apply_operation(op, after_app)})
    say(f"1. code diff applied to a copy of the app: {', '.join(changed) or 'nothing to change'}  "
        f"(in {after_app})")
    say("2. DNS team removes the two surviving CNAMEs     -> pilot/generated/route53_after.json")
    say("3. plan keeps global-namespace buckets as tombstones, archive still deleted -> pilot/generated/plan_after.json")
    after, secs = assess("plan_after.json", "route53_after.json", after_app, logs, policy)
    rec_a = evidence.record(after, {**policy.__dict__})
    say("\nThe three global-namespace buckets are no longer in the deletion list: they are kept (emptied) "
        "so nobody else can register their names. What is still deleted:")
    for x in after.resources:
        say(f"\n{x.verdict.value.upper():<17}{x.resource.address}")
        say(x.reasons[0], 4)
    g = rec_a["gate"]
    say(f"\nGATE: {'PASS' if g['passed'] else 'FAIL'}  ->  exit code {0 if g['passed'] else 2}   (took {secs:.1f} s)")
    (OUT / "after_evidence.json").write_text(json.dumps(rec_a, indent=2), encoding="utf-8")
    (OUT / "after_report.md").write_text(evidence.markdown(rec_a), encoding="utf-8")

    # ------------------------------------------------------------------ 9
    if a.drift:
        step(9, "Live drift scan (read-only DNS + S3 checks)")
        from retiresafe.probes import live
        res = live.scan(a.drift)
        table([[f.hostname, f.classification, f.detail[:70]] for f in res], ["hostname", "result", "detail"])

    step("done", "What was written")
    say(f"Evidence records and readable reports are in {OUT}:")
    for p in sorted(OUT.glob("*.*")):
        say(f"- {p.name}", 2)
    say("\nOpen before_report.md to see every reference, condition, traffic figure and patch, or "
        "before_evidence.json for the full audit record (input hashes, sources, evidence ids).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
