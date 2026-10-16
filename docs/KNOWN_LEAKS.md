# Known split leakage

Do not tune away these findings or rewrite the frozen test.

This report uses masked character shingles, not the unavailable auditor script.

| Split | Row | Train neighbour | Jaccard | Prompt copy |
|---|---|---|---|---|
| test | syn_0650 | syn_0151 | 0.667 | False |

All neighbour distances and sibling pairs: `evals/final/leakage.json`. Legacy dev is a training subset. dev2 is agent-authored synthetic development, not an independent human evaluation. The split_report.json legacy note is wrong; its hashes are preserved, with corrected metadata in split_report_v2.json.
