# Dev check of the v2 fixes (2026-11-19)

This checks the fixes from `../v2/REPORT.md` on development data only, using C2 and
gpt-oss:20b on Ollama. `AI_DELIVERY_LOCATIONS` was set to the 12 dataset locations.

| Set | Before | After | Dialogues fixed / broken |
|---|---|---|---|
| v2 validation (198) | 0.823 | **0.909** | 17 / 0 |
| v1 validation (200) | 0.960 | 0.960 | 0 / 0 |

Changes on v2 validation by category:
- removal: 0.41 → 0.91
- ambiguous_item: 0.59 → 0.77
- multi_problem: 0.68 → 0.77

No other category changed.

The fixes:
- Removal is accepted when a named line is dropped, and a named line is removed on a
  dev-attested removal verb.
- A location named in the turn is filled in when the model leaves it empty.
- Option prefixes, plurals and negated add-ons are cleaned up.
- A vague line is replaced instead of restored, keeping its quantity.

What this check does not cover:
- The location and option rules barely show on menu A. Their effect will show on
  test B and PIZZA.
- Those rules were chosen from test-set failures: removal and location from test A and
  B, options from PIZZA. A re-run on v2 test measures how much they help, but it is no
  longer an unseen test.
