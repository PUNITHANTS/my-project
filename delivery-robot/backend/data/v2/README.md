# Dataset v2

v1 (`data/dialogues.jsonl`) came from ~245 sentence shapes on one menu, and every split
shared them. A fix for a template then fixed it in every split, so v1 test scores
overstate how the assistant handles new wording or new restaurants. v2 tests both.

| File | Menu | Templates | Dialogues | Use |
|---|---|---|---|---|
| `splits/train.jsonl` | A (`../menu_snapshot_v1.json`) | dev | ~600 | C5 training |
| `splits/validation.jsonl` | A | dev | ~200 | C5 threshold |
| `splits/test_a.jsonl` | A | **test only** | ~200 | new wording, same menu |
| `splits/test_b.jsonl` | **B** (`menu_snapshot_b.json`, never used in development) | test only | 200 | new restaurants |
| `../external/pizza_human.jsonl` | B, Slice Factory | **human-written** (PIZZA) | 300 | real customer wording, git-ignored |

Categories:
- **From v1:** clear_request, ambiguous_item, unavailable_option, customization
  (missing required option and "one of them" splits), correction (quantity, location,
  swap, option change).
- **New:**
  - removal: "drop the fries"
  - multi_item: 2–3 items
  - multi_problem: a vague item plus a missing option in one message
  - quantity_limit: more than the maximum
  - partial_answer: two required options answered one at a time; menu B only, since
    menu A has no such item

Building:
- **Paraphrase:** about half the generated messages are paraphrased by `qwen3.5:9b`, a
  different model from the one under test. A paraphrase is kept only if every item,
  option, quantity and location word survives and no menu word is added (field
  `paraphrased`).
- **Gold check:** every gold order is checked against the assistant's own validator.
- **Rebuild:** `python build_v2.py`. For the PIZZA set, first download the two PIZZA
  files listed in `SOURCES.md` into `../external/raw/`.
- **Evaluate:** `run_eval_v2.ps1` runs the full C1–C5 evaluation into
  `data/evaluations/v2/`.

Generator: `generate_v2.py` is menu-driven. Item families, option wording and
unavailable requests come from the menu snapshot plus a small hints file
(`hints_menu_*.json`), so a new vendor's menu can be turned into dialogues without
code changes.
