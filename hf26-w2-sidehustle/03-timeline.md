# 03 — Timeline (Tue Oct 13, 1:30 PM IST → Mon Oct 19, 12:29 PM IST)

About 5.5 days. Agents run continuously; **[V]** = Vedant must act.

| When (IST) | Work | Gate |
|---|---|---|
| **Tue Oct 13, eve** | [V] Claim promos (Tinker, Render, .tech; ElevenLabs if listed), AI Studio key, Prior Labs key (accept non-commercial licence). [V] Message 2–3 tiffin cooks / PG tiffin services asking for an anonymised week of orders and a 20-minute trial. Agent: scaffold repo, licence, CI, WhatsApp export parser + tests, OrderEvent schema | Repo first commit dated Oct 13 |
| **Wed Oct 14** | Synthetic generator (600 rows), Gemma baseline extractor, reconciler + bold tests, eval harness. [V] Collect real messages, anonymise, hand-label ≥50 | Baseline numbers on synthetic in RESULTS.md |
| **Thu Oct 15** | Tinker fine-tune run 1 (train on synthetic plus *non-test* real rows); eval vs baseline; TabPFN forecast + naive baseline; SQLite dues ledger | FT beats baseline on real holdout **or** an honest write-up of why not |
| **Fri Oct 16** | Front end (upload → review → prep sheet → dues), ElevenLabs brief, pseudonymisation, deploy to Render, point the .tech domain. Sentry tracing if chosen | Public URL works from phone |
| **Sat Oct 17** | [V] **First-user session** (in person or a call): she uploads her own export; record her reactions, ask "would you pay ₹249?". Fix the top 3 asks. Demo video | User notes in `docs/first-user.md` |
| **Sun Oct 18** | Final evals rerun, README, post.md full draft, screenshots and GIF, cost table from real logs | Draft done by 10 PM IST |
| **Mon Oct 19, 6–9 AM** | [V] Edit voice, paste into the **official template**, publish. **Hard stop 12:29 PM IST** | Published by 9 AM |

Fallbacks: if Tinker credits are late, ship Gemma-only and drop the Tinker claim. If Render asks for a card, record a local demo and use only the .tech domain if a free static host (GitHub Pages) can serve the landing page. If no real user replies by Fri, use a family member who cooks for others, or say honestly "first user: not yet".
