"""Recompute the report's Section 7 metrics (definitions from Section 6.3) from the turn traces.

    python data/evaluations/section7_tables.py

Writes data/evaluations/SECTION7_RESULTS.md and data/evaluations/figures/fig6_tradeoff.png.
Run from delivery-robot/backend.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np

ROOT = Path("data/evaluations")
MIN_SHOWN = 10
POLICIES = ["C1", "C2", "C3", "C4", "C5"]
RUNS = [
    # key, folder, title, C5 artifact used in that run
    ("v1_fixed", "rerun_fixed/test", "v1 test, after evaluation fixes (rerun_fixed)", "artifacts/clarification_policy_v2.joblib"),
    ("v1_canon", "rerun_canonical/test", "v1 test, after draft clean-up (rerun_canonical)", "artifacts/clarification_policy_v3.joblib"),
    ("v2_a", "v2/test_a", "v2 test A: new wording, v1 menu", "artifacts/clarification_policy_v4.joblib"),
    ("v2_b", "v2/test_b", "v2 test B: held-out menu", "artifacts/clarification_policy_v4.joblib"),
    ("pizza", "v2/pizza", "v2 PIZZA: human-written orders, held-out menu", "artifacts/clarification_policy_v4.joblib"),
]
SHORT = {"v1_fixed": "v1 test (fixes)", "v1_canon": "v1 test (clean-up)", "v2_a": "v2 test A (new wording)",
         "v2_b": "v2 test B (new menu)", "pizza": "v2 PIZZA (human)"}
CATEGORY_NAMES = {
    "clear_request": "Clear requests",
    "ambiguous_item": "Ambiguous items",
    "unavailable_option": "Unavailable options",
    "customization": "Customizations",
    "correction": "Corrections",
    "removal": "Removals",
    "multi_item": "Multiple items",
    "multi_problem": "Multiple problems",
    "quantity_limit": "Quantity limits",
    "partial_answer": "Partial answers",
    "pizza_human": "Human-written pizza orders",
}


def pct(x):
    return "--" if x is None else f"{100 * x:.1f}%"


def lines(items):
    return Counter((str(i), int(q), tuple(sorted(str(c).lower() for c in (cs or [])))) for i, q, cs in items)


def run_metrics(folder):
    out = {}
    summary = json.loads((ROOT / folder / "summary.json").read_text(encoding="utf-8"))
    for policy in POLICIES:
        turns = [json.loads(l) for l in (ROOT / folder / f"{policy.lower()}_trace.jsonl").read_text(encoding="utf-8").splitlines()]
        final = {}
        for t in turns:
            final[t["dialogue_id"]] = t
        n = len(final)
        tp = pred = gold = 0
        for t in final.values():
            p, g = lines(t["items"]), lines(t["gold_items"])
            tp += sum((p & g).values())
            pred += sum(p.values())
            gold += sum(g.values())
        invalid = lambda t: bool(t["violations"]) or t["missing_details"] > 0
        labelled = [t for t in turns if t["label_valid"]]
        confirms = [t for t in labelled if t["action"] == "CONFIRM"]
        asks = [t for t in labelled if t["action"] in ("ASK", "REPAIR")]
        all_confirms = [t for t in turns if t["action"] == "CONFIRM"]
        s = summary[policy]
        out[policy] = {
            "exact": s["exact_order_accuracy"],
            "f1": 2 * tp / (pred + gold) if pred + gold else None,
            "completion": sum(t["action"] == "CONFIRM" for t in final.values()) / n,
            "invalid_raw": sum(invalid(t) for t in turns) / len(turns),
            "invalid_confirm": sum(invalid(t) for t in all_confirms) / len(all_confirms) if all_confirms else None,
            "missed": sum(not t["exact"] for t in confirms) / len(confirms) if confirms else None,
            "unnecessary": sum(t["exact"] for t in asks) / len(asks) if asks else None,
            "questions": s["questions_per_dialogue"],
            "turns": s["mean_turns_per_dialogue"],
            "latency": s["mean_turn_latency_ms"],
            "tokens": s["mean_tokens_per_dialogue"],
            "n": n,
            "by_category": {c: v["exact_order_accuracy"] for c, v in s["by_category"].items()},
        }
    return out


def tradeoff(folder, artifact):
    """Offline replay on the C2 turn logs: accuracy of presented carts vs questions per order."""
    rows = [json.loads(l) for l in (ROOT / folder / "c2_features.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = [r for r in rows if r["label_valid"]]
    dialogues = len({r["dialogue_id"] for r in rows})
    wrong = np.array([r["wrong"] for r in rows], dtype=bool)
    forced = np.array([r["validation_violation"] or r["missing_required_count"] > 0 for r in rows], dtype=bool)
    s1 = np.array([r["features"]["s1"] for r in rows])
    s3 = np.array([r["near_match_count"] for r in rows])
    bundle = joblib.load(artifact)
    names = bundle["feature_names"]
    prob = bundle["classifier"].predict_proba(np.array([[r["features"][k] for k in names] for r in rows]))[:, 1]

    def point(ask):
        ask = ask | forced
        shown = ~ask
        # Fewer than 10 presented carts is too few to score.
        acc = float(np.mean(~wrong[shown])) if shown.sum() >= MIN_SHOWN else None
        return float(ask.sum() / dialogues), acc

    sweep = np.round(np.linspace(0, 1, 101), 2)
    return {
        "C2": point(np.zeros_like(wrong)),
        "C3": point(s3 >= 2),
        "C4": [point(s1 < t) for t in sweep],
        "C5": [point(prob >= t) for t in sweep],
        "C4_fixed": point(s1 < 0.85),
        "C5_fixed": point(prob >= float(bundle["threshold"])),
        "c5_threshold": float(bundle["threshold"]),
    }


def main_table(m, title, number):
    rows = [
        ("Exact-order accuracy", lambda p: pct(m[p]["exact"])),
        ("Line-item F1", lambda p: pct(m[p]["f1"])),
        ("Successful completion", lambda p: pct(m[p]["completion"])),
        ("Invalid drafts (raw)", lambda p: pct(m[p]["invalid_raw"])),
        ("Invalid drafts at confirmation", lambda p: pct(m[p]["invalid_confirm"])),
        ("Missed clarifications (outcome / annotation)", lambda p: f"{pct(m[p]['missed'])} / --"),
        ("Unnecessary clarifications (outcome / annotation)", lambda p: f"{pct(m[p]['unnecessary'])} / --"),
        ("Questions per order", lambda p: f"{m[p]['questions']:.2f}"),
        ("Turns per order", lambda p: f"{m[p]['turns']:.2f}"),
        ("Latency per turn", lambda p: "--"),
        ("Tokens per order", lambda p: f"{m[p]['tokens']:,.0f}"),
    ]
    out = [f"**Table {number} - Main results by configuration: {title} (n={m['C1']['n']}).**", "",
           "| Metric | " + " | ".join(POLICIES) + " |", "|---|" + "---|" * len(POLICIES)]
    out += ["| " + name + " | " + " | ".join(f(p) for p in POLICIES) + " |" for name, f in rows]
    return "\n".join(out)


def category_table(m, title, number):
    cats = list(m["C1"]["by_category"])
    order = [c for c in CATEGORY_NAMES if c in cats]
    out = [f"**Table {number} - Exact-order accuracy by dialogue category: {title}.**", "",
           "| Dialogue category (exact-order accuracy) | " + " | ".join(POLICIES) + " |", "|---|" + "---|" * len(POLICIES)]
    for c in order:
        out.append(f"| {CATEGORY_NAMES[c]} | " + " | ".join(pct(m[p]["by_category"][c]) for p in POLICIES) + " |")
    return "\n".join(out)


def figure(trades, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"C2": "#2a78d6", "C3": "#eb6834", "C4": "#1baf7a", "C5": "#eda100"}
    ink, muted, grid = "#1f1f1d", "#6b6a63", "#e6e5e0"
    fig, grid_axes = plt.subplots(2, 3, figsize=(10.5, 6.4), sharey=True)
    axes = grid_axes.flat
    for ax, (title, t) in zip(axes, trades):
        for name, style in (("C4", "-"), ("C5", "--")):
            pts = sorted({p for p in t[name] if p[1] is not None})
            ax.plot([p[0] for p in pts], [p[1] for p in pts], style, color=colors[name], lw=2, label=f"{name} (threshold sweep)")
            fx, fy = t[f"{name}_fixed"]
            if fy is None:
                # Asks on every turn: no cart is presented, so there is nothing to score.
                ax.annotate(f"{name} at fixed threshold: <10 carts shown\n({fx:.2f} q/order)", (0.98, 0.04), xycoords="axes fraction",
                            ha="right", fontsize=7, color=muted)
                continue
            ax.plot(fx, fy, "o" if name == "C4" else "s", ms=8, color=colors[name], mec="white", mew=2)
            ax.annotate(f"{name}", (fx, fy), textcoords="offset points",
                        xytext=(7, -13) if name == "C4" else (7, 6), fontsize=8, color=ink)
        for name, marker in (("C2", "^"), ("C3", "D")):
            x, y = t[name]
            ax.plot(x, y, marker, ms=9, color=colors[name], mec="white", mew=2, label=name)
            ax.annotate(name, (x, y), textcoords="offset points",
                        xytext=(-16, 7) if name == "C2" else (7, 7), fontsize=8, color=ink)
        ax.set_title(title, fontsize=9, color=ink)
        ax.set_xlabel("Questions per order", fontsize=8, color=muted)
        ax.grid(color=grid, lw=0.8)
        ax.tick_params(labelsize=8, colors=muted)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(grid)
    for row in grid_axes:
        row[0].set_ylabel("Accuracy of presented carts", fontsize=8, color=muted)
    grid_axes[0][0].set_ylim(0.5, 1.02)
    legend_ax = grid_axes[1][2]
    legend_ax.axis("off")
    handles, labels = grid_axes[0][0].get_legend_handles_labels()
    legend_ax.legend(handles, labels, loc="center", frameon=False, fontsize=9,
                     title="Large markers: thresholds fixed in advance", title_fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)


def main():
    metrics, trades = {}, []
    for key, folder, title, artifact in RUNS:
        metrics[key] = run_metrics(folder)
        trades.append((SHORT[key], tradeoff(folder, artifact)))
    fig_path = ROOT / "figures" / "fig6_tradeoff.png"
    figure(trades, fig_path)

    parts = [
        "# Section 7 results for the runs executed (2026-11-18/19)", "",
        "Generated by `section7_tables.py` from the turn traces. Metric definitions follow report Section 6.3.",
        "See the notes at the end before using a number.", "",
        "## 7.1 Main results", "",
    ]
    number = 7
    for key, _, title, _ in RUNS:
        parts += [main_table(metrics[key], title, f"{number}{'abcde'[[r[0] for r in RUNS].index(key)]}"), ""]
    parts += ["## 7.2 Results by dialogue category", ""]
    for key, _, title, _ in RUNS:
        if key == "pizza":
            continue
        parts += [category_table(metrics[key], title, f"8{'abcde'[[r[0] for r in RUNS].index(key)]}"), ""]
    parts += [
        "## 7.3 Clarification policy results", "",
        "![Figure 6](figures/fig6_tradeoff.png)", "",
        "**Figure 6 - Accuracy of presented carts against questions per order as the clarification threshold "
        "varies, for C4 (confidence) and C5 (learned), with C2 and C3 as single points (offline replay on the "
        "held-out C2 turn logs). Large markers on the curves are the thresholds fixed in advance (C4 0.85, C5 from validation).**", "",
        "| Test set | C2 | C3 | C4 (0.85) | C5 (fixed threshold) |", "|---|---|---|---|---|",
    ]
    for (key, _, title, _), (_, t) in zip(RUNS, trades):
        cell = lambda p: "--" if p[1] is None else f"{100 * p[1]:.1f}% at {p[0]:.2f} q/order"
        parts.append(f"| {title} | {cell(t['C2'])} | {cell(t['C3'])} | {cell(t['C4_fixed'])} | "
                     f"{cell(t['C5_fixed'])} (t={t['c5_threshold']:.3f}) |")
    c1_latency = ", ".join(f"{SHORT[k]} {metrics[k]['C1']['latency'] / 1000:.1f} s" for k, *_ in RUNS
                           if metrics[k]["C1"]["latency"] > 1000)
    cached = [SHORT[k] for k, *_ in RUNS if metrics[k]["C1"]["latency"] <= 1000]
    if cached:
        c1_latency += f" ({', '.join(cached)} reused an earlier run's cache entirely, so it has no timing)"
    parts += ["", "## Notes on these numbers", "",
        "1. **Comparable to the draft report.** Tables 7a/7b and 8a/8b use the same 200 test dialogues as the "
        "report's Tables 7 and 8 (report: C1 27.0%, C2 43.0%, C3 44.5%, C4 42.0%, C5 50.0% exact-order accuracy). "
        "7a is the rerun after the evaluation fixes; 7b adds the draft clean-up rules, whose rules were taken from "
        "test failures, so 7b is an upper bound, not a held-out result.",
        "2. **v2 (7c-7e, 8c-8d)** is the honest generalisation test: test templates never used in development, "
        "a menu never used in development (B), and 300 human-written PIZZA orders. Removals, multiple items, "
        "multiple problems, quantity limits and partial answers are categories new in v2.",
        "3. **Model.** gpt-oss:20b served locally by Ollama at temperature 0 with a response cache, not "
        "openai/gpt-oss-20b on Groq as in the report's Section 6.6. C5 is a different trained model per run: "
        "v2 (7a), v3 (7b), v4 (7c-7e). C5 v4 picks a threshold that asks on almost every turn, which is why its "
        "completion is near 0% on v2: the dialogue ends on a question once the scripted replies run out.",
        "4. **Missed / unnecessary clarifications** use the outcome definitions of Section 6.3: missed = share of "
        "CONFIRM turns whose cart was wrong; unnecessary = share of questions asked when the draft was already "
        "right. Turns before a scripted correction are excluded. The datasets carry no per-turn need-a-question "
        "annotation, so the annotation-based figure is --.",
        "5. **Invalid drafts (raw)** is the share of all turns whose draft, after the preservation and clean-up "
        "steps but before the policy, fails the validator (any violation or missing required option). "
        "**Invalid drafts at confirmation** is the share of CONFIRM turns whose cart fails it; 0% by construction "
        "with validation on. C5 on v2 test A never confirms, so its value is --.",
        "6. **Successful completion** is the share of dialogues whose last turn is CONFIRM. It depends on the "
        "scripted replies: a dialogue whose replies run out while the assistant is still asking counts as "
        "not completed even if the draft is right (C3 on PIZZA asks on many near-matches, hence 61%).",
        "7. **Line-item F1** is micro-averaged over final carts; a line counts only if item, quantity and the set "
        "of customizations all match. Delivery location is not part of it.",
        f"8. **Latency** is not reported. C1 ran first in each run and filled the response cache, so the later "
        f"configurations mostly read cached answers (1-600 ms) and their times are not comparable. Mean C1 turn "
        f"time, largely uncached, on a local GPU: {c1_latency}. Groq latency was not measured.",
        "9. **Tokens per order** counts prompt plus completion tokens, including cached responses. No cost is "
        "given because the runs used a local model.",
        "10. **Figure 6** replays every policy offline on the C2 turn logs of each test set. A turn the validator "
        "flags is always a question; the policy decides the rest. Accuracy of presented carts = share of "
        "non-question turns whose cart matches gold. C4 sweeps its confidence threshold and C5 its probability "
        "threshold from 0 to 1. The large markers are the thresholds fixed beforehand (C4 0.85; C5 chosen on the "
        "validation split). A point with fewer than 10 presented carts is not scored "
        "(shown as -- in the table and left off the curves): C5 v4 at its fixed threshold asks on nearly every turn.",
    ]
    (ROOT / "SECTION7_RESULTS.md").write_text("\n".join(parts) + "\n", encoding="utf-8")
    json.dump({k: v for k, v in metrics.items()}, open(ROOT / "section7_metrics.json", "w"), indent=1)
    print("\n".join(parts))


if __name__ == "__main__":
    main()
