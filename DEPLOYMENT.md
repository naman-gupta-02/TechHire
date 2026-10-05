# Deploying TechHire

A step-by-step guide to getting a free, publicly reachable demo live. Free-tier limits on these platforms change over time — check current terms at signup, the shape of the setup below won't change much even if specific limits do.

**Recommended stack:**

| Piece | Service | Why |
|---|---|---|
| Postgres | [Neon](https://neon.tech) | Serverless Postgres, generous free tier, standard for portfolio projects |
| Redis | [Upstash](https://upstash.com) | Serverless Redis, free tier, pairs well with a Render/Railway-hosted API |
| Backend | [Render](https://render.com) (or [Railway](https://railway.app)) | Deploys straight from the repo's `Dockerfile` |
| Frontend | [Vercel](https://vercel.com) | Native Vite support, deploys straight from `frontend/` |

You'll need this repo pushed to GitHub (it already is) and accounts on the four services above.

---

## 1. Postgres (Neon)

1. Create a project at neon.tech.
2. Copy the connection string it gives you — it looks like `postgresql://user:pass@ep-xxxx.neon.tech/dbname?sslmode=require`.
3. Nothing to enable by hand for RAG: Neon ships the `pgvector` extension, and the API runs `CREATE EXTENSION IF NOT EXISTS vector` on startup.
3. Keep this — it's your production `DATABASE_URL`.

---

## 2. Redis (Upstash)

1. Create a database at upstash.com (choose the region closest to where your backend will run).
2. Copy the **Redis URL** (the `rediss://...` connection string, not the REST API URL).
3. Keep this — it's your production `REDIS_URL`.

---

## 3. Backend (Render)

1. New → Web Service → connect your GitHub repo.
2. Environment: **Docker**. Render will detect the root `Dockerfile` automatically.
3. Set environment variables (Render → your service → Environment):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string from step 1 |
   | `REDIS_URL` | the Upstash connection string from step 2 |
   | `GROQ_API_KEY` | your key from console.groq.com |
   | `ADMIN_API_KEY` | a random secret — generate one with `openssl rand -hex 32` |
   | `ALLOWED_ORIGINS` | leave as `http://localhost:5173` for now, you'll update this in step 5 |

4. Deploy. Once it's live, note the backend URL (e.g. `https://techhire-api.onrender.com`).
5. Sanity check: `curl https://<your-backend-url>/health` should return `{"status":"ok"}`.

> Free-tier web services on Render spin down after inactivity and take ~30-60s to wake on the next request — expect a cold-start delay on the first load after idle time. Worth mentioning if a recruiter tries the link and it's slow to respond initially.

---

## 4. Frontend (Vercel)

1. New Project → import your GitHub repo.
2. Set **Root Directory** to `frontend`.
3. Framework preset: Vite (should auto-detect).
4. Add an environment variable:

   | Key | Value |
   |---|---|
   | `VITE_API_BASE_URL` | your Render backend URL from step 3, e.g. `https://techhire-api.onrender.com` |

5. Deploy. Note the resulting URL (e.g. `https://techhire.vercel.app`).

---

## 5. Close the loop: CORS

Go back to Render → your backend service → Environment, and update:

```
ALLOWED_ORIGINS=https://techhire.vercel.app
```

(comma-separate if you also want to keep localhost for local dev against the prod backend). Redeploy the backend for the change to take effect.

---

## 6. Smoke test checklist

- [ ] Load the Vercel URL — jobs grid renders (may be empty until you trigger a refresh)
- [ ] Filters work and don't error in the browser console
- [ ] Open a job → AI summary generates (confirms `GROQ_API_KEY` + CORS are correct)
- [ ] Upload a resume in the Resume Checker → analysis returns
- [ ] Click Refresh without an admin key → prompts for one (confirms `ADMIN_API_KEY` is wired)
- [ ] Enter the admin key → refresh starts, `/scrape/status` shows progress

---

## Populating initial data

`python main.py` pulls real, live postings from Greenhouse, Lever, and Ashby's public job-board APIs — no key needed. Run it locally against your **production** `DATABASE_URL` once to seed real data:

```bash
DATABASE_URL="<your Neon connection string>" python main.py
```

This alone gets you ~1,000 real postings from real companies (Stripe, OpenAI, Databricks, Palantir, Ramp, and others — see `scraper/runner.py`'s `SCRAPE_CONFIGS` for the full list). Add `RAPIDAPI_KEY` too if you also want the broader keyword-search coverage from JSearch (Indeed/Glassdoor/Handshake) — optional, not required to have real data in production.

`main.py` also builds the RAG index (chunks + embeddings for "Ask TechHire" and similar roles) as its last step — about 3–4 minutes of CPU for ~1,000 postings the first time, then only new or changed postings on later runs. To (re)build just the index:

```bash
DATABASE_URL="<your Neon connection string>" python scripts/build_rag_index.py
```

> Memory: the API keeps the embedding model loaded after the first RAG request. Measured locally: ~110 MB for the API alone, ~300 MB peak once the model is loaded (ONNX Runtime adds ~190 MB). That fits Render's free 512 MB instance, but with less headroom than before — the model is the largest single chunk of the API's memory.
