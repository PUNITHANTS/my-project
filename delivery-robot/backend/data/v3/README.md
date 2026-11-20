# Dataset v3 and the experiment redo

This folder holds the redo plan's data, scripts and commands. All paths are relative to
`delivery-robot/backend`.

## What is where

| What | Path | In git |
|---|---|---|
| Frozen menu (10 restaurants, 74 items) | `data/v3/menu_snapshot_v3.json` (built by `make_menu_v3.py`) | yes |
| Generation-only wording hints | `data/v3/hints_menu_v3.json` | yes |
| Seed-P (300 human PIZZA orders, expansion seeds) | `data/external/pizza_human.jsonl` | no (licence) |
| External-P (100 held-out human PIZZA orders) | `data/external/pizza_external_p.jsonl`; ids in `data/v3/external_p_source_ids.json` | ids only |
| Which seeds fed which split | `data/v3/seed_split.json` | yes |
| All 1,000 dialogues | `data/v3/dialogues.jsonl` (field `split`) | yes |
| Splits | `data/v3/splits/{train,validation,test}.jsonl` | yes |
| Plain-English copy (format of the v1 Word file) | `data/v3/dialogues_v3.docx` | yes |
| Counts, gold check and leakage check | `data/v3/manifest.json` | yes |
| C5 model | `artifacts/clarification_policy_v5.joblib` | yes |
| Results | `data/evaluations/v3/<run>/summary.json`, `stats_*.json`, `policy_replay.json`, traces | yes |

## Leakage rules and how they are enforced

- **External-P is never read** by generation, training or tuning.
  - It is cut from the PIZZA pool before anything else: orders 301–400 of the shuffled pool, which
    were never run in v2.
  - `build_v3.py` fails if any dialogue's seed is an External-P id.
- **Seeds stay in one split.** Seed-P is split 180 / 60 / 60 into train / validation / test seed
  pools before generation. Each dialogue records its seed as `source_group`, and `build_v3.py`
  fails if one seed appears in two splits.
- **Test wording is separate.** Test-200 uses the v2 test sentence templates; train and validation
  use the dev templates.
- **Tuning uses only train and validation.** C5 is trained on train and its threshold is chosen on
  validation. Test-200 and External-P are only evaluated.

## Commands

1. Build the data. This needs Ollama with qwen3.5:9b, and the PIZZA downloads described in
   `data/v2/SOURCES.md`:

   ```
   python data/v2/convert_pizza.py data/external/raw/PIZZA_test.json data/external/raw/PIZZA_dev.json --out data/external/pizza_human.jsonl --sample 300 --holdout 100 --holdout-out data/external/pizza_external_p.jsonl
   python data/v3/build_v3.py
   ```

2. Run the evaluation, plan steps 7–11. This needs Ollama with gpt-oss:20b and gemma3:12b:

   ```
   powershell -ExecutionPolicy Bypass -File data/v3/run_eval_v3.ps1
   ```

3. Run the statistics for one result folder (`run_eval_v3.ps1` already does this):

   ```
   python data/v3/stats_v3.py data/evaluations/v3/test --metric completed_exact
   ```

## Metrics (`summary.json`)

- `completed_exact_rate`: the assistant reached CONFIRM with exactly the gold order, and the order
  is valid. This is the headline metric.
- `exact_order_accuracy`: the last draft matches gold, even if the assistant was still asking. This
  is the older metric. It overstates a policy that keeps asking, which is how C5 v4 scored 0.77
  while asking on every turn.
- `line_item_f1`, `line_item_precision`, `line_item_recall`: lines must match item, quantity and
  options. `item_only_f1` checks the menu item only.
- `invalid_at_confirmation_rate`: confirmed orders that fail the menu check.
- `wrong_at_confirmation_rate`: confirmed orders that differ from gold.
- `missed_clarification_rate` and `unnecessary_clarification_rate` are per turn.
  `questions_per_dialogue` and `mean_turns_per_dialogue` are per dialogue.
- `stats_completed_exact.json` and `stats_exact.json` give Wilson 95% intervals and exact McNemar
  tests between policies on the same dialogues.
