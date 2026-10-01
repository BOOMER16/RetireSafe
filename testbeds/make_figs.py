"""Generate figures for the RetireSafe research PDF from real test-bed outputs."""
import json
import os
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = os.path.join(os.path.dirname(__file__), "results")
FIG = os.path.join(os.path.dirname(__file__), "figs")
os.makedirs(FIG, exist_ok=True)

INK = "#1b2430"; MUT = "#5b6775"; ACC = "#c23b22"; ACC2 = "#2f6f8f"; GRID = "#dfe4ea"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": MUT, "axes.labelcolor": INK,
                     "text.color": INK, "xtick.color": MUT, "ytick.color": MUT,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": .8,
                     "figure.dpi": 150, "savefig.bbox": "tight"})

tb1 = json.load(open(f"{R}/tb1_summary.json"))
tb2 = json.load(open(f"{R}/tb2_summary.json"))
tb3 = json.load(open(f"{R}/tb3_summary.json"))

# Fig 1: TB1 evidence ladder (stacked, excluding the dominant no_cname/resolves)
fig, ax = plt.subplots(figsize=(6.6, 2.9))
cats = ["cname_resolves", "stale_cname_target_missing", "reclaimable_candidate"]
labels = ["CNAME resolves\n(healthy)", "Stale: target\nNXDOMAIN", "Reclaimable\ncandidate"]
top = [tb1["by_stratum"]["top"]["class"].get(c, 0) for c in cats]
rnd = [tb1["by_stratum"]["random"]["class"].get(c, 0) for c in cats]
x = range(len(cats))
ax.bar([i - .2 for i in x], top, .4, label="Top 8k", color=ACC2)
ax.bar([i + .2 for i in x], rnd, .4, label="Random 8k", color=ACC)
ax.set_yscale("symlog")
ax.set_xticks(list(x)); ax.set_xticklabels(labels, fontsize=8)
ax.set_ylabel("resources (log)")
ax.set_title("TB1  Surviving-reference ladder over 16,000 real hostnames", fontsize=10, loc="left")
for i, (a, b) in enumerate(zip(top, rnd)):
    ax.text(i - .2, a, str(a), ha="center", va="bottom", fontsize=7)
    ax.text(i + .2, b, str(b), ha="center", va="bottom", fontsize=7)
ax.legend(frameon=False, fontsize=8)
fig.savefig(f"{FIG}/fig1_tb1.png"); plt.close(fig)

# Fig 2: TB2 quarantine window distribution
q = tb2["quarantine_days_for_1pct_miss"]
fig, ax = plt.subplots(figsize=(6.6, 2.9))
ks = ["p50", "p90", "p99", "max", "mean"]
vals = [q[k] for k in ks]
bars = ax.bar(ks, vals, color=[ACC2, ACC2, ACC2, ACC, MUT])
ax.set_ylabel("days of silence")
ax.set_title("TB2  Silence needed for 99% confidence a resource is dead",
             fontsize=10, loc="left")
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}d", ha="center", va="bottom", fontsize=8)
ax.axhline(tb2["observed_span_days"], color=INK, ls="--", lw=1)
ax.text(4.4, tb2["observed_span_days"], " log span", va="center", fontsize=7, color=INK)
fig.savefig(f"{FIG}/fig2_tb2_quar.png"); plt.close(fig)

# Fig 3: TB2 reliability diagram
rel = tb2["holdout_validation"]["reliability_deciles"]
fig, ax = plt.subplots(figsize=(3.6, 3.4))
ax.plot([0, 1], [0, 1], color=MUT, ls=":", lw=1)
ax.plot([r["pred"] for r in rel], [r["obs"] for r in rel], "-o", color=ACC, ms=4)
ax.set_xlabel("predicted P(returns)"); ax.set_ylabel("observed P(returns)")
ax.set_title("TB2  Poisson calibration", fontsize=10, loc="left")
ax.set_xlim(0, 1); ax.set_ylim(0, 1)
fig.savefig(f"{FIG}/fig3_tb2_rel.png"); plt.close(fig)

# Fig 4: TB3 hidden dependents
off = tb3["top_offenders"][:8]
fig, ax = plt.subplots(figsize=(3.6, 3.4))
names = [o["resource"].split("/")[-1] or o["resource"] for o in off]
ext = [o["distinct_external_clients"] for o in off]
ax.barh(range(len(off)), ext, color=ACC)
ax.set_yticks(range(len(off))); ax.set_yticklabels(names, fontsize=7)
ax.invert_yaxis()
ax.set_xlabel("distinct external clients")
ax.set_title("TB3  'Idle' resources, hidden\nexternal dependents", fontsize=10, loc="left")
for i, v in enumerate(ext):
    ax.text(v, i, f" {v:,}", va="center", fontsize=7)
fig.savefig(f"{FIG}/fig4_tb3.png"); plt.close(fig)
print("figures written", os.listdir(FIG))
