# Architectural & Project Decisions (ADR Log)

14 Oct 2026: the bullets below that name Tinker, TabPFN, Render, a live .tech domain, or a real 50-message set are plans from before the red-team pass. They are not the current system. The running extractor without a key is the regex. Fallback must be labelled as fallback. Deployment status lives in `docs/DEPLOY.md`, not in this file.

ADR 002 and ADR 006 still name TabPFN, Tinker and a Render domain. Read them as history: TabPFN and the Tinker backend are gone from the code (ADR 011), and the deployment status lives in `docs/DEPLOY.md`, not here.

## ADR 001: Strict No Credit Card Policy
- **Context:** Student/early-career budget and strict hackathon rule.
- **Decision:** Zero reliance on any service requiring a credit card for setup or evaluation.
- **Consequences:** If any hosted vendor demands a card to access API credits or deploy tiers, that path is bypassed immediately. If an external API is unavailable or unkeyed, the offline rules keep the app functional.

## ADR 002: Limited Disk & Hosted-Only Inference
- **Context:** Developer environment has limited disk space; large PyTorch/CUDA libraries and multi-gigabyte open model weights cannot be downloaded locally.
- **Decision:** No local model weights in this repository. Hosted APIs are optional, never required: Google AI Studio for Gemma, Modal for the fine-tuned Qwen adapter, any OpenAI-compatible endpoint for Ollama or vLLM. The offline rules are the default and need no key at all.
- **Consequences:** Lightweight install and deploy footprint. Every hosted path degrades to the rules with a visible label rather than failing.

## ADR 003: Privacy-Preserving Client-Side Pseudonymization
- **Context:** Tiffin customer messages contain real names, phone numbers, and dietary habits.
- **Decision:** Before any text is dispatched to a hosted model, customer names are replaced with opaque tokens (`C001`, `C002`, and so on). The token map lives in memory only; it is never written to disk.
- **Consequences:** A hosted provider does not receive the names. The cook cannot be shown a real name again after a restart, because the map is gone. See ADR 010 for what persistence stores.

## ADR 004: Zero Auto-Send WhatsApp Policy
- **Context:** Automated WhatsApp sending risks account banning, costs per conversation via Meta Cloud API, and removes the cook's personal relationship with her PG students.
- **Decision:** TiffinTally NEVER auto-sends messages. It ingests standard WhatsApp export `.txt` or raw copied text, and drafts polite Hinglish reminder messages with a one-tap "Copy to Clipboard" button.
- **Consequences:** Zero risk of accidental messages or account bans; zero WhatsApp Business API fees.

## ADR 005: Two-Stage Pipeline (LLM Extract + Deterministic Reconcile)
- **Context:** Large language models struggle with reliable tally arithmetic, order updates, and cutoff timestamps over long multi-turn chats.
- **Decision:** A model is used solely as an information extractor to parse unstructured Hinglish chat lines into atomic `OrderEvent` records. The reconciler is a pure, deterministic Python module that handles cutoff rules, cancellations, modifications, dish totals, and ledger math.
- **Consequences:** Reproducible math, testable edge cases, and zero arithmetic hallucination. Money is never taken from a model.

## ADR 006: Data Split and Benchmark Integrity
- **Context:** Prevents data leakage and ensures benchmark numbers are honest.
- **Decision:**
  - Synthetic dataset, seeded and reproducible, split into train, dev2 and test.
  - A real human-written holdout is test-only and requires provenance, consent and independent labelling before it may be scored.
  - Benchmark rule: "If it didn't run, it isn't published. `NOT RUN` beats a fake number."

## ADR 007: Cutoff Timestamp and Late Order Policy
- **Context:** Tiffin cooks need orders finalized by a strict cutoff to buy vegetables at the morning mandi.
- **Decision:** Messages received after the cutoff hour/minute are marked with `is_late=True` and flagged distinctly on the prep sheet review for cook approval, rather than silently modifying kitchen quantities.

## ADR 008: Served Model Ids and Labelled Fallback (17 Oct 2026)
- **Context:** The hosted default was `gemma-2-9b-it`, which the Gemini API retired; it answers 404. A 404 is terminal in this client, so every call fell back to the offline rules while the UI still named Gemma. Separately, Gemma 4 can answer with a `thought` part before the JSON part, and the parser read `parts[0]`, so a good reply parsed as empty and every message fell back.
- **Decision:** Default to `gemma-4-26b-a4b-it`. Concatenate only parts without `thought: true`. Strip a JSON code fence before parsing. On a 400, retry once without `responseMimeType` and record which mode answered, in `BatchResult.response_mime_mode` and in the eval metadata. A retired id must produce the rules label plus the HTTP error, never a model label.
- **Consequences:** A 404 or a rejected MIME type is visible instead of silent. There is still no measurement: no `GOOGLE_API_KEY` was available, so the Gemma baseline stays `NOT RUN` and no accuracy is claimed anywhere. `EXTRACTOR_BACKEND` is the only way to force `off` on a host that also holds a key.

