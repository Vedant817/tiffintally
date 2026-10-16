# To the Statistician: what may be claimed?

Question: can the saved legacy model aggregates establish that adaptation helps,
and what should the repaired scorer report?

Statistician response: refuse superiority signoff without aligned saved predictions
and a paired interval excluding zero. The only currently complete predictions are
from the cleaned rules. Their synthetic labels and sibling templates prevent a
generalisation claim about real cook conversations. No plausible reconstruction
of the private adapter's missing predictions is admissible evidence.

Implement event-set strict and lenient match, Wilson score intervals for individual
row accuracies, exact binomial McNemar on discordant paired outcomes, and a paired
bootstrap that samples whole templates with replacement. Keep row-weighted means
within each bootstrap draw; do not resample individual siblings independently.
Report leave-one-template-out sensitivity and category counts. A same-file
comparison checks the statistics plumbing; it is not a comparison of two systems.

References actually fetched during this round:

- https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html
  documents exact McNemar using the binomial distribution and discordant counts.
- https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html
  documents Wilson score intervals for binomial proportions.

The template bootstrap is the explicit analysis design here; neither reference
certifies that this synthetic dataset estimates real-world accuracy.

Public claim sentence: The saved synthetic results describe the cleaned rules only;
they establish neither model superiority nor accuracy on real cook messages.
