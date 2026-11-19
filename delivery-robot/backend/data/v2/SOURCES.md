# Dataset v2 external sources

Neither dataset is redistributed in this repository. `build_v2.py` reads local
downloads in `data/external/raw/` (git-ignored) and writes any file containing their
text to `data/external/` (also git-ignored).

## PIZZA (Amazon Science)

- Source: https://github.com/amazon-science/pizza-semantic-parsing-dataset, files
  `data/PIZZA_dev.json` (148 KB) and `data/PIZZA_test.json` (584 KB). These are the
  human-written splits; the synthetic training set is not used.
- Paper: Arkoudas et al., "PIZZA: A new benchmark for complex end-to-end task-oriented
  parsing", 2022, https://arxiv.org/abs/2212.00265
- License: CC BY-NC 4.0 (non-commercial). Used here for non-commercial university
  research only.
- Use: `convert_pizza.py` maps each order's parse onto the Slice Factory vendor of the
  held-out menu (`menu_snapshot_b.json`). Of 1,705 orders, 1,228 map exactly. The
  rest are dropped: unsupported drink sizes and containers, toppings or styles we
  don't sell, "light" or extra non-cheese toppings, and similar. 300 are sampled into
  `data/external/pizza_human.jsonl`. The customer text is unchanged except for an
  appended ", deliver to <location>" (or a scripted location reply for 30% of
  orders that need nothing else). Gold orders come from the parse.

## Taskmaster-1 (Google Research)

- Source: https://github.com/google-research-datasets/Taskmaster, file
  `TM-1-2019/self-dialogs.json` (66 MB).
- Paper: Byrne et al., "Taskmaster-1: Toward a Realistic and Diverse Dialog Dataset",
  EMNLP 2019, https://arxiv.org/abs/1909.05358
- License: CC BY 4.0.
- Use: no text is copied into the dataset. The 2,844 pizza- and coffee-ordering
  dialogues were mined for how customers phrase answers and corrections. The
  test-template replies in `generate_v2.py` follow the attested patterns:
  - terse option answers ("large please.", "grande.", "a large, please.": 947 short
    size answers)
  - "make it a large", "let's go with …", "on second thought …", "wait, I want to
    change …", "instead of the …" (951 correction-cue turns)
