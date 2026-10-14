# TiffinTally 60–90 Second Video Demo Script

Demo notes. Say "rules fallback" unless a Gemma key is set. Do not open tiffintally.tech. Do not call the forecast TabPFN. Do not mention a cook visit.

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
  - Browser opens to `http://127.0.0.1:8000`.
  - Paste chat export into the box (or click "Paste Demo Chat Export").
  - Click **"Reconcile Kitchen Sheet"**.
- **Voiceover:**
  > "We paste an exported chat. With no model key, a rules parser reads the lines on this machine. Names are swapped for tokens only on a hosted call, and only when that key is set. The fine-tune is not served on this page."

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

### [0:50 - 1:05] Forecast (synthetic history only)
- **Visual:**
  - Scroll to the **Cook Prediction card** showing:
    - *Confirmed Orders:* 35
    - *Model suggestion (HistGradientBoosting on synthetic history):* say the number on screen, and say it is not measured on a real kitchen.
    - *Confidence Interval:* 40 to 46
  - Click on the explanation toggle showing Day-of-Week seasonality and late doorstep walk-in buffer.
- **Voiceover:**
  > "This forecast is a scikit-learn model on made-up history. It is not TabPFN, and it is not a saving in rupees."

---

### [1:05 - 1:20] Hinglish Voice Briefing & Dues Ledger
- **Visual:**
  - Click the **Play Morning Brief** audio button.
  - Audio plays: *"Namaste Aunty ji! Aaj dopahar ke liye total 28 thali banani hai..."*
  - Navigate to `/ledger` view:
    - Show customer balances and the one-click **"Copy Polite Hinglish Reminder"** button.
- **Voiceover:**
  > "The morning brief is a text transcript unless an ElevenLabs key is set. The dues page drafts a reminder. Nothing is sent."

---

### [1:20 - 1:30] Closing: Open-Source AI for Real Lives
- **Visual:**
  - Quick flash of GitHub repo: MIT License, 44 passing tests, zero live secrets, under $0.05/month operating cost.
- **Voiceover:**
  > "TiffinTally is open source, private, runs on free tiers, and costs under ₹249 a month. Real AI solving real side-hustle headaches."
