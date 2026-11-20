# Dataset v3 sources and licences

## PIZZA (Amazon Science), CC BY-NC 4.0

- Source: https://github.com/amazon-science/pizza-semantic-parsing-dataset, the human-written
  `PIZZA_dev.json` and `PIZZA_test.json`. Paper: Arkoudas et al., 2022,
  https://arxiv.org/abs/2212.00265.
- `data/v2/convert_pizza.py` maps 1,228 of the 1,705 orders exactly onto Slice Factory (vendor 6),
  shuffles them with seed 11 and writes two disjoint sets. Both files are git-ignored.
  - **Seed-P:** the first 300, in `data/external/pizza_human.jsonl`. These were already used in
    dataset v2.
  - **External-P:** the next 100, in `data/external/pizza_external_p.jsonl`. These were never run,
    read or used for anything before the v3 evaluation. Their PIZZA ids are listed in
    `external_p_source_ids.json`.
- How v3 uses Seed-P:
  - `pizza_seed` dialogues are a Seed-P customer's own text with one detail changed (a topping,
    the size, a drink or a quantity). They contain edited PIZZA text.
  - Every other dialogue is rewritten in a Seed-P customer's style, without copying their text.
- **Licence:** CC BY-NC 4.0 allows sharing adapted material for non-commercial use with
  attribution and a note of changes. This file is that attribution and note. Do not use dataset v3
  commercially.

## Taskmaster-1 (Google Research), CC BY 4.0

- No text is used. The test-split reply templates (from `data/v2/generate_v2.py`) follow customer
  phrasings attested in Taskmaster-1; see `data/v2/SOURCES.md`.

## Models used to build the data

- **qwen3.5:9b** (Ollama) rewrites messages in a seed customer's style and edits the seed orders.
- **Not used:** the model under test (gpt-oss:20b) and the second model (gemma3:12b) are not used
  to build the data.
