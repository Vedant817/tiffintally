# 01 — Idea Board (Side Hustle)

Scoring (1–5) is weighted to the judging: Writing/story ×3, Relevance (open core + would pay) ×2, Creativity ×2, Feasibility in ~5.5 days with no card and low disk ×2, Partner fit ×1. Max 50.
Excluded on purpose: Flow Pilot, MediClarity, Nexus Forge, PayHack, Wiretight, Baahar, Aaji's Pill Clerk (and anything close to them, like handwritten-document OCR or payments/bank fraud).

| # | Idea | Who pays | Pain (real) | Open core | Partners | Story | Rel | Crea | Feas | Partner | **Total** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **TiffinTally**: turns a home tiffin cook's WhatsApp order chaos (Hinglish, voice-note transcripts, "kal 2 thali no pyaaz") into tomorrow's prep sheet, dues ledger and a cooking-quantity forecast | Home tiffin and cloud-kitchen operators, ₹199–299/mo | Orders spread across WhatsApp DMs, last-minute changes, food waste, unpaid dues ("udhaar") | Gemma extraction + Tinker-tuned small open model + TabPFN forecast | Gemma, Tinker, TabPFN, Render, ElevenLabs, .tech | 5 | 5 | 5 | 4 | 5 | **47** |
| 2 | **TuitionBook**: home tutors log attendance and fees by voice note; it drafts polite fee reminders for parents | Home tutors | Fee chasing is awkward; attendance is in notebooks | Whisper-class STT + Gemma | Gemma, ElevenLabs, Render | 4 | 4 | 4 | 4 | 3 | **39** |
| 3 | **ResellerDM**: Instagram/Meesho reseller pastes customer DMs and gets structured orders, a size/stock check and reply drafts | Small Instagram sellers | Orders lost in DMs, size mix-ups | Gemma + fine-tuned classifier | Gemma, Tinker, Render | 4 | 4 | 3 | 4 | 4 | **38** |
| 4 | **GST Shoebox**: local sorter for freelancer invoices and receipts into GST-ready CSV | Indian freelancers | Quarterly GST/ITR scramble | Local Gemma vision | Gemma, Render | 3 | 5 | 2 | 4 | 3 | **36** (too close to the organizer example) |
| 5 | **Quote Coach**: freelancers paste a client brief and get a scoped, priced quote using their own past-project CSV | Freelance devs and designers | Underpricing, scope creep | Gemma + TabPFN regression on past rates | Gemma, TabPFN | 4 | 4 | 3 | 4 | 4 | **38** |
| 6 | **LatePay Radar**: predicts which client invoices will be paid late (TabPFN) and drafts chasers | Freelancers, agencies | Cash-flow stress | TabPFN + Gemma | TabPFN, Gemma, Temporal | 3 | 4 | 3 | 4 | 4 | **35** (feels near PayHack/finance; skip) |
| 7 | **BakeCost**: home bakers enter a recipe and get a cost per unit and suggested price from live ingredient prices | Home bakers | Underpricing cakes | Gemma + SerpApi prices | Gemma, SerpApi | 4 | 4 | 3 | 3 | 3 | **35** |
| 8 | **Thali Menu Card**: a small restaurant's handwritten/regional menu becomes a bilingual menu with allergen tags | Small dhabas | Tourists can't read the menu | Gemma vision, Tinker on dish names | Gemma, Tinker, .tech | 3 | 4 | 2 | 4 | 4 | **33** (organizer example + near Pill Clerk OCR) |
| 9 | **SocietyDesk**: housing society treasurer reconciles maintenance payments from UPI SMS exports | RWA volunteers | Manual reconciliation | Local model on SMS text | Gemma, MongoDB | 3 | 4 | 3 | 3 | 2 | **32** (near Wiretight banking) |
| 10 | **ClipCutter**: a podcaster's long episodes become short-clip suggestions and captions | Indie podcasters | Hours spent editing | Open STT + Gemma | ElevenLabs, Gemma | 3 | 3 | 2 | 2 | 3 | **28** (heavy media, disk) |

## Recommendation: TiffinTally (#1)
- **Who pays and why:** India's home-tiffin economy runs on WhatsApp. One cook with 30–80 daily customers loses money in three ways: missed or changed orders, over- or under-cooking, and dues nobody tracks. ₹249/mo is less than one wasted day of dal-rice.
- **Why open matters (post angle):** (a) Customer names, addresses and dues should not sit on a closed API's servers, so the tuned small model can run on the cook's own phone or laptop later. (b) Unit cost: a few thousand short messages a month on a tuned 1–3B open model is close to free, which closed per-token pricing can't match at ₹249. (c) Hinglish order slang ("half plate", "no pyaaz", "Sunday off", "Ravi bhaiya ke liye bhi") is a niche that fine-tuning visibly improves.
- **Partner stack:** Gemma (extraction and teacher), Tinker (fine-tune a small open model with a measured gain), TabPFN (tomorrow's thali count), Render (host), ElevenLabs (morning voice summary in Hindi), .tech domain.
- **First-user path:** Bengaluru has many PG/office tiffin services. Vedant asks one cook (or a family member's cook) for an anonymised week of orders and a 20-minute trial.

## Runners-up
1. **TuitionBook** (39): warm story, but fewer partner categories.
2. **ResellerDM** (38): good, but Instagram DM scraping is legally and technically awkward; it would have to rely on pasted text.
3. **Quote Coach** (38): solid TabPFN story; less emotional pull for the write-up.
