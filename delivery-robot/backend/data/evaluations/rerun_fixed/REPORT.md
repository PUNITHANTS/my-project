# C1–C5 rerun after the evaluation fixes (2026-11-18)

Model: `gpt-oss:20b` (MXFP4) on a local RTX 5070 Ti through Ollama 0.40, temperature 0,
reasoning effort low, S5 off (`AI_SAMPLE_AGREEMENT_K=0`). Same 1,000-dialogue dataset,
splits and menu snapshot as the earlier run in `../full`.

Steps (`run_eval.ps1` in this folder, about 5.7 h in total):

1. C2 on train (600) and validation (200) to collect C5 features.
2. C5 retrained into `artifacts/clarification_policy_v2.joblib` (the old model is untouched).
3. C1–C5 on the 200 held-out test dialogues, with traces.
4. Offline replay of the five policies on the test C2 features (`policy_replay.json`).

Two turns hit Ollama's "token repeat limit" abort and were retried at temperature 0.3 with
a fixed seed (see `groq_client._post_with_rate_limit_retry`); every other turn is greedy.

## Exact-order accuracy on the test split (200 dialogues)

The "before" column is the earlier run (`../full/progress.jsonl`) restricted to the same 200
test dialogue ids, so both columns score the same dialogues. Before, C5 used the old
artifact; now it uses v2.

| Policy | Before | Now | Missed question | Unnecessary question | Questions / dialogue |
|---|---|---|---|---|---|
| C1 model only | 0.270 | 0.465 | 0.682 | 0.011 | 0.26 |
| C2 + validator | 0.430 | 0.765 | 0.100 | 0.000 | 0.66 |
| **C3 + rules** | 0.445 | **0.800** | 0.050 | 0.043 | 0.73 |
| C4 + confidence | 0.420 | 0.775 | 0.086 | 0.026 | 0.69 |
| C5 + learned | 0.515 | 0.795 | 0.007 | 0.098 | 0.80 |

Invalid final draft rate: C1 0.465, C2–C5 0.165.

### By category (now; before in brackets)

| Policy | ambiguous_item | clear_request | correction | customization | unavailable_option |
|---|---|---|---|---|---|
| C1 | 0.275 (0.075) | 0.850 (0.950) | 0.825 (0.050) | 0.175 (0.175) | 0.200 (0.100) |
| C2 | 0.600 (0.150) | 0.850 (0.800) | 0.825 (0.100) | 0.725 (0.850) | 0.825 (0.250) |
| C3 | 0.775 (0.100) | 0.850 (0.825) | 0.825 (0.225) | 0.725 (0.875) | 0.825 (0.200) |
| C4 | 0.650 (0.100) | 0.850 (0.850) | 0.825 (0.100) | 0.725 (0.825) | 0.825 (0.225) |
| C5 | 0.750 (0.225) | 0.850 (0.950) | 0.825 (0.200) | 0.725 (0.950) | 0.825 (0.250) |

**Customization got worse** (0.85–0.95 → 0.725), and clear requests did for C1 and C5.
The likely cause is the compact menu format introduced for this run: options are listed as
`Size (required): Regular, Large`, and the model then writes `"Size: Regular"`, which the
validator rejects (11 of C3's 40 failures). The earlier run also used a different
provider, so the model may differ too.

## What the numbers do and do not show

- C3 vs C5 differ by one dialogue (C3 right and C5 wrong on `dialogue-0209`, never the
  reverse). That is no evidence either way.
- C3 beats C2 on 7 dialogues and C4 on 5, all `ambiguous_item`, with no dialogue going the
  other way: the near-match rule is what helps.
- C5 v2 ranks turns very well offline (AUROC 0.995, Brier 0.033, ECE 0.069) and almost never
  misses a needed question (0.7%), but asks 2.3× as many unnecessary questions as C3
  (9.8% vs 4.3%) for the same accuracy.
- Assistant fixes and scoring fixes land together, so this run cannot say how much each
  contributed. The traces allow rescoring under the old rules without new model calls.
- The dataset is 1,000 template dialogues; 200 test dialogues give roughly ±5–6 points of
  noise on an accuracy around 0.8.

## Remaining failures (C3, 40 of 200)

All 40 end after the simulated customer's scripted replies are used up; 33 end on an open
ASK or REPAIR (the assistant knew it was not done) and 7 on a wrong CONFIRM.

| Cause | Dialogues | Example | Fix |
|---|---|---|---|
| Option written as `Group: Option` | 11 | `202 ×2 ["Size: Regular"]`, gold `["Regular"]` | Normalise `<group name>: <option>` to `<option>` in the validator, or change the menu format |
| Option named in the reply is dropped | ~20 | "Two regular berry smoothies." → `501 ×2 []` | Same normaliser plus a prompt line; or add the option from the reply by matching option names |
| "Two X, one of them with no mayo" → 2 + 1 lines | 4 | `104 ×2 [] + 104 ×1 [No mayo]` | Prompt example; long term the `line_id` gap from the review |
| Correction keeps the replaced line | 2 | "Change that to three spicy…" kept the classic burger | Do not restore a line when the turn says "change that / instead" |
| Wrong option on a split line | 1 | `dialogue-0738` | — |

The first two account for about three-quarters of the remaining failures and are
deterministic post-processing, not model changes.

## Recommendation

Use **C3** as the kiosk default (`AI_DEFAULT_POLICY=C3`, already set in `.env`):

- It ties C5 on accuracy and asks fewer unnecessary questions.
- It needs no trained artifact.
- It is explainable: the assistant asks when details are missing or 2+ items are close
  matches.

Keep C5 v2 as the research comparison. Revisit it after dataset v2, which has harder cases
where a learned threshold has room to beat fixed rules.

## Files

- `summary.json`: per-policy metrics including `by_category`.
- `c*_features.jsonl`: per-turn signals and labels (`label_valid` marks turns before a
  scripted correction).
- `c*_trace.jsonl`: per-turn draft, action, violations and gold, with no transcripts.
- `policy_replay.json`: offline replay of the five policies on the C2 test features.
- `../../../artifacts/clarification_policy_v2.joblib`: the retrained C5.
- `train/`, `validation/`: C2 runs used to train C5 v2 (train 0.72, validation 0.76 exact).
