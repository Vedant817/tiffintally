# Architectural & Project Decisions (ADR Log)

## ADR 001: Strict No Credit Card Policy
- **Context:** Student/early-career budget and strict hackathon rule.
- **Decision:** Zero reliance on any service requiring a credit card for setup or evaluation.
- **Consequences:** If any hosted vendor demands a card to access API credits or deploy tiers, that path is bypassed immediately. We use verified free tiers (Google AI Studio Gemma free tier, Render free tier, Prior Labs TabPFN free quota, ElevenLabs free tier). If an external API is unavailable or unkeyed, fallback pipelines (cached runs, rule heuristics, local mock extractor) keep the app 100% functional.

## ADR 002: Limited Disk & Hosted-Only Inference
- **Context:** Developer environment has limited disk space; large PyTorch/CUDA libraries and multi-gigabyte open model weights cannot be downloaded locally.
- **Decision:** No local model weights. Hosted APIs only:
  - Google AI Studio API for Gemma baseline & teacher extraction.
  - Thinking Machines Tinker API for LoRA fine-tuning and inference.
  - Prior Labs `tabpfn-client` for tabular forecasting.
  - ElevenLabs API for morning audio summary.
- **Consequences:** Lightning-fast environment install with `uv`, lightweight deploy footprint on Render (<150MB container).

## ADR 003: Privacy-Preserving Client-Side Pseudonymization
- **Context:** Tiffin customer messages contain real names, phone numbers, and dietary habits.
- **Decision:** Before any text is dispatched to external LLM APIs (AI Studio or Tinker), customer names are replaced with opaque tokens (`C001`, `C002`, etc.). The name-to-token map is stored strictly on the cook's local SQLite database.
- **Consequences:** Third-party LLM providers never see personal identifiable customer information (PII). Real test data in `data/private/` is permanently gitignored.

## ADR 004: Zero Auto-Send WhatsApp Policy
- **Context:** Automated WhatsApp sending risks account banning, costs per conversation via Meta Cloud API, and removes the cook's personal relationship with her PG students.
- **Decision:** TiffinTally NEVER auto-sends messages. It ingests standard WhatsApp export `.txt` or raw copied text, and drafts polite Hinglish reminder messages with a one-tap "Copy to Clipboard" button.
- **Consequences:** Zero risk of accidental messages or account bans; zero WhatsApp Business API fees.

## ADR 005: Two-Stage Pipeline (LLM Extract + Deterministic Reconcile)
- **Context:** Large language models struggle with reliable tally arithmetic, order updates, and cutoff timestamps over long multi-turn chats.
- **Decision:** The LLM is used solely as an information extractor to parse unstructured Hinglish chat lines into atomic `OrderEvent` records. The reconciler is a pure, deterministic, 100% unit-tested Python module that handles cutoff rules, cancellations, modifications, dish totals, and ledger math.
- **Consequences:** 100% reproducible math, testable edge cases, and zero arithmetic hallucination.

## ADR 006: Data Split and Benchmark Integrity
- **Context:** Prevents data leakage and ensures benchmark numbers are honest.
- **Decision:**
  - Synthetic dataset (≥600 rows): Seeded, reproducible, split 80% train / 20% test.
  - Real dataset (≥50 rows): Marked for TEST ONLY, never used in training or fine-tuning prompts.
  - TabPFN History: Time-based chronological split (train on earlier weeks, evaluate on final 2 weeks). No shuffling.
  - Benchmark Rule: "If it didn't run, it isn't published. `NOT RUN` beats a fake number."

## ADR 007: Cutoff Timestamp and Late Order Policy
- **Context:** Tiffin cooks need orders finalized by a strict cutoff (e.g. 11:00 PM for lunch next day) to buy vegetables at the morning mandi.
- **Decision:** Messages received after the cutoff hour/minute are marked with `is_late=True` and flagged distinctly on the prep sheet review for cook approval, rather than silently modifying kitchen quantities.
