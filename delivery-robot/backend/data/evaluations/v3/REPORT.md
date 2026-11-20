# Dataset v3 evaluation (2026-11-20)

This is the experiment redo of `data/v3/README.md`.

**Setup:**
- Menu: `menu_snapshot_v3.json` (10 restaurants, 74 items), frozen.
- Data: 1,000 dialogues (600/200/200) generated from 300 human PIZZA seeds, split by seed. External-P
  is 100 held-out human PIZZA orders that were never used before.
- Model under test: gpt-oss:20b on Ollama at temperature 0, with response caching. The second
  model is gemma3:12b.
- C5 v5 (`artifacts/clarification_policy_v5.joblib`) was trained on train 600 and its threshold
  chosen on validation 200. Test-200 and External-P were only evaluated.

## Metrics

- **Completed exactly**: the assistant reached CONFIRM with the gold order. This is the headline
  task metric.
- **Last draft exact**: the final draft equals the gold order, even if the assistant was still
  asking a question. This is the metric earlier reports used.
- **Line-item F1**: lines must match item, quantity and options.
- **Confirmed wrong**: dialogues confirmed with an order that is not the gold order.
- **Missed / unnecessary questions**: per turn.
- **Intervals**: Wilson 95%.
- **p-values**: exact McNemar on the same dialogues (`stats_*.json`).

## Main results: gpt-oss:20b on Test-200

| Policy | Completed exactly | Last draft exact | Line-item F1 | Item-only F1 | Confirmed wrong | Invalid at confirmation | Missed / unnecessary | Questions per dialogue |
|---|---|---|---|---|---|---|---|---|
| C1 model only | 0.510 [0.441, 0.578] | 0.510 | 0.581 | 0.873 | 48.5% | 42.5% | 78% / 0% | 0.14 |
| C2 + validator | **0.845** [0.788, 0.889] | 0.845 | 0.871 | 0.952 | 8.0% | 0% | 11% / 0% | 0.68 |
| C3 + missing/near-match | 0.770 [0.707, 0.823] | **0.855** | 0.877 | 0.962 | 6.5% | 0% | 9% / 10% | 0.79 |
| C4 + confidence | **0.845** [0.788, 0.889] | 0.845 | 0.871 | 0.952 | 7.5% | 0% | 10% / 0% | 0.69 |
| C5 v5 learned | 0.350 [0.287, 0.418] | **0.855** | 0.880 | 0.964 | **4.5%** | 0% | **6%** / 59% | 1.34 |

**Paired tests on completed exactly (McNemar):**
- C1 is worse than every other policy (p < 0.002).
- C2 = C4: identical results on every dialogue.
- C2 and C4 beat C3 (17 vs 2 discordant, p = 0.0007).
- C2, C3 and C4 all beat C5 (p < 0.0001).

**On last draft exact**, C2–C5 do not differ (0.845–0.855, every pair p ≥ 0.5). Only C1 differs
(p < 0.0001).

### Why completed and draft-exact differ for C3 and C5

- **Where the gap is:**
  - C5: 101 dialogues.
  - C3: 17 dialogues.
- **What happens in each:**
  - The final draft is correct and passes the validator.
  - The policy still asks one more question.
  - The scripted customer has no reply left, so the dialogue ends without CONFIRM.
- **How to read it:**
  - Completed exactly treats an unnecessary question at the end as a lost order. That is the
    strictest reading.
  - A real customer would answer "yes, that's right". Whether the policy then confirms or asks
    again is not tested here.
  - Draft-exact shows that C3 and C5 build orders as well as C2 and C4.
- **Why C5 asks so much:**
  - It was trained with a missed question costing 5 times an unnecessary one.
  - Its threshold (0.186) asks on 48% of correct validation drafts, just under the 50% limit
    that `train_clarification_policy` refuses.
- **What C5 buys for it:** the fewest missed questions (6%) and the fewest wrong orders confirmed
  (4.5%).
- **Ranking quality:** on Test-200 C5 ranks drafts well (AUROC 0.878, calibration error 0.049). The
  problem is how high it puts the bar, not how it ranks.

### Per category, completed exactly (Test-200)

| Category | n | C1 | C2 | C3 | C4 | C5 |
|---|---|---|---|---|---|---|
| clear_request | 17 | 1.00 | 1.00 | 0.94 | 1.00 | 0.35 |
| ambiguous_item | 17 | 0.24 | 0.76 | 0.71 | 0.76 | 0.24 |
| unavailable_option | 17 | 0.53 | 0.94 | 0.88 | 0.94 | 0.24 |
| customization | 17 | 0.18 | 0.59 | 0.59 | 0.59 | 0.29 |
| correction | 17 | 1.00 | 1.00 | 0.94 | 1.00 | 0.24 |
| removal | 17 | 1.00 | 1.00 | 0.94 | 1.00 | 0.12 |
| multi_item | 17 | 0.94 | 0.94 | 0.94 | 0.94 | 0.65 |
| multi_problem | 17 | 0.24 | 0.41 | 0.41 | 0.41 | 0.41 |
| quantity_limit | 16 | 0.00 | 1.00 | 1.00 | 1.00 | 0.31 |
| partial_answer | 16 | 0.00 | 0.94 | 0.94 | 0.94 | 0.62 |
| same_name | 16 | 0.44 | 0.81 | 0.50 | 0.81 | 0.31 |
| pizza_seed (edited human text) | 16 | 0.50 | 0.75 | 0.44 | 0.75 | 0.44 |

### C2 failures on Test-200 (31 dialogues, from the traces)

