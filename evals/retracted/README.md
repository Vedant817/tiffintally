# Retracted runs

Measurements that were taken and are no longer quoted. They are kept rather than
deleted so the sequence stays auditable, and so nobody re-derives the same wrong
number and believes it.

Do not cite anything in this directory. `evals/runs/` holds the current runs.

## Why each one was retracted

### `20261015_164203` — the model was served the wrong prompt
**Measured:** regex 78.0%, "open model" 24.0%.
**Why it is wrong:** the Modal image did not contain this package, so
`from tiffintally.extract.base import SYSTEM_PROMPT` raised and a three-word
fallback prompt was served instead of the eleven-rule prompt the adapter was
trained on. The 24% was a measurement of the fallback, not of the checkpoint.
`scripts/modal_serve.py` now bakes the package into the image and raises rather
than falling back.

### `20261015_165355` — superseded
Same numbers as the current run, taken before generation was batched and before
the no-adapter control was added. Kept only as the intermediate step; cite
`evals/runs/20261015_175344/` instead.

### `20261015_165558` — wrong model name, wrong exact-match definition, fake real set
**Measured:** "gemma-4-26b-a4b-it" at 98.0%, plus an 88.0% row headed
"Real held-out cook messages".
**Why it is wrong, three ways:**
1. The model column printed the configured default while Modal served a Qwen
   adapter. The name now comes from the endpoint's own response.
2. Exact match ignored `mods`, which inflated the model by ten points and made
   this report contradict the head-to-head. It now scores meal, qty, action and
   mods together.
3. The "real" section scored `data/private/real_test.jsonl`, which claims
   `is_synthetic: false` while every line came from the generator. Scoring it is
   refused unless the file carries a `collected_from_cook` provenance marker.

### `20261015_171528` — still the wrong model name
The provenance gate and the exact-match fix landed in this run, but the model
column still printed `gemma-4-26b-a4b-it`. Superseded by `20261015_174336`.
