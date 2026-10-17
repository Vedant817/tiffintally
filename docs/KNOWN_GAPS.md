# Known gaps

What the app still does not do, written down so a claim cannot drift past it.

## Persistence is experimental

`TIFFINTALLY_PERSIST=1` stores masked chat in SQLite. After a restart the sheet shows tokens (`C001`), and the page says names are tokens after restart. The cutoff, target date, price and corrections are not restored. Each upload builds a new token map, so a correction token need not match the order token for the same person. The reverse map is not encrypted, and persistence does not refuse to start when `TIFFINTALLY_DB_KEY` is unset, because that key is not used. The corrections files store a token for the customer, not the typed name.

A bare street name such as "Baner Road" is still stored. `tests/test_db_persistence.py` asserts that, and it scans the SQLite file and every file under `data/` for that session, including `data/private/`.

## Not in this release

- No measured model accuracy. Gemma, the adapter, few-shot and the base model are NOT RUN.
- No forecast, and no real-time ingestion.
- `/benchmarks` is a scorer demo over four hand-written sentences. One of them does not pass. Pasting a chat does not call it.
- Voice notes are not accepted. The old `/api/voice-note` stub wrote files in demo mode, so the route was removed.
- The morning brief is a written template. Audio exists only when an ElevenLabs key is set, and the page says "(ElevenLabs)" only then. Demo mode does not create `data/briefings`.
- A decrement of one plate ("ek thali kam", "cancel one thali") is sent to review. The reconciler has no subtract action, so it does not guess the meal.
- A date range ("Monday to Friday", "ek hafte") is sent to review. The sheet is one day.
