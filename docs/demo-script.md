# TiffinTally 60–90 Second Video Demo Script

This script walks through the core problem, extraction, deterministic state, TabPFN forecasting, dues ledger, and voice briefing in under 90 seconds.

---

### [0:00 - 0:15] The Hook: The 10 PM Tally Problem
- **Visual:** Open WhatsApp on phone or split screen with unread messages from tiffin customers:
  - *"aunty kal lunch cancel"*
  - *"bina pyaaz ke do thali bhejo"*
  - *"roommate Priya ke liye bhi ek lunch add kar dena"*
  - *"Sunday off"*
  - *"₹500 GPay kiya"*
- **Voiceover:**
  > "Every night at 10 PM, thousands of home kitchen aunties across India stare at a storm of WhatsApp messages, a diary, and a boiling pot. One missed cancellation means cooking food for ghosts. One forgotten roommate request means someone goes hungry. This is TiffinTally."

---

### [0:15 - 0:35] Instant Extraction & Pseudonymization
- **Visual:**
  - Browser opens to `http://localhost:8000` (or `https://tiffintally.tech`).
  - Paste chat export into the box (or click "Paste Demo Chat Export").
  - Click **"Reconcile Kitchen Sheet"**.
- **Voiceover:**
  > "We paste an exported group chat or individual messages. Before anything leaves the machine, customer phone numbers and names are pseudonymized locally into safe tokens. Then, an open model fine-tuned on Hinglish kitchen slang extracts meal types, quantities, and dietary modifications in milliseconds."

---

### [0:35 - 0:50] Deterministic Reconciler & The Prep Sheet
- **Visual:**
  - Show the generated **Kitchen Prep Sheet**:
    - Total Lunch Count vs Dinner Count.
    - Special dietary requests highlighted in amber: *"Pooja: Lunch - no onion"*, *"Priya: Lunch - extra rice"*.
    - Packing Labels ready with customer name and meal.
  - Hover over the late cutoff alert: *"Deepak (11:15 PM) flagged for review, not silently added."*
- **Voiceover:**
  > "Crucially, LLMs don't do arithmetic. A deterministic state machine applies orders in timestamp order, handles cancellations, splits multi-person requests, and stops orders arriving after the 10 PM cutoff from silently entering the cook list."

---

### [0:50 - 1:05] TabPFN Kitchen Forecast (Stop Over-Cooking)
- **Visual:**
  - Scroll to the **Cook Prediction card** showing:
    - *Confirmed Orders:* 35
    - *TabPFN Predicted Total:* 43
    - *Confidence Interval:* 40 to 46
  - Click on the explanation toggle showing Day-of-Week seasonality and late doorstep walk-in buffer.
- **Voiceover:**
  > "Cooking only confirmed orders under-cooks by 4 to 8 plates because doorstep walk-ins always arrive at lunchtime. We use TabPFN regression directly on small tabular kitchen histories to tell the cook exactly how many extra plates to prep."

---

### [1:05 - 1:20] Hinglish Voice Briefing & Dues Ledger
- **Visual:**
  - Click the **Play Morning Brief** audio button.
  - Audio plays: *"Namaste Aunty ji! Aaj dopahar ke liye total 28 thali banani hai..."*
  - Navigate to `/ledger` view:
    - Show customer balances and the one-click **"Copy Polite Hinglish Reminder"** button.
- **Voiceover:**
  > "At 6:30 AM while chopping vegetables, she doesn't read spreadsheets. ElevenLabs delivers a warm Hinglish voice brief with exact vegetable and dal counts. And when rent is due, TiffinTally drafts polite WhatsApp reminders without ever auto-spamming."

---

### [1:20 - 1:30] Closing: Open-Source AI for Real Lives
- **Visual:**
  - Quick flash of GitHub repo: MIT License, 44 passing tests, zero live secrets, under $0.05/month operating cost.
- **Voiceover:**
  > "TiffinTally is open source, private, runs on free tiers, and costs under ₹249 a month. Real AI solving real side-hustle headaches."
