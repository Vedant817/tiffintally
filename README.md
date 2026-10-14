# TiffinTally

A home-kitchen tool that turns a pasted WhatsApp export into a prep sheet and a dues ledger.

The cook's problem is real: orders, cancels, and "bina pyaaz" arrive as messy chat, usually after 9pm. A Google Form avoids that mess only if every customer uses it. Most of these customers will not. Exporting the chat is still manual, and that friction is the main reason this may not replace a notebook.

This repository does **not** currently prove a fine-tuned model, a TabPFN forecast, an on-device benchmark, or a live deployment.

## What actually runs

- `tiffintally/parser.py` reads Android, iOS, `dd.mm.yy`, and `YYYY-MM-DD` WhatsApp headers. A message that says someone "left" is not dropped as a system line.
- `tiffintally/extract/base.py` is a regex heuristic. It labels "aaj", "today", and "tonight" as today, and "kal" or "tomorrow" as tomorrow.
- `tiffintally/reconcile.py` resolves those words against the message timestamp, then keeps only the day the cook asked for. Standing orders are off unless the caller passes them.
- `tiffintally/app.py` keeps each browser's sheet in its own cookie. One visitor does not see another visitor's customers. Nothing is preloaded.
- With `GOOGLE_API_KEY`, extraction calls Gemma and sends the key in the `x-goog-api-key` header. Without a key, the page says it used the rules fallback.
- The voice-note route without a key returns a demo stub. It does not invent an order from the filename.
- `tiffintally benchmark-edge` exits with an error. It does not print a latency.

`evals/modal_run_iter_1.json` through `modal_run_iter_30.json` are retracted Qwen2.5-0.5B logs. `evals/modal_run_iter_31.json` is a later Qwen2.5-3B LoRA run on the template-disjoint synthetic test: 84.0% exact match on 50 rows (meal, qty, action, mods, and date). That file is the source. The app does not serve the adapter. See `RESULTS.md`.

## What this is not

- Not a Tinker fine-tune. The Tinker SDK is not configured, and `extract/tinker.py` will not call a placeholder host.
- Not a TabPFN result. The forecast is HistGradientBoosting on `data/kitchen_history.csv`, which is synthetic. TabPFN's client licence is non-commercial. The prep sheet tells the cook to follow the chat count. The model buffer is not an order.
- Not measured on a Raspberry Pi, and not shipped as GGUF.
- Not deployed. `https://tiffintally.tech` is not this app. There is a `render.yaml` and no evidence of a live service.
- No first-user visit is claimed. No real cook messages are in git. `data/private/` is gitignored for when you label some.

## Quickstart

Requires Python 3.11 or 3.12 (`requires-python` is `>=3.11,<3.13`).

```bash
uv sync
uv run pytest
uv run tiffintally serve
```

Open `http://127.0.0.1:8000` and paste a chat. The prep sheet starts empty.

```bash
uv run tiffintally parse my_chat.txt --date tomorrow
uv run tiffintally forecast --confirmed 42
uv run python scripts/gen_synthetic.py
```

`benchmark-edge` is intentionally a failure until someone measures a model on a device.

## Data

`data/synthetic/train.jsonl` and `test.jsonl` are generated. Rows are deduped by text. A template is entirely in train or entirely in test (`data/synthetic/split_report.json`). They are not real WhatsApp messages.

## Tests

`uv run pytest` runs the suite. The count is whatever pytest prints. CI on GitHub is the status that matters. A badge that hardcodes "71 passed" was removed because it goes stale.

## Privacy

Names can be masked before a model call. Message text is not attached to Sentry events (`data_collection` leaves user info, cookies, headers, query strings, and request bodies off). The sheet still lives in process memory, keyed by cookie, so a deployed process remembers that browser until restart. Do not put a real customer export on a shared server until that store is per-cook and encrypted.

## License

MIT. Vedant Mahajan.
