
### 3. Hinglish Slang Understanding
Off-the-shelf closed models struggle with informal Hinglish idioms:
- *"kal lunch cancel aunty, team lunch hai"* -> correctly parsed as `qty=0, action='cancel'`.
- *"2 nahi 3 thali"* -> correctly parsed as `qty=3, action='change'` rather than adding 2 + 3 = 5.
- *"bina pyaaz ke do thali"* -> extracted as Jain/no-onion modification (`qty=2`, `mods=['no onion']`).
- *"Send dinner tonight by 8:30 pm sharp, 1 thali"* -> parsed as `qty=1`, not confusing `8:30` with quantity.

---

## Evals (The Honest Bit)

All numbers are measured using our evaluation suite (`tiffintally eval all`) and empirical Modal GPU fine-tuning runs stored in `evals/`:

### A. Extractor Accuracy on Held-Out Real WhatsApp Orders (50 hand-collected customer messages)
| Metric | Heuristic Baseline (Rules) | Gemma 2 (AI Studio) | Fine-Tuned Qwen-0.5B (Modal Iteration 6) |
| :--- | :--- | :--- | :--- |
| **Exact Match Accuracy** | 74.0% (37/50) | 74.0% | **96.0% (48/50)** (\u26a1 +22.0% over rules) |
| **Meal Type F1** | 0.880 | 0.840 | **0.960** |
| **Quantity F1** | 0.860 | 0.760 | **1.000 (Zero Cardinality Errors)** |
| **Action (New/Cancel/Pause) F1** | 0.840 | 0.820 | **1.000 (Zero Action Errors)** |
| **Special Modifications F1** | 0.880 | 0.920 | **0.980** |
| **JSON Structural Validity** | N/A | 100.0% | **100.0% (Zero Parse Errors)** |

### B. The 6-Iteration Fine-Tuning Loop on Modal GPU
Tuning a 0.5B SLM on conversational Hinglish is full of real-world ML pitfalls. Here is our exact diagnostic journey:

| Stage | Iteration 1 | Iteration 2 | Iteration 3 | Iteration 4 | Iteration 5 | Iteration 6 (Dual Benchmark) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GPU Target** | Modal T4 | Modal T4 | Modal A10G | Modal A10G | Modal A10G | **Modal A10G** |
| **Training Duration** | 240.1s | 561.0s | 79.8s | 107.7s | 109.3s | **185.6s** |
| **Dataset Rows** | 640 synthetic | 640 synthetic | 640 synthetic | 640 synthetic | 640 synthetic | **1,016 augmented** |
| **Synthetic Exact Match** | 0.0% | 100.0% (small sample) | 80.0% | 90.0% | 100.0% (20/20) | **100.0% (30/30)** |
| **Real WhatsApp Exact Match** | Unverified | Unverified | Unverified | Unverified | Unverified | **96.0% (48/50 Real Cases)** |
| **Real Qty & Action F1** | 0.00 / 0.00 | — | — | — | — | **1.000 / 1.000** |
| **Domain Edge Cases** | 0 / 5 Passed | 4 / 5 Passed | 4 / 5 Passed | 5 / 5 Passed | 6 / 6 Passed | **8 / 8 PASSED (100%)** |
| **Diagnostic Finding** | Truncation (`max_seq_len=192`) & no label masking | Fixed context (512) & ChatML label masking | A10G speedup + lexical number words ("do"=2) | Solved prompt truncation (`max_seq_len=768`) & balanced data | Rule 9 lexical numbers ("teen"=3) | Discovered synthetic evaluation trap; benchmarked 50 real messages with 96% accuracy |

### C. Kitchen Plate Forecast (TabPFN vs Baselines on 14-Day Holdout)
| Model | MAE (Plates) | RMSE (Plates) | Days Within \u00b13 Plates |
| :--- | :--- | :--- | :--- |
| **TabPFN Regression** | **0.79** | **1.04** | **100.0%** |
| Naive Lag-7 (Same weekday last week) | 2.07 | 2.63 | 71.4% |
| Confirmed-Only (No walk-in buffer) | 4.79 | 4.96 | 14.3% |

### What's Still Imperfect:
- **Chit-chat Compliment Default Meal Leakage:** In purely conversational compliments (*"Aaj ki bhindi fry bahut badiya thi aunty!"*), the model correctly identified `action='none', qty=0`, but leaked `meal='dinner'` instead of `meal='unspecified'`.
- **Compound Dual Meal Ordering:** When a single message orders both meals separately (*"kal lunch 1, dinner 1"*), attention can favor the trailing clause unless explicitly mapped to `meal='both'`.

---

## My First User

<!-- <<VEDANT FILLS>>: who (anonymised), what she did, verbatim "would you pay?", what she asked for next. Or "not yet" honestly. -->
*(Vedant will document his real testing session with the Pune tiffin aunty here before final publish)*

---

## Prize Categories

- **Best Use of Gemma:** Used Gemma 2 9B via Google AI Studio as the primary zero-shot teacher extractor for Hinglish order parsing.
- **Best Use of Tinker:** Prepared SFT datasets and trained LoRA fine-tune adapter (`qwen2.5-3b-tiffintally-lora`) served on Thinking Machines' Tinker API.
- **Best Use of TabPFN:** Applied TabPFN Regression directly on 90-day tabular kitchen histories to solve doorstep walk-in plate prediction with an MAE of 0.79 plates.
- **Best Use of Render:** Deployed zero-downtime free tier web service configured via `render.yaml` with automated health checks.
- **Best Use of ElevenLabs:** Synthesized daily morning Hinglish voice briefings for the cook, cached locally in MP3 format.
- **Best Use of a .tech Domain:** Live deployment at [https://tiffintally.tech](https://tiffintally.tech).

---

## Credits

- **FastAPI & Jinja2** for lightning-fast responsive UI.
- **TabPFN** team (Prior Labs) for tabular foundation models.
- **Google DeepMind** for Gemma open models.
