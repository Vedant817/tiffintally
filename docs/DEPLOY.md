# Deployment notes (not a live deploy)

Nothing here has been deployed. `https://tiffintally.tech` does not serve this app. There is no Dockerfile. `render.yaml` is a blueprint only.

The steps below are a plan for later. Do not describe them as done.

One thing to decide before making a public URL: with `GOOGLE_API_KEY` set, every paste is sent to Google in masked form and spends the owner's quota. Leave the key unset for a rules-only public demo.

# Deployment guide: Render free tier

Follow these steps if you later deploy TiffinTally. A custom domain is optional and is not attached.

> [!IMPORTANT]
> **No Credit Card Rule:** Render's free web service tier does NOT require a credit card. If you are ever prompted for card details during setup, **STOP immediately**, log it in `docs/DECISIONS.md`, and inform the team.

---

## 1. Prerequisites

1. Public GitHub repository: `https://github.com/<your-username>/tiffintally`
2. Free Render account at [render.com](https://render.com)
3. Free `.tech` domain from Hacktoberfest promos (or student developer pack)

---

## 2. Deploy via Render Blueprint (One-Click)

1. Log into [Render Dashboard](https://dashboard.render.com).
2. Click **New +** -> **Blueprint**.
3. Select your `tiffintally` GitHub repository.
4. Render will read `render.yaml` and configure:
   - Service name: `tiffintally`
   - Runtime: Python 3.11
   - Plan: Free
   - Build Command: `uv sync`
   - Start Command: `uv run uvicorn tiffintally.app:app --host 0.0.0.0 --port $PORT`
   - Health check: `/health`

5. In the **Environment Variables** panel in Render, fill in the values:
   - `TIFFINTALLY_DEMO_MODE`: `true`
   - `EXTRACTOR_BACKEND`: `off` (rules only) or `gemini` (hosted Gemma)
   - `GOOGLE_API_KEY`: your Google AI Studio API key. Leave it unset for a rules-only public demo.
   - `GEMMA_MODEL`: `gemma-4-26b-a4b-it` (the default; only read when the gemini backend is selected)

6. Click **Apply**. The deployment build will take ~2-3 minutes.

---

## 3. Verify Health Check

Once the deployment shows "Live", test the endpoint:
```bash
curl https://tiffintally.onrender.com/health
# Response: {"status":"healthy","version":"0.1.0"}
```

---

## 4. Custom domain, only after a deploy exists

`tiffintally.tech` does not point at this app. Do not type that name into Render unless you own the domain and intend to attach it.

1. In the Render Dashboard, go to your service settings.
2. Under **Custom Domains**, click **Add Custom Domain**.
3. Enter a domain you control.
4. Render will display DNS target records (e.g. `CNAME` pointing to `tiffintally.onrender.com` or an `A` record).
5. Go to your domain registrar (where you claimed the `.tech` domain):
   - Add a `CNAME` record for `@` or `www` pointing to `tiffintally.onrender.com`.
6. Render automatically provisions a free Let's Encrypt TLS/SSL certificate.
