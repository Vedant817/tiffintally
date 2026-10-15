# docs/

Planning notes and self-reviews. **Not evidence.**

| Path | What it is |
| :--- | :--- |
| `review/REDTEAM-round1.md` | First adversarial self-review of this repo. Historical. |
| `review/REDTEAM2.md` | Second self-review (15 Oct 2026). Its findings drove the fix order. |
| `planning/FIX_PROMPT2.md` | The ordered fix brief written from that review. |
| `planning/hf26-w2-sidehustle/` | Contest planning pack: idea board, timeline, agent prompts. |
| `DECISIONS.md` | Architecture and dependency decisions, with reasons. |
| `DEPLOY.md` | Render deployment steps. |
| `demo-script.md` | Shot list for the 60–90s demo recording. |

## The rule these files follow

A number in `README.md`, `RESULTS.md`, `post.md` or the UI must point at a file,
a test, a command that was run, or a live URL that shows it now.

Nothing in this directory is such a pointer. A claim sourced to a planning note
or a self-review is a claim about what was *planned* or *criticised*, never about
what the product does. Measured numbers live in `evals/runs/<timestamp>/` and are
cited by path from `RESULTS.md`.

The self-reviews are kept rather than deleted because the retraction history is
part of the honest record: round 1 of this project claimed numbers that did not
hold up, and that retraction is documented in `RESULTS.md` and the post.
