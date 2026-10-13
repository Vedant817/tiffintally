# Deployment Guide: Render Free Tier + .tech Domain

Follow these steps to deploy TiffinTally to Render and attach your custom `.tech` domain.

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
   - `GOOGLE_API_KEY`: Your Google AI Studio API key
   - `GEMMA_MODEL`: `gemma-2-9b-it` (or `gemma-3-27b-it`)
   - `TABPFN_API_KEY`: Your Prior Labs TabPFN API key (optional for demo)
   - `TINKER_API_KEY`: Your Tinker API key (optional)
   - `ELEVENLABS_API_KEY`: Your ElevenLabs API key (optional)
   - `TIFFINTALLY_DEMO_MODE`: `true`

6. Click **Apply**. The deployment build will take ~2-3 minutes.

---

## 3. Verify Health Check

Once the deployment shows "Live", test the endpoint:
```bash
curl https://tiffintally.onrender.com/health
# Response: {"status":"healthy","version":"0.1.0"}
```

---

## 4. Connect Custom `.tech` Domain

1. In the Render Dashboard, go to your `tiffintally` service settings.
2. Under **Custom Domains**, click **Add Custom Domain**.
3. Enter your domain: `tiffintally.tech` (and `www.tiffintally.tech`).
4. Render will display DNS target records (e.g. `CNAME` pointing to `tiffintally.onrender.com` or an `A` record).
5. Go to your domain registrar (where you claimed the `.tech` domain):
   - Add a `CNAME` record for `@` or `www` pointing to `tiffintally.onrender.com`.
6. Render automatically provisions a free Let's Encrypt TLS/SSL certificate.
