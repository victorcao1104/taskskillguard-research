"""Render paper figures from frozen release tables; never write research inputs."""
from pathlib import Path
import csv
import hashlib
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.labelsize": 9,
                     "axes.titlesize": 10, "legend.fontsize": 8, "pdf.fonttype": 42,
                     "svg.fonttype": "none", "axes.spines.top": False,
                     "axes.spines.right": False})
COLORS = ["#176b8b", "#c56a22", "#557a32", "#8064a2"]
sources = {}
selected = []

def read(rel):
    path = ROOT / rel
    sources[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return list(csv.DictReader(path.open(encoding="utf-8")))

def one(rows, **filters):
    hits = [r for r in rows if all(r.get(k) == str(v) for k, v in filters.items())]
    if len(hits) != 1:
        raise ValueError((filters, len(hits)))
    selected.append(hits[0])
    return float(hits[0]["estimate"])

def save(fig, name):
    fig.savefig(HERE / "figures" / (name + ".pdf"), bbox_inches="tight",
                metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(HERE / "figures" / (name + ".png"), bbox_inches="tight", dpi=220)
    plt.close(fig)

pol = read("results/phase11/analysis/policy_conditions.csv")
fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.6), layout="constrained")
budgets = [2, 4, 8, 12]
for j, (policy, label) in enumerate([("original_first", "Original-first"),
                                    ("route_cover", "Route-cover"),
                                    ("observe_cover", "Observe-cover"),
                                    ("random", "Random (one seed)")]):
    y = [100*one(pol, cohort="combined", policy=policy, budget=b, stop=True,
                 metric="completion") for b in budgets]
    axes[0].plot(budgets, y, marker="o", ms=4, color=COLORS[j], label=label)
for stop, label, style in [(False, "Fixed budget", "--"), (True, "Certificate stop", "-")]:
    y = [one(pol, cohort="combined", policy="observe_cover", budget=b,
             stop=stop, metric="query_count") for b in budgets]
    axes[1].plot(budgets, y, style, marker="o", ms=4,
                 color=COLORS[0] if stop else COLORS[1], label=label)
for ax in axes:
    ax.set_xlabel("Allowed queries"); ax.set_xticks(budgets)
    ax.grid(axis="y", alpha=.2); ax.legend(loc="lower right")
axes[0].set_ylabel("Acknowledged completion (%)"); axes[0].set_ylim(0, 100)
axes[0].set_title("(a) Deterministic selectors")
axes[1].set_ylabel("Mean acquired queries"); axes[1].set_ylim(0, 9)
axes[1].set_title("(b) Observe-cover stopping")
save(fig, "acquisition")

cmp = read("results/phase11/figures/matched_model_comparison.csv")
fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.6), layout="constrained")
names = ["Observe-cover", "GPT-6 Luna", "GPT-4.1 mini"]
for ax, metric, multiplier, ylabel in [(axes[0], "completion", 100, "Acknowledged completion (%)"),
                                      (axes[1], "query_count", 1, "Mean acquired queries")]:
    vals = [one(cmp, cohort="combined", metric=metric, side="heuristic", model="gpt-6-luna")]
    vals += [one(cmp, cohort="combined", metric=metric, side="model", model=m)
             for m in ["gpt-6-luna", "gpt-4.1-mini"]]
    bars = ax.bar(names, np.array(vals)*multiplier, color=COLORS[:3], width=.6)
    ax.set_ylabel(ylabel); ax.grid(axis="y", alpha=.2); ax.set_axisbelow(True)
    for bar, v in zip(bars, vals):
        label = f"{v*100:.2f}%" if metric == "completion" else f"{v:.3f}"
        ax.annotate(label, (bar.get_x()+bar.get_width()/2, bar.get_height()),
                    ha="center", va="bottom", xytext=(0, 3), textcoords="offset points")
axes[0].set_ylim(0, 100); axes[1].set_ylim(0, 6.7)
axes[0].set_title("(a) Completion at budget 12")
axes[1].set_title("(b) Acquisition cost at budget 12")
save(fig, "models")

rec = read("results/phase11/physical_goal/conditions.csv")
fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.7), layout="constrained")
for ax, fault, title in zip(axes, ["ambiguous_after", "terminal_noncommit"],
                           ["(a) Commit, then lose acknowledgement", "(b) Fenced terminal noncommit"]):
    x = np.arange(2)
    for i, (metric, label) in enumerate([("authorized_goal", "Acknowledged completion"),
                                       ("physical_goal", "Physical goal (posthoc)")]):
        vals = [100*one(rec, cohort="combined", fault=fault, status_budget=1,
                        policy=p, metric=metric) for p in ["strict_stop", "terminal_status"]]
        bars = ax.bar(x+(i-.5)*.34, vals, .34, label=label, color=COLORS[i],
                      hatch="//" if i else None)
        for bar, v in zip(bars, vals):
            ax.annotate(f"{v:.1f}", (bar.get_x()+bar.get_width()/2, v), ha="center",
                        va="bottom", xytext=(0, 2), textcoords="offset points", fontsize=8)
    ax.set_xticks(x, ["Strict-stop", "Terminal-status"]); ax.set_ylim(0, 108)
    ax.set_ylabel("Family-mean success (%)"); ax.set_title(title)
    ax.grid(axis="y", alpha=.2); ax.set_axisbelow(True)
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="outside lower center", ncols=2, frameon=False)
save(fig, "recovery")

(HERE / "verification" / "figure_inputs.json").write_text(
    json.dumps({"source_sha256": sources, "selected_rows": selected}, indent=2)+"\n",
    encoding="utf-8", newline="\n")
print(f"Rendered 3 figures from {len(sources)} unchanged source tables; {len(selected)} selected rows.")
