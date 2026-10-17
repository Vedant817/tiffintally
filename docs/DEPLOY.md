# Deployment notes

## What is actually deployed

As of 2026-10-17:

| Thing | State |
| --- | --- |
| Render web service `tiffintally` | **Live** at <https://tiffintally-lbn2.onrender.com> |
| `GET /health` on that URL | **Verified** `200 {"status":"ok","version":"0.1.0"}` |
| Auto-deploy from `main` | Enabled |
| Per-PR preview deployments | **Live** via `.github/workflows/preview.yml` |
| `https://tiffintally.tech` | **Does not serve this app.** No domain is attached. |
| Dockerfile | None. The service builds from `render.yaml` on the native Python runtime. |
| Hosted model key in the deployed demo | **Not set.** The demo answers with the local rules path. |

Everything else in this file is either a reproducible recipe or an explicitly open item.
Do not describe an open item as done.

## Deployment guide: Render free tier

The live service was created from the Render API with exactly the commands in
`render.yaml`. The steps below are the dashboard equivalent, for recreating it by hand.

> [!IMPORTANT]
> **No Credit Card Rule:** Render's free web service tier does NOT require a credit card. If you are ever prompted for card details during setup, **STOP immediately**, log it in `docs/DECISIONS.md`, and inform the team.

---

## 1. Prerequisites

1. Public GitHub repository: `https://github.com/Vedant817/tiffintally`
2. Free Render account at [render.com](https://render.com)
3. Optional: a `.tech` domain, claimed separately — **not** currently attached

## 2. Deploy via Render Blueprint (One-Click)

1. Log into [Render Dashboard](https://dashboard.render.com).
2. Click **New +** -> **Blueprint**.
3. Select the `tiffintally` GitHub repository.
4. Render reads `render.yaml` and configures:
   - Service name: `tiffintally`
   - Runtime: Python 3.11
   - Plan: Free
   - Build Command: `pip install uv && uv sync --frozen --no-dev`
   - Start Command: `.venv/bin/uvicorn tiffintally.app:app --host 0.0.0.0 --port $PORT`
   - Auto-deploy: on commit to `main`

   `uv` is installed explicitly because it is not guaranteed to exist in the build image.
   `--frozen` pins the deploy to `uv.lock`, so a deploy cannot quietly resolve a different
   dependency set than the one the suite was tested against.

5. In the **Environment Variables** panel, optionally add:
   - `GOOGLE_API_KEY`: a Google AI Studio key. **Omit it** and the app uses the local
     rules path and reports that honestly in the UI.
   - `MODAL_EXTRACTOR_URL` / `MODAL_EXTRACTOR_TOKEN`: fine-tuned adapter endpoint.
   - `ELEVENLABS_API_KEY`: morning voice brief.

   Never commit these. `.env.example` holds placeholders only, and CI runs `gitleaks`.

6. Click **Apply**.

## 3. Verify the deployment

```bash
curl -i https://tiffintally-lbn2.onrender.com/health
# HTTP 200, body: {"status":"ok","version":"0.1.0"}
```

A free instance idles out, so the **first** request after a quiet period can take ~30
seconds to answer. `curl` reporting a timeout once does not mean the deploy failed; retry.

`/health` returns liveness only. It deliberately does not enumerate features.

## 4. Custom domain, only after a deploy exists

`tiffintally.tech` does not point at this app. Do not type that name into Render unless
you own the domain and intend to attach it.

1. In the Render Dashboard, go to your service settings.
2. Under **Custom Domains**, click **Add Custom Domain**.
3. Enter a domain you control.
4. Render will display DNS target records (e.g. `CNAME` pointing to the
   `onrender.com` host, or an `A` record).
5. Go to your domain registrar and add the record Render specified.
6. Render automatically provisions a free Let's Encrypt TLS/SSL certificate.

## 5. Per-PR preview deployments

The Render free tier has no built-in preview feature, so previews are managed through the
Render API from CI. See `.github/workflows/preview.yml`.

One service named `tiffintally-pr-<number>` is created per non-draft PR, built from that
PR's head commit, and deleted when the PR closes. The workflow registers it as a GitHub
deployment and comments the URL, so anything listening for a deployment signal — including
third-party PR testing — has something real to test against.

Required repository configuration:

- Secret `RENDER_API_KEY`
- Variable `RENDER_WORKSPACE_ID`

Free-tier service slots are shared. Several PRs open at once can exhaust them; the
workflow fails loudly rather than silently skipping a deployment.

## Public URL extractor decision (17 Oct 2026)

`EXTRACTOR_BACKEND` is defined in `render.yaml` as `sync: false`, so the dashboard owns its
value. **Recommended value for the public demo: `off`.**

- With `EXTRACTOR_BACKEND=off`, every paste is read by the on-device regex rules. Nothing is
  sent to any third party, and the page says "Rules (regex) only".
- Left unset, `tiffintally/extract/gemma.py` selects the `gemini` backend the moment
  `GOOGLE_API_KEY` is present. So adding a key later would silently change what a public URL
  does with a visitor's pasted chat. Setting `off` keeps the demo on the rules no matter what
  else is configured.
- No `GOOGLE_API_KEY` is configured on the live service today, and that was verified by hand:
  `POST https://tiffintally-lbn2.onrender.com/process` returns the rules-only banner.
- `GEMMA_MODEL` is only read when the `gemini` backend is selected, so leaving both unset keeps
  the current behaviour exactly.

To exercise hosted extraction, set `EXTRACTOR_BACKEND=gemini` and add a key, and expect masked
text to leave the instance and spend the owner's quota. That is a deliberate choice, not a
default.

Demo mode is on for the live service: `TIFFINTALLY_DEMO_MODE=true` and `TIFFINTALLY_PERSIST=0`,
so a visitor's pasted chat is held in that browser session's memory and never written to disk.

Free tier sleeps: a service that has been idle cold-starts on the next request, so open the
public URL about a minute before recording a demo.
