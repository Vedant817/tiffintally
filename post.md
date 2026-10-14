---
title: I built a prep sheet for a tiffin cook's WhatsApp, then had to delete the scoreboard
published: false
tags: hacktoberfest, python, machinelearning
---

# The 10pm notebook problem, without the fake 100%

A home tiffin cook in Pune or Bengaluru often has 30 to 50 customers. They order on WhatsApp, in Hinglish, late. "Kal lunch 2, dinner skip." "Aaj raat 1, bina pyaaz." "Roommate left, cancel one." The cook copies that into a notebook after the burners are off. A missed cancel is food in the bin. A missed extra is a hungry customer.

A Google Form would be cleaner, and it is free. It fails when the customers will not open it. They already have the cook's chat. The form is another app they will ignore on a Tuesday. That is the only reason a parser is worth building. The cost of that choice is the export: WhatsApp still makes the cook tap Export Chat and upload a file every night. I have not removed that step. If that is too much, the notebook wins, and it should.

## What the program does

TiffinTally is a small FastAPI app. You paste the export. A parser reads Android and iOS headers, including `13.10.26` and `2026-10-13 22:18`, which the first version glued onto the previous message. It no longer treats the word "left" as a WhatsApp system line, so "roommate left for home" stays an order.

A regex labels the meal, the quantity, and the day. "Aaj", "today", and "tonight" mean the day of the message. "Kal" and "tomorrow" mean the next day, counted from the message timestamp, not from whenever the cook opens the laptop. A note sent at 00:30 no longer slides onto the wrong sheet. The reconciler then drops anything that is not the day being cooked, applies cancels, and prints packing lines.

Standing orders used to add Priya, Rahul, Vikram, Amit, and Sneha to every upload. Four real thalis became ten. Those names are gone unless a cook configures them. Each browser gets its own cookie. Another visitor does not see the last cook's customers. That is process memory, not a proper multi-tenant store. I would not put a real export on a public URL yet.

If `GOOGLE_API_KEY` is set, extraction calls Gemma and sends the key in a header, not the query string. If it is not set, the page says "rules fallback". The fine-tune that ran on Modal is a 0.5B Qwen LoRA. It is not wired into this app. I am not going to pretend the sheet is using it.

Voice notes without a speech key return a stub that says the file was not transcribed. They used to invent a sentence from the filename. A file named `cancel.ogg` is not a cancel.

## What I claimed, and what was untrue

I published a 100% exact match on "50 real WhatsApp messages". The file lived in `data/synthetic/`, it was produced by the generator, and most of those strings were also in the training file. The test split had the same problem: hundreds of test rows were copied into train. A model can memorise that and look perfect.

The labels were wrong in a second way. Messages that said "aaj", "today", or "tonight" were marked `tomorrow`, and the test file was all `tomorrow`. A perfect score had learned the bug.

The Tinker write-up described a 3B LoRA on Thinking Machines' platform. The runs were Qwen2.5-0.5B on Modal. The Tinker client posted to a host that does not exist and, with no key, returned the regex under a model name. Those early "Gemma" and "Tinker" eval files have the same scores and a latency under a millisecond. That is the regex. I deleted the claim. `benchmark-edge` slept and printed catalog numbers, including a 100% and a Raspberry Pi latency. It now exits with an error.

The forecast number 0.79 was scikit-learn's HistGradientBoosting on 90 days of invented history. I turned that into ₹4,218 a month and an 18x return. Those are assumptions, and the post did not say that TabPFN's client licence is non-commercial. There is no saved TabPFN call. `tiffintally.tech` does not serve this app. There is no Dockerfile in the tree, so "containerized on Render" was a plan, not a deploy.

I also wrote a visit to a cook in Karve Nagar, with quotes about a kitchen screen and a voice feature that were committed the next day. That visit did not happen. It is gone. There is no first user yet.

The planning notes in `hf26-w2-sidehustle/` are the brief I wrote before building. They are not evidence.

## What I would need before asking anyone to pay

Fifty real messages from a cook, labelled by hand, kept out of training, and scored once. A Gemma call with the key set, saved as JSON, named as Gemma only if it did not fall back. Either a real Tinker job or no Tinker category. Either a real TabPFN job, with the non-commercial licence in the post, or no TabPFN category. One measurement on a machine if I want to talk about latency. A deploy, or silence about a domain.

Until then the honest demo is the paste box, the prep sheet, and the sentence on that sheet that says which extractor ran. The tests cover the parser, the dates, the empty standing-order list, and the split. They do not cover a model I have not called.

I would still build the sheet. I would not sell the scoreboard.
