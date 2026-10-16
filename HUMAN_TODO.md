# Human decisions and evidence

- Supply the original audit probe sources; only the two Markdown reports arrived.
- Collect consented cook exports or blind human-written messages; label without
  model outputs, independently relabel, split before scoring and supply provenance.
- GPU budget: ZERO calls. No training or hosted Modal inference is authorized.
  Reruns need `approved: gpu calls <N>`; training needs `approved: train` from Vedant.
- Supply GOOGLE_API_KEY through the environment for a free-tier baseline if wanted.
- Redeploy or stop the Modal app yourself and verify unauthenticated requests fail.
- Decide the Qwen research licence story before any commercial use.
- Review the branch, numerical evidence, policy and secondary allocation convention.
- The original ignored `data/privacy_map.db` may contain prior local mappings.
  Current code does not read it. Review and delete that pre-existing private file
  yourself if no longer needed; this round preserves pre-existing data.
- The new dev2 rows are agent-authored synthetic development data, not human labels.
  Review the proposed secondary-allocation errata before using it as training gold.
- Human holdout labelling must be blind, independently checked, and split before
  any scoring. The loader requires collector, date, consent, source, labeller,
  label_date and second_labeller on every row. A repeated call must not consume a
  previously scored holdout to tune rules.
- Use `scripts/label_cli.py label --input data/private/raw_real.txt --provenance
  data/private/provenance.json` to author all events without model suggestions.
  Independently review labels, then use its `freeze` command before an explicit
  private `--human-holdout` run. Complete the blind repeat-label agreement check
  described in docs/planning/FIX_PROMPT4.md; the agent cannot supply that evidence.
