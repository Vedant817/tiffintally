# Proposed training recipe — NOT RUN

This is a design for review, not a measured result or a ready training dataset.
Keep the current adapter intact. Resolve the base licence choice with Vedant.

Author at least six hundred SFT rows from at least one hundred fifty templates,
with at most six variants per template. At least a quarter must cover multi-event
messages, negation, uncertainty, cancel and change. Use the total-quantity and
secondary-share policy, canonical dietary vocabulary, and quantities up to ten.
Write held-out templates in a different style before training. Never use the
legacy dev subset or the frozen legacy test for selection. The relabel overlay
contains proposed corrections and still needs human review.

Pin dataset hashes, code SHA, base revision, prompt SHA and seeds. Suggested
initial configuration: seed 271, LoRA rank 32, alpha 64, dropout 0.05, learning
rate 0.00015, two epochs, batch four, accumulation four. These are proposed
settings, not optimized results. Save every generated row and all decoding
settings. Publish the adapter if its licence permits, or publish predictions.

Proposed command after the new dataset and licence are reviewed:

```powershell
uv run modal run scripts/modal_finetune.py --iteration 32 --seed 271 --epochs 2 --train-path data/synthetic/sft_v2.jsonl
```

That dataset intentionally does not exist yet; this command must fail until it is
provided. The local entry point also requires the exact plain line `approved: train`
in HUMAN_TODO.md. GPU minutes for this new recipe are NOT MEASURED; the old run
does not establish its duration. Proposed safety timeout is twenty GPU minutes,
not a runtime estimate. Vedant must approve training and a spend/time cap before
it runs. Do not infer approval from the example command or this document.
