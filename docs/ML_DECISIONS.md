# Does fine-tuning add value?

Unknown. The old adapter aggregate cannot be independently recomputed. No aligned
few-shot base, adapter and hybrid predictions exist under the shared scorer.
The cleaned rules have saved predictions; the offline hybrid is deliberately
marked incomplete because its reviewed rows have not reached a language model.
It cannot be cited as a model result or an improvement.

Use `scripts/run_baselines.py` for regex and the offline hybrid. Base, adapter and
hosted baselines default to NOT RUN. A future GPU execution requires a plain
approval line in HUMAN_TODO.md; both HTTP requests and message counts consume
the durable cap. Failed requests consume their reservation; there are no retries.
Few-shot examples are selected by training ID. The deployed endpoint does not
support a custom prompt, so the harness refuses to call that an eight-shot run.
Implement and review that contract before approving the comparison.

Human holdout consumption requires an explicit `--human-holdout` run, complete
provenance, a matching pre-score freeze and private output paths. Each named
system consumes a durable receipt before scoring; even a failed run stays consumed.
An incomplete hybrid cannot consume the holdout. A supplied key alone is
not evidence that a free hosted baseline ran. GPU configuration and adapter SHA
must be captured by the endpoint before any future result can be called reproducible.