## ADR 009: /benchmarks Is a Scorer Demo, Not Self-Healing (17 Oct 2026)
- **Context:** The evaluation lab scored an extraction against a caller-supplied gold event, then applied repair rules written against the same four sentences the suites score. Passing there demonstrates the scorer, not extraction quality, and the adversarial suite never reached the threshold. The page and the submission had described it as a self-healing loop that corrected live output, and had named flaw codes that exist nowhere in the code.
- **Decision:** Present `/benchmarks` as a scorer demo with repair rules. The page states that it needs gold labels, starts from the offline rules or an injected fake flaw, is not used when a chat is pasted, and that the adversarial suite is expected to fail. No repair rule, threshold or suite was changed to make a result look better.
- **Consequences:** A passing suite on that page means the rules recognise the sentence they were written for. Tests pin that the lab makes no HTTP call and that the adversarial suite keeps failing, so nobody can quietly turn it green.

## ADR 010: Persisted Chat Text Is Masked, And Names Do Not Come Back (17 Oct 2026)
- **Context:** With `TIFFINTALLY_PERSIST=1`, `db.mask_chat_text_for_storage` split each line on its first colon. In a bracketed export that colon belongs to the timestamp, so the sender was never registered and real names, a roommate's name and a raw email in `payment_note` reached the database file. The alternative considered was persisting the token map so a cook could see real names again, which puts the names back on disk and defeats the masking.
- **Decision:** Mask with the parser's own sender rules, one `Pseudonymizer` per upload, over every stored line and over `orders.customer`, `orders.secondary_customer` and `orders.payment_note`. Do not persist the token map. A restored session therefore shows tokens, and the UI says so: "Restored, not re-extracted", plus a note that stored names are tokens.
- **Consequences:** Persistence is for counts, money and audit, not for a readable customer list. A bare street name with no flat or building number is still not matched; that limit is stated in the README and pinned by a test, so the docs cannot claim more than the code does.

## ADR 011: Configuration Files Describe Only What Exists (17 Oct 2026)
- **Context:** `.env.example` and `docs/DEPLOY.md` listed `TINKER_API_KEY`, `TABPFN_API_KEY` and `ELEVENLABS_*`. TabPFN and the Tinker *backend* are gone from the code; ElevenLabs is not, it is wired into the sheet build, has an endpoint and has tests. A first-time reader cannot tell which is which.
- **Decision:** `.env.example` documents `EXTRACTOR_BACKEND` and only the keys the code reads, keeps ElevenLabs, drops TabPFN and Tinker, and says in its header that no hosted Gemma run has been measured. `docs/DEPLOY.md` belongs to the deployment session and keeps its key.
- **Consequences:** A judge reading the configuration is not sent looking for a feature that is not implemented, and is not told a voice brief is gone when it is not.

## ADR 012: Evidence Gates Live in Scripts, Not in Prose (17 Oct 2026)
- **Context:** Numbers in prose drift from numbers in files, which is how the earlier retracted model figures happened.
- **Decision:** The public tables are generated by `scripts/publish_results.py` from saved per-row predictions, and `scripts/check_claims.py` fails the build on an unregistered percentage in `README.md`, `RESULTS.md`, `post.md` or `docs/*.md`. The submission post carries no percentage signs at all, so its only numbers are counts taken from `RESULTS.md` or from a test run in the same session.
- **Consequences:** A number in a document cannot outlive the artefact behind it. A test asserts that the README privacy section still matches what the persistence test proves, so the section cannot quietly grow a stronger claim.

## ADR 013: Per-Kitchen SFT Export, SQLite Is the Single Correction Store (21 Oct 2026)
- **Context:** One deployment serves many kitchens, but three paths still pooled their data. `persist_correction` appended every appending kitchen into one `data/private/corrections.jsonl`; the SFT export route wrote every kitchen into the constant `ACTIVE_SFT_EXPORT` (`data/sft/active_learning_batch.jsonl`), so cook B's export silently erased cook A's batch; and the route reported that constant rather than the file it had actually written. Corrections had gone per-session (`corrections_file_for`) in an earlier fix, but these two paths were left behind.
- **Decision:** The SFT export goes to `sft_export_file_for(session)` — one `active_learning_batch_<sid>.jsonl` per kitchen beside the defaults — and the route returns that path as `export_path`. `export_sft_dataset` writes to a temp file in the destination directory and `os.replace`s it into place, so a torn export never replaces a good one. `persist_correction` drops the shared JSONL append: the SQLite `corrections` table (keyed by `kitchen_id`) is the single durable store.
- **Consequences:** Two kitchens recording and exporting produce two separate batches, neither overwriting the other (`test_two_kitchens_export_separate_sft_files`). No code path writes several kitchens into one corrections file (`test_persist_correction`). A half-written export leaves no torn batch and no `.tmp` litter (`test_export_replaces_an_existing_batch_atomically`). Anyone re-combining kitchens for training does it explicitly at read time by joining on `kitchen_id`, not by accident of file layout.