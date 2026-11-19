# Dataset v2 evaluation (2026-11-19)

Code: commit 9694cdc. Nothing was changed during the run. Model: gpt-oss:20b on Ollama at
temperature 0, with the response cache on and agreement sampling off. C5 is v4
(`artifacts/clarification_policy_v4.joblib`), trained on v2 train and validation.

The test sets measure something v1 could not:
- **Test A:** the v1 menu with wording the system has never seen. Its templates do not
  overlap with train or validation.
- **Test B:** a menu never used in development.
- **PIZZA:** 300 human-written orders.

The fixes from rerun_canonical were derived from v1 test failures, so v1 overstates how
good the system is. v2 is the honest number.

## Headline: exact order accuracy

| Policy | v1 rerun_fixed | v1 rerun_canonical | **v2 test A** | **v2 test B** | **v2 PIZZA** |
|---|---|---|---|---|---|
| C1 model only | 0.465 | 0.585 | 0.374 | 0.275 | 0.420 |
| C2 + validator | 0.765 | 0.955 | 0.763 | 0.650 | 0.810 |
| C3 + missing/near-match rule | 0.800 | 0.990 | **0.773** | 0.655 | 0.810 |
| C4 + confidence | 0.775 | 0.965 | 0.763 | 0.650 | 0.810 |
| C5 v4 learned | 0.795 | 0.985 | 0.773 | 0.660 | 0.810 |

Dialogue counts:
- C2 on the development data: train 0.847 (603 dialogues), validation 0.823 (198).
- Tests: test A 198 dialogues, test B 200, PIZZA 300.

Question behaviour per final turn, as missed / unnecessary / questions per dialogue:

| Policy | Test A | Test B | PIZZA |
|---|---|---|---|
| C2 | 0.22 / 0.01 / 0.61 | 0.16 / 0.01 / 0.90 | 0.10 / 0.00 / 0.63 |
| C3 | 0.20 / 0.08 / 0.69 | 0.15 / 0.05 / 0.93 | 0.08 / 0.32 / 0.90 |
| C4 | 0.24 / 0.01 / 0.59 | 0.16 / 0.01 / 0.91 | 0.10 / 0.00 / 0.63 |
| C5 v4 | 0.00 / **1.00** / 1.78 | 0.02 / **0.97** / 1.88 | 0.02 / **0.87** / 1.39 |

What the numbers say:
1. **Generalisation gap.**
   - New wording costs about 20 points against v1 rerun_canonical (0.99 → 0.77 for C3).
   - A new menu costs another 12 (→ 0.66).
   - Human PIZZA orders land at 0.81.
   - The v1 rerun_canonical figure is an upper bound, as flagged at the time.
2. **The validator is where the gain comes from.** C1 → C2 adds 38–40 points on every set.
3. **C2–C5 differ by at most one point in accuracy.**
   - Almost every remaining failure is a wrong draft, and no question would have fixed it.
   - So the ask-or-confirm policy is no longer the bottleneck; the interpreter and
     draft clean-up are.
4. **C5 v4 is unusable.** It asks on nearly every turn; see below.

## Per category (C3, exact accuracy)

| Category | Train (C2) | Validation (C2) | Test A | Test B |
|---|---|---|---|---|
| clear_request | 1.00 | 1.00 | 0.91 | 0.90 |
| ambiguous_item | 0.75 | 0.59 | 0.95 | 0.80 |
| unavailable_option | 0.90 | 0.86 | 0.91 | 0.85 |
| customization | 0.93 | 1.00 | 0.68 | 0.65 |
| correction | 0.94 | 0.86 | 0.82 | 0.65 |
| removal | 0.61 | 0.41 | **0.00** | **0.00** |
| multi_item | 0.99 | 1.00 | 0.95 | 0.75 |
| multi_problem | 0.54 | 0.68 | 0.73 | 0.65 |
| quantity_limit | 0.99 | 1.00 | 1.00 | 1.00 |
| partial_answer | n/a | n/a | n/a | 0.30 |

## Failure causes (from the traces)

Counts are C3 final turns unless stated. Dev means train and validation.

### 1. Removal phrasing is not recognised
- **Size:** 22/22 on test A, 19/20 on test B, about half of dev.
- **What happens:** `_preserve_untouched` treats a turn as a removal only if it contains
  remove, delete, drop, cancel, without or "no longer" (`services.py`).
  - The test replies say "Never mind the X." or "Scratch the X."
  - Dev paraphrases say "can we take the X out?"
  - In each case the model drops the line, and preservation puts it back
    (`restored_missing_line`).
- **Result:** the draft is valid, so no policy can catch it.
- **Fix:** add the cues "never mind", "scratch", "take … out", "get rid of", "forget" and
  "don't want".
- **Why not just add words:** the word list will always miss some phrasings.
  - Better: let the model's removal stand whenever the turn names that line and gives no
    new item for it.
  - Choose this rule on dev failures, not on these test ones.

### 2. Stated location dropped (test B)
- **Size:** 33 of 195 first turns on test B, against 5 of 193 on test A.
- **What happens:** the location is in the message, but the model returns null.
  - It happens mostly with phrasings such as "Can Calcia Hall get a lamb curry?" and
    "Order for College Hall: …".
  - It also happens with some "Hey, I'm at College Hall! …" messages.
  - The prompt was not truncated: the Ollama log shows none apart from 2 repeat-limit
    turns.
