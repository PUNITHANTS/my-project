"""Paired statistics for one evaluation folder (step 11 of the v3 plan).

    python data/v3/stats_v3.py data/evaluations/v3/test [--metric completed_exact]

Reads progress.jsonl (one row per policy and dialogue) and writes stats.json:
* each policy's rate with a Wilson 95% confidence interval
* exact McNemar tests for every pair of policies on the same dialogues
"""

import argparse
import json
import math
from itertools import combinations
from pathlib import Path


def wilson(successes, n, z=1.959964):
    if not n:
        return None, None
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value from the discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("--metric", default="completed_exact", choices=["completed_exact", "exact"])
    args = parser.parse_args()
    folder = Path(args.folder)
    results = {}
    for line in open(folder / "progress.jsonl", encoding="utf-8"):
        row = json.loads(line)
        results.setdefault(row["policy"], {})[row["dialogue_id"]] = bool(row[args.metric])
    out = {"metric": args.metric, "policies": {}, "pairs": []}
    for policy, by_dialogue in sorted(results.items()):
        n, k = len(by_dialogue), sum(by_dialogue.values())
        low, high = wilson(k, n)
        out["policies"][policy] = {"n": n, "successes": k, "rate": k / n, "ci95": [low, high]}
    for a, b in combinations(sorted(results), 2):
        shared = sorted(set(results[a]) & set(results[b]))
        only_a = sum(results[a][d] and not results[b][d] for d in shared)
        only_b = sum(results[b][d] and not results[a][d] for d in shared)
        out["pairs"].append({"a": a, "b": b, "n": len(shared), "a_only": only_a, "b_only": only_b,
                             "p_value": mcnemar_exact(only_a, only_b)})
    (folder / f"stats_{args.metric}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for policy, row in out["policies"].items():
        print(f"{policy}: {row['rate']:.3f} [{row['ci95'][0]:.3f}, {row['ci95'][1]:.3f}] n={row['n']}")
    for pair in out["pairs"]:
        print(f"{pair['a']} vs {pair['b']}: {pair['a_only']} vs {pair['b_only']} discordant, p={pair['p_value']:.4f}")


if __name__ == "__main__":
    main()
