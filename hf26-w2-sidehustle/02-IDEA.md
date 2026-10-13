# 02 — IDEA: TiffinTally

> **Tagline:** "Your WhatsApp orders, sorted before the pressure cooker's first whistle."
> Repo name: `tiffintally` · Domain: `tiffintally.tech` (claim it in promos; check it's free first)

## Problem (one real person)
Meet a home tiffin cook in Bengaluru with about 40 customers (PG students and office workers). Every evening 60–120 WhatsApp messages come in: "kal lunch 2, dinner skip", "aaj roti nahi rice", "no onion for Priya", "paying Friday", a voice note. She tallies by hand at 10 PM, cooks too much or too little the next morning, and forgets who owes ₹1,800.

## What it does (MVP)
1. **Ingest:** paste text or upload a WhatsApp **chat export .txt** (a standard feature; no scraping, no WhatsApp API). Optional: an audio note gets transcribed through a hosted open Whisper endpoint (stretch).
2. **Extract:** each message becomes structured `OrderEvent {customer, date, meal(lunch|dinner), qty, items, mods[], action(new|change|cancel|pause), payment_note, confidence}`, with Hinglish handled.
3. **Reconcile:** apply changes and cancels in time order to get **tomorrow's prep sheet** (counts per dish, special mods list, packing labels per customer).
4. **Forecast:** TabPFN predicts tomorrow's actual thali count (orders + typical late additions) from the cook's history CSV (day of week, holidays, weather, last 7 days). Show it as "Cook for about 46 (confirmed 41)".
5. **Dues:** a running ledger per customer; it drafts polite reminder messages in Hinglish for the cook to copy. **It never sends anything automatically.**
6. **Morning voice brief (ElevenLabs):** a 30-second Hindi/English summary ("Kal 41 confirmed, 5 extra expected, 6 no-onion...").
7. **Review-first UX:** low-confidence extractions are highlighted for one-tap fix, and fixes are saved as new training rows.

## Out of scope
Payments, sending WhatsApp messages, delivery routing, multi-kitchen.

## Architecture
```
chat export / paste ─▶ parser (regex: WhatsApp line format, timestamps)
                      ─▶ extractor: Tinker-FT small open model (primary)
                                    ↳ fallback/teacher: Gemma 3 via Google AI Studio
                      ─▶ reconciler (pure Python, deterministic, unit-tested)
                      ─▶ prep sheet + dues ledger (SQLite)
history CSV ─▶ TabPFN (Prior Labs API, tabpfn-client) ─▶ "cook for N"
prep sheet ─▶ ElevenLabs TTS ─▶ morning brief mp3
FastAPI + a small HTMX/vanilla front end ─▶ Render free web service ─▶ tiffintally.tech
```
- Python 3.11 + `uv`, FastAPI, SQLite, pydantic. No local model weights (disk is limited).
- **Model choice:** Tinker fine-tunes an open-weight model from Tinker's supported list (pick the smallest Llama/Qwen it offers, e.g. ~1–8B; check the list on the day). LoRA, served through Tinker's sampling API. Gemma (`gemma-3-27b-it` or the latest Gemma on AI Studio) is the baseline and labeler.
- **Privacy mode:** names are pseudonymised before any hosted call (`C001`), and the mapping stays in local SQLite. The post states honestly that hosted inference is still a third party, and that the open model is what allows moving fully local later.

## Data (honest)
- **Synthetic set:** a generator script builds about 600 Hinglish order messages from templates plus Gemma paraphrases, with gold labels from the generator. It is clearly marked synthetic.
- **Real set:** 50–150 anonymised messages from the first user, hand-labelled by Vedant. **Held out for test only.**
- **History CSV for TabPFN:** if the user has a notebook log, digitise 4–8 weeks. Otherwise the demo uses synthetic history, the post says so, and the TabPFN claim is scoped to "works on synthetic, here's the method".

## Pricing story (for "would someone pay")
- Free: 1 kitchen, 20 customers. Pro ₹249/mo: forecast, voice brief, unlimited customers.
- Compute RESULTS.md cost per 1,000 messages: FT small model vs Gemma vs a closed API list price (cite the pricing page and date). Use real token counts from logs.

## Definition of Done
- Upload an export and get a prep sheet in under 10 s for 200 messages (measured)
- Eval: baseline Gemma vs Tinker FT on the **real held-out** set, field-level F1 and exact-match per message
- TabPFN vs naive baseline (last-same-weekday) MAE
- Hosted demo URL + .tech domain + 60–90 s demo video
- First-user notes (real quotes, with consent) or an honest "not yet"
- DEV post draft in `post.md`