- **Impact:** it accounts for most of test B's REPAIR finals.
  - partial_answer: 11 of 14 failures.
  - customization: 6; multi_item: 5.
- **Fix:** a deterministic fallback in `canonicalize_draft` fills the location when the
  model returns null and the transcript names exactly one known delivery location.
  - It would use the `AI_DELIVERY_LOCATIONS` setting.
  - Until then, the validator asks, and the customer has to repeat themselves.

### 3. Customization errors (PIZZA 50 of 57 failures, test A and B customization)
- **Group prefix not stripped:** 19 options came back as "Toppings: Black olives" or
  "Size (required): Extra large".
  - `_canonical_option` only strips an exact group name.
  - "(required)" and options with a near-miss name ("Black olives" for "Olives") get
    through.
- **Negations returned as options:** 19 options came back as "No Sausage" or "Hold Tuna"
  and are rejected as `invalid_customization`.
  - They should be dropped, because the base item has no default toppings.
- **Toppings missed:** 18 dialogues, for example "olives sausage but without tuna"
  → no toppings.
- **Identical lines merged:** "one large with sausage and peppers, one large with ham
  and olives, …" came back as three copies of one line.
  - This is the known line_id gap: lines of the same item are keyed by
    `menu_item_id`.

### 4. Vague line not replaced (multi_problem, dev and test)
- **What happens:**
  - The customer first says "a burger".
  - The model makes a placeholder line, and the reply names "a veggie burger".
  - The model adds the new line, and preservation restores the placeholder, which leaves
    an extra line.
- **Fix:** when a reply resolves an `unknown_item` or near-match line, replace that line
  instead of keeping it.

### 5. Quantity lost when an ambiguous item is resolved (dev)
- "Two wraps … The veggie one." ends as 1 × veggie wrap.

### 6. Dataset issues (not system failures)
- **Paraphrase changed the meaning:** one dev removal was paraphrased to "can we
  actually swap out that veggie wrap?".
  - The anchor check keeps item words, not the intent.
  - Removal and correction paraphrases need an intent check or should be skipped.
- **Ambiguous PIZZA gold parses:** a few are debatable ("without ham and tuna chicken on
  top"). They are left as they are, because they are rare.
- **Odd paraphrase output:** some paraphrases add emoji or "??". The paraphraser keeps
  them; this is harmless but not realistic kiosk input.

## Why C5 v4 asks every time

- **Two problems with the training data:**
  - On v2 dev data 47% of the labelled C2 turns are wrong (399/912 train, 147/310
    validation), compared with 33–36% on v1 (275/844, 108/300).
  - The bigger change is that on v1 nearly every wrong turn showed up in the signals.
    On v2, many wrong turns look valid to all seven:
    - 13 of 22 removal turns
    - 19 of 41 customization turns
    - 3 corrections
    - the multi_problem extra lines
- **What the cost rule then picks:**
  - With a missed question costing 5 and an unnecessary one costing 1, asking every time
    costs 163 on validation.
  - Never asking costs 735.
  - Ranking quality fell from AUROC 0.98 on v1 to 0.84, which is not good enough for any
    threshold to beat asking every time.
  - The training command picked threshold 0.160, with 99.4% unnecessary questions on
    validation, without warning.
- **What this means:**
  - C5's signals describe the problems the validator can see.
  - The v2 errors are mostly invisible to it, and asking a question doesn't repair them
    anyway, since the draft is already wrong.
  - So the fix is upstream, in causes 1–4, not a better classifier.
- **Code fix:** `train_clarification_policy` should refuse, or loudly flag, a threshold
  whose validation unnecessary rate is above a set limit (for example 0.5).

## Recommendation

- **Default policy: C3 (rule-based, no artifact).**
  - It ties for the best accuracy on every set and catches the most missing details.
  - Its cost is more unnecessary questions on PIZZA (0.32), where the near-match rule
    fires on "pizza" (S3 = 13 candidates).
  - C4 is the alternative if fewer questions matter more. It has the same accuracy and
    almost no unnecessary questions, but misses a few more.
  - `AI_DEFAULT_POLICY` currently defaults to C5. It should be C3 until C5 is retrained
    on data where it can work.
- **Do not deploy C5 v4.** It is committed only so the results can be reproduced.

## Next steps

1. Fix causes 1 to 4. Choose each rule from the train and validation traces only, never
   from test A, test B or PIZZA.
2. Re-run on v2 test A, test B and PIZZA once, and report the change. After that, v2 test
   is "seen", so a later round needs fresh test templates (a v3 test set), or ideally
   real kiosk requests.
3. Add the threshold check to `train_clarification_policy`, then retrain C5 on the fixed
   pipeline.

## Files

- `train/`, `validation/`: C2 traces and features used to train C5 v4.
- `test_a/`, `test_b/`, `pizza/`: C1–C5 traces, features, `summary.json`, and the
  offline `policy_replay.json`.
- The PIZZA result files hold ids, item ids and features only, no customer text. The
  input file stays git-ignored, as `data/v2/SOURCES.md` requires.
