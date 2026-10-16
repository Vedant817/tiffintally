# Open gates after the round-four audit

## Historical batching diagnosis

The Gemini event-multiplication bug could not have affected the historical Modal
head-to-head or single-message eval runs. At the audited revision, head_to_head.py
posted directly to Modal and parsed positional results without GemmaExtractor;
tiffintally eval called extract_from_text with one message per call. The affected
Gemini batch path was neither measurement path. The earlier demand to remeasure
those aggregates because of that bug was incorrect.

Those aggregates still lack complete saved per-row predictions and the adapter
is private. That is the independent reason they cannot be rescored or used as
reproducible evidence. No rerun is claimed. The current head_to_head entry point
compares saved predictions only. The cleaned-rule artifacts have new explicit
strict and lenient metric definitions; they are not direct comparisons with the
old metrics.

## Human gates

See HUMAN_TODO.md. GPU budget is zero until an explicit approval is recorded.
The deployed endpoint's authentication status was reported by the audit; this
round did not contact, stop, modify or redeploy that app. A code fix is not proof
about the running service. Render, domain, video and the DEV post are outside this
technical round.

A consented human holdout, independent labelling, and licence decision remain
open. The newly written synthetic dev2 set does not satisfy that human task.
The proposed training label overlay is not approved gold and is not scored.

## Known technical limits

The original auditor probe sources were not supplied. Reconstructed regressions
are identified in tests/probes. Removed test-fitted dietary capabilities retain
strict expected-failure tests. Sibling leakage is documented, not repaired after
scoring. Historical duplicate run folders and the ignored local privacy database
are preserved because the brief prohibits deleting pre-existing data; the current
code neither reads nor creates that default database.

The baseline runner's hosted paths have not been called in this round. Few-shot
serving and verified adapter/decoding metadata still need an endpoint contract
before that comparison can be certified. No superiority claim is supported.
