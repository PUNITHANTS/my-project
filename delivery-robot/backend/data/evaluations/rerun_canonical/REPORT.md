# C1–C5 after the draft clean-up rules (2026-11-19)

Same setup as `../rerun_fixed` (local `gpt-oss:20b`, temperature 0, same splits and menu),
plus `canonicalize.py` and the "change that to" replacement rule (commit `3fc59f6`).
Run with `../rerun_fixed/run_eval.ps1 -OutRoot data/evaluations/rerun_canonical
-PolicyModel artifacts/clarification_policy_v3.joblib`.

The run took 90 seconds. The clean-up runs after the model call, so all but 11 model
requests were identical to the previous run and came from the response cache.

## Exact-order accuracy

| Policy | Earlier run (same 200) | rerun_fixed | **This run** | Missed q. | Unnecessary q. | Questions / dialogue |
|---|---|---|---|---|---|---|
| C1 | 0.270 | 0.465 | 0.585 | 0.624 | 0.009 | 0.26 |
| C2 | 0.430 | 0.765 | 0.955 | 0.088 | 0.000 | 0.47 |
| **C3** | 0.445 | 0.800 | **0.990** | 0.020 | 0.035 | 0.54 |
| C4 | 0.420 | 0.775 | 0.965 | 0.069 | 0.031 | 0.51 |
| C5 (v3) | 0.515 | 0.795 | 0.985 | 0.029 | 0.065 | 0.56 |

All policies except C1 now end with a valid draft (invalid final draft 0.0; C1 0.37).

C2 on the splits used to train C5: train 0.72 → 0.947, validation 0.76 → 0.96.

### By category (this run)

| Policy | ambiguous_item | clear_request | correction | customization | unavailable_option |
|---|---|---|---|---|---|
| C1 | 0.375 | 1.000 | 1.000 | 0.350 | 0.200 |
| C2 | 0.825 | 1.000 | 1.000 | 0.950 | 1.000 |
| C3 | 1.000 | 1.000 | 1.000 | 0.950 | 1.000 |
| C4 | 0.875 | 1.000 | 1.000 | 0.950 | 1.000 |
| C5 | 0.975 | 1.000 | 1.000 | 0.950 | 1.000 |

Clean-up rules applied in C3's test turns: 23 required options filled from the customer's
words, 12 group-prefixed options mapped, 5 "one of them" splits fixed, 1 empty option
dropped.

## Remaining C3 failures (2 of 200)

- `dialogue-0721`: "Two grilled chicken burgers, one of them with no mayo" came back as one
  line of two with "No mayo". There is no second line to split, and this needs the
  `line_id` work.
- `dialogue-0738`: "Two spicy chicken burgers, one of them with mayo" came back as Mayo +
  No mayo. The model invented the second option.

## Caveats: read before quoting 0.99

- **The rules were written after reading the test-split failures.** The test split is no
  longer an unseen test of them. Train went up just as much (C2 0.72 → 0.947) without
  being looked at, so they are not fitted to the 40 test dialogues alone.
- **All splits come from the same ~245 templates**, so a rule that fixes a template fixes
  it in every split. That means 0.99 measures this dataset, not real customers.
- These numbers need confirming on dataset v2: held-out templates, harder cases,
  paraphrases and real student requests. Until then, the rerun_fixed numbers (0.80) are
  the honest "before rules" baseline and these are an upper bound.

## Recommendation (unchanged)

Use **C3** as the kiosk default: it ties C5 (one dialogue apart) with about half the
unnecessary questions and no trained artifact. C5 v3 is in
`artifacts/clarification_policy_v3.joblib` (AUROC 0.989 offline).