| Cause | Dialogues |
|---|---|
| multi_problem: a required option still missing at the end | 6 |
| customization: wrong quantity or option | 5 |
| Wrong item picked (ambiguous items 2, same-name items 2) | 4 |
| Edited pizza orders: a topping missed, or an item not identified | 4 |
| Two restaurants mixed in one order | 3 |
| Others (one or two each) | 9 |

There is no single dominant bug, unlike v2's removals.

## External evaluation: gpt-oss:20b on External-P (100 held-out human orders)

| Policy | Completed exactly | Last draft exact | Line-item F1 | Confirmed wrong | Missed / unnecessary | Questions per dialogue |
|---|---|---|---|---|---|---|
| C1 | 0.41 [0.32, 0.51] | 0.41 | 0.598 | 54% | 86% / 0% | 0.09 |
| C2 | **0.77** [0.68, 0.84] | 0.77 | 0.804 | 8% | 12% / 0% | 0.61 |
| C3 | 0.55 [0.45, 0.64] | 0.77 | 0.804 | 4% | 6% / 29% | 0.87 |
| C4 | 0.75 [0.66, 0.83] | 0.77 | 0.804 | 8% | 12% / 3% | 0.63 |
| C5 | 0.54 [0.44, 0.63] | 0.77 | 0.804 | **3%** | **4%** / 30% | 0.89 |

- **Same pattern as Test-200**, about 8 points lower: C2 and C4 lead on completion, and all four
  of C2–C5 build the same drafts.
- **C5 on External-P:** ranking quality AUROC 0.897, unnecessary questions 30%.
- **The 23 C2 failures:**

  | Cause | Orders |
  |---|---|
  | Option not on the menu, left for the customer to fix | 9 |
  | Item not identified | 6 |
  | Topping or size wrong | 5 |
  | Wrong location | 2 |
  | Wrong quantity | 1 |

## Cross-model check: gemma3:12b, same pipeline, C1 and C5

| Set | Policy | Completed exactly | Last draft exact | Line-item F1 | Item-only F1 | Confirmed wrong |
|---|---|---|---|---|---|---|
| Test-200 | C1 | 0.110 [0.074, 0.161] | 0.110 | 0.293 | 0.582 | 87% |
| Test-200 | C5 | 0.100 [0.066, 0.149] | 0.120 | 0.407 | 0.634 | 8% |
| External-P | C1 | 0.030 [0.010, 0.085] | 0.030 | 0.323 | 0.620 | 96% |
| External-P | C5 | 0.020 [0.006, 0.070] | 0.030 | 0.311 | 0.609 | 4% |

gpt-oss:20b on the same sets: C1 0.510 / 0.41 and C5 0.350 / 0.54.

- **gemma3:12b is far weaker as the interpreter.**
  - Two thirds of its failed Test-200 drafts (122 of 178) list the delivery place as an extra,
    unidentified item.
  - Removing those lines would rescue only 23 dialogues. It also picks the wrong menu items (item-only
    F1 0.58, against 0.87–0.96 for gpt-oss).
- **The pipeline still protects the customer.** With C5, gemma confirms a wrong order in 8% of
  Test-200 dialogues, against 87% with C1. The validator and policy turn a weak model into one that
  asks instead of confirming wrong orders, but they cannot make it build the right order.
- **No pipeline changes for gemma.** The pipeline was not adapted for gemma, as the plan requires.
- **A bug the gemma run found:**
  - The first gemma run crashed because the model picked an unavailable item named in full, which
    hit a bug in the same-name check.
  - It is fixed in `services.py` with a regression test.
  - The gpt-oss runs could not have hit it, since that path always crashed.

## Conclusions

1. **Main claim (Test-200):**
   - The menu validator is what makes the assistant usable: completed orders go from 0.51 to 0.845,
     and confirmed-wrong orders from 48.5% to 8%.
   - The ask-or-confirm policies on top of it (C3–C5) do not build better orders (draft-exact
     0.845–0.855, not significant).
   - They trade completion for safety. C5 confirms the fewest wrong orders (4.5%) but asks too
     often under strict completion.
   - For the kiosk, **C4 or C2** gives the best completion. **C3**, the current default, is a
     middle ground.
2. **External claim (External-P):** the same ordering holds on unseen human pizza orders, about 8
   points lower: C2 0.77 against 0.845.
3. **Cross-model:** a smaller model (gemma3:12b) collapses as the interpreter (0.11), so the model
   is the bottleneck. With C5 the pipeline still keeps confirmed-wrong orders low.
4. **Leakage:** no External-P order was used for generation, training or tuning, and no seed's
   dialogues appear in two splits (`data/v3/manifest.json`). C5's threshold came from validation
   only.

## Limitations

- **Strict completion:** completion ends the dialogue at the first question beyond the script. The
  suggested follow-up adds a scripted "yes, that's right" reply to unscripted questions and re-runs
  Test-200 and External-P.
- **Generated data:** Test-200 is generated, not real kiosk traffic. Only 16 test dialogues per
  split keep real human text (pizza_seed), and External-P covers pizza orders only.
- **Small sets:** at n = 200 a 95% interval is about ±5–7 points, and at n = 100 about ±9.
- **C5 cost setting:** C5's behaviour depends on the cost ratio of 5 to 1. A different ratio would
  give a different threshold, and none was tuned here.

## Files

| Folder | Contents |
|---|---|
| `train/`, `validation/` | C2 traces and features used to train C5 v5 |
| `test/`, `external_p/` | C1–C5 summaries, traces, features, `policy_replay.json`, `stats_completed_exact.json`, `stats_exact.json` |
| `test_gemma3_12b/`, `external_p_gemma3_12b/` | the same for gemma3:12b, C1 and C5 |

The External-P folders hold ids, item ids and features only, no customer text.
