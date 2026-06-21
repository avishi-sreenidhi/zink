# SPDX-License-Identifier: Apache-2.0
"""
study/figures.py — render the writeup figures from results.json.
    python -m study.figures   ->   study/out/*.png
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).parent / "out"
R = json.loads((OUT / "results.json").read_text())

INK = "#1f2933"
MUTED = "#7b8794"
ACCENT = "#2b8a8f"
BAD = "#b23a48"
GOOD = "#2f855a"
GRID = "#e4e7eb"

plt.rcParams.update({
    "font.size": 11, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 140,
})

LAYER_NAMES = {
    "identity": "L1 Identity", "injection": "L2 Injection",
    "scope": "L9 Scope", "policy": "L6 Policy", "memory": "L4 Memory",
}

# ── Fig 1: which gate caught what ─────────────────────────────────────────────
def fig_attribution():
    hits = R["layer_attribution"]
    order = ["identity", "injection", "scope", "policy", "memory"]
    labels = [LAYER_NAMES[k] for k in order]
    vals = [hits.get(k, 0) for k in order]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    bars = ax.barh(labels, vals, color=ACCENT, height=0.6)
    ax.bar_label(bars, padding=4, color=INK, fontweight="bold")
    ax.set_xlim(0, max(vals) + 1)
    ax.set_xlabel("actions blocked")
    n_block = sum(vals)
    ax.set_title(f"Responsible gate per blocked action  ({n_block} blocked of {R['n_cases']})",
                 loc="left", fontweight="bold", pad=10)
    ax.invert_yaxis()
    ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(OUT / "fig1_layer_attribution.png"); plt.close(fig)

# ── Fig 2: audit completeness + tamper-evidence ───────────────────────────────
def fig_integrity():
    t = R["tamper_evidence"]; ac = R["audit_completeness"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.2, 3.2),
                                 gridspec_kw={"width_ratios": [1, 1.25]})
    # left: completeness
    a1.bar(["actions", "log rows"], [ac["actions_executed"], ac["audit_rows_written"]],
           color=[MUTED, ACCENT], width=0.55)
    a1.set_ylim(0, ac["actions_executed"] + 3)
    for i, v in enumerate([ac["actions_executed"], ac["audit_rows_written"]]):
        a1.text(i, v + 0.3, str(v), ha="center", fontweight="bold")
    a1.set_title("Audit completeness", loc="left", fontweight="bold")
    a1.text(0.5, -0.27, "every action -> one log row", transform=a1.transAxes,
            ha="center", color=MUTED, fontsize=9.5)
    # right: chain verification clean vs tampered
    states = ["clean log", f"after 1-field\nedit (row {t['tampered_row_id']})"]
    valid = [1 if t["verify_before_tamper"] else 0,
             1 if t["verify_after_tamper"] else 0]
    colors = [GOOD if v else BAD for v in valid]
    a2.bar(states, [1, 1], color=colors, width=0.55)
    for i, ok in enumerate(valid):
        a2.text(i, 0.5, "VERIFIED" if ok else "BROKEN", ha="center", va="center",
                color="white", fontweight="bold", fontsize=10, rotation=0)
    a2.set_yticks([]); a2.set_ylim(0, 1.15)
    a2.set_title("Hash-chain verification", loc="left", fontweight="bold")
    a2.text(0.5, -0.27, f"tamper localised to row {t['chain_breaks_at_row']}",
            transform=a2.transAxes, ha="center", color=MUTED, fontsize=9.5)
    fig.tight_layout(); fig.savefig(OUT / "fig2_audit_integrity.png"); plt.close(fig)

# ── Fig 3: determinism / replay fidelity ──────────────────────────────────────
def fig_determinism():
    d = R["determinism"]; n = d["runs"]; sig = d["signature"][:10]
    fig, ax = plt.subplots(figsize=(8.2, 2.4))
    for i in range(n):
        ax.add_patch(plt.Rectangle((i, 0), 0.86, 1, color=ACCENT))
        ax.text(i + 0.43, 0.5, f"{sig}…", ha="center", va="center",
                color="white", fontsize=7.5, family="monospace", rotation=90)
    ax.set_xlim(0, n); ax.set_ylim(0, 1); ax.set_yticks([])
    ax.set_xticks([i + 0.43 for i in range(n)])
    ax.set_xticklabels([f"run {i+1}" for i in range(n)], fontsize=8)
    verdict = "identical" if d["deterministic"] else "DIVERGENT"
    ax.set_title(f"Replay fidelity — {n} independent runs, "
                 f"{d['unique_decision_signatures']} unique decision signature ({verdict})",
                 loc="left", fontweight="bold", pad=10)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "fig3_determinism.png"); plt.close(fig)


if __name__ == "__main__":
    fig_attribution(); fig_integrity(); fig_determinism()
    print("wrote:", *[p.name for p in sorted(OUT.glob("fig*.png"))])