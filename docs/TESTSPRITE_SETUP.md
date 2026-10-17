# TestSprite automated PR testing — setup and status

TestSprite 3.0 is a third-party automated testing service. It generates a browser-level
test suite against a live URL, and runs that suite automatically on every pull request
through its GitHub App. Nothing about it is required to build or run TiffinTally — the
product stands on its own. It is wired in as an extra verification layer.

Reference: <https://docs.testsprite.com/web-portal/integrations/github-integration>

---

## Why the deployment half already exists

TestSprite does not build or deploy anything. It **listens** for a signal that means
"this code is built, deployed and reachable", then points its suite at a URL. So the
repository had to produce that signal before anything in the portal could work.

| Requirement | Where it comes from | State |
| --- | --- | --- |
| Public source repository | This repo | Done |
| Live HTTPS deployment | Render service `tiffintally` → <https://tiffintally-lbn2.onrender.com> | Done, verified |
| Per-PR deployment of the PR's own code | `.github/workflows/preview.yml` | Done, verified |
| "Deployment ready" signal GitHub can see | GitHub deployment record + `active` status carrying the preview URL, plus a bot comment on the PR | Done |
| Repository to attach the GitHub App to | `Vedant817/tiffintally` | Done |
| TestSprite account / workspace | TestSprite portal | **Needs a human** |
| Generated test suite | TestSprite portal | **Needs a human** |
| Pull Request trigger | TestSprite portal | **Needs a human** |

The remaining steps all live behind an authenticated TestSprite session, so they cannot
be completed from an agent session without account credentials.

---

## What a human needs to do

Roughly ten minutes. Keep the app deployed and reachable while you do it — the suite is
generated against the live URL, and the PR check has nothing to hit if the service is
down.

### 1. Create the account

Sign up at <https://www.testsprite.com/auth/cognito/sign-up> using the email address you
will be identified by. Sign-in: <https://www.testsprite.com/auth/cognito/sign-in>

### 2. Connect GitHub to the workspace

1. TestSprite → **Workspace Settings → Connections → Integrations**.
2. Find the **GitHub** row → **Connect**.
3. On GitHub, choose the `Vedant817` account, then **Only select repositories** and pick
   `tiffintally` (granting all repositories is not needed).
4. **Install & Authorize**. You are returned to TestSprite showing **Connected**.

The App requests read access to actions/checks/issues/metadata and read-write access to
code, commit statuses, deployments and pull requests.

### 3. Create the project and generate the suite

1. **New project**, pointed at <https://tiffintally-lbn2.onrender.com>.
2. Generate the test suite against that URL.
3. Review what it produced before continuing — see the scenario checklist below.

### 4. Create the Pull Request trigger

1. Project → **GitHub Action** tab → **Add Trigger** → **Pull Request**.
2. Paste the URL of a PR that has a working preview deployment, then **Detect Events**.
3. Select the event that means *deployment finished*. On this repo that is the
   `PR Preview` workflow run, or the deployment status it posts.
4. **Target URL pattern** — previews are one Render service per PR, named
   `tiffintally-pr-<number>`, so Render assigns the host. Use the event's own
   environment URL if the picker offers it; otherwise use the `{pr}` placeholder form
   that matches the host Render generated, confirmed from a live preview comment.
5. **Send Test Event**, then confirm a `testsprite-dev` comment appears on the PR and
   updates in place.
6. **Create Trigger** — it appears as **Active**.
7. Leave **Block PR until tests pass** off until a few runs are green.

### 5. Confirm it runs without being asked

Push another commit to an open PR and confirm a new run starts on its own. That is the
difference between a wired-up integration and a one-off manual run.

---

## Suite design guidance

A suite that clicks through the happy path and passes proves very little. Cover the
behaviour that actually matters for this product:

**Core workflow**
- Load `/` and confirm the paste form and its controls render.
- Submit a small Hinglish chat export containing clear order lines.
- Confirm a prep sheet appears with per-meal counts for the selected date.
- Submit a cancellation after an order and confirm the meal count drops.
- Confirm an uncertain message is routed to review rather than silently counted.

**Daily policy and the ledger**
- Confirm the ledger and the prep sheet agree for the same date.
- A payment message in chat stays an unconfirmed claim; only after confirming receipt does
  it reduce the balance.
- Cancelled meals are not billed.
- A late cancel is handled the way the cutoff rule says, not silently dropped.
- Balances CSV export downloads and contains one row per expected customer.

**Input handling**
- Empty submission, non-chat garbage text, and an oversized paste are each rejected with
  a clear message rather than a stack trace or a silent no-op.
- A phone number and an address in the message do not appear anywhere in the returned
  sheet or ledger.

**State and isolation**
- Two different browser sessions do not see each other's sheets.
- Reloading the page does not duplicate orders.

**Failure and recovery**
- A malformed message degrades to the review queue instead of failing the request.

Use isolated test data. In the deployed demo `TIFFINTALLY_PERSIST=0`, so sessions are
already ephemeral and in-memory — nothing a test does can corrupt a real user's data. If
persistence is ever switched on, point the suite at its own throwaway kitchen rather than
production data.

---

## Honest status

No TestSprite result is claimed anywhere in this repository until a real run has been
observed on a real PR. See `docs/DEVELOPMENT_HANDOFF.md` §4 for the live status table and
§8 for what has actually been verified.

When the suite exists, add one line to the **Automated testing** section of `README.md`
naming it and what it covers. Do not add that line before a run has actually passed.