# 05 — Day 1 Kickoff Prompt (short)

````markdown
You are building TiffinTally (spec in docs/IDEA.md) for DEV HF26 Week 2 "Side Hustle"; deadline Oct 19, 12:29 PM IST. Today do only P0–P2 of docs/MASTER_PROMPT.md:
1. Scaffold: uv project, FastAPI skeleton, MIT licence, .gitignore (.env, data/private/, *.db), .env.example, GitHub Actions (ruff + pytest).
2. WhatsApp export parser + OrderEvent schema, with ≥15 tests on hand-written fixtures (Android and iOS formats, multiline, media-omitted, system lines, Devanagari).
3. scripts/gen_synthetic.py → data/synthetic/orders.jsonl (≥600 rows, seeded, gold labels, includes cancels/changes/pauses/no-order chatter).
4. scripts/label_cli.py for Vedant to label real messages into data/private/real_test.jsonl.
Rules: no credit card, no local model weights, never commit secrets, never invent numbers. End with PROGRESS.md, and ask me for the [HUMAN] items you need (keys, repo push, real data).
````
