# Deploying ORDER — Vercel (frontend) + Render (backend) + Supabase (database)

Architecture: one Vercel project serves the React SPA for **all** restaurant domains and
proxies `/api/*` to the Render backend. The backend resolves the tenant from the original
host (forwarded by Vercel) and enforces isolation with Postgres RLS on Supabase.

```
customer / restaurant domain ──► Vercel (SPA + /api proxy) ──► Render (FastAPI) ──► Supabase (RLS)
```

---

## 0. Prerequisites (do once)

1. **Rotate the leaked secrets** in `backend/.env` (DB password, `SUPABASE_SERVICE_KEY`,
   `OPENAI_API_KEY`, `JWT_SECRET`). Generate a fresh JWT secret:
   `python -c "import secrets;print(secrets.token_urlsafe(48))"`.
2. Push the repo to GitHub (Render + Vercel deploy from Git).
3. Have your Supabase project ref handy (the `xxxx` in `db.xxxx.supabase.co`).

---

## 1. Database (Supabase)

You connect to Supabase **through the Supavisor pooler** from Render (Render egress is IPv4;
the direct DB host is IPv6-only). Use **Session mode** — the app sets a per-connection RLS GUC
and the chatbot commits mid-request, which transaction mode (port 6543) would break.

1. In Supabase → **Database → Connection string → Session pooler**, copy the string. It looks like:
   `postgresql://postgres.<ref>:<pwd>@aws-...pooler.supabase.com:5432/postgres`
   This is your **owner** string → use it as `MIGRATE_DATABASE_URL`.

2. **Run the migrations** with the owner string (locally is fine):
   ```bash
   cd backend
   pip install -r requirements.txt
   DATABASE_URL='<owner session-pooler string>' python scripts/migrate.py
   ```
   This applies 0001–0013: tenant lifecycle, the 3 priced plans, domain verification,
   order idempotency, **RLS (creates the `order_app` role, NOLOGIN)**, and `chat_sessions`.

3. **Turn on the app role** (Supabase → SQL editor):
   ```sql
   ALTER ROLE order_app WITH LOGIN PASSWORD '<a-strong-secret>';
   ```
   The app role is `NOBYPASSRLS`, so the database now enforces tenant isolation.

4. Build the **app** connection string by swapping the role in the session-pooler string:
   `postgresql://order_app.<ref>:<the-password-you-just-set>@aws-...pooler.supabase.com:5432/postgres`
   This is your `DATABASE_URL`. Sanity-check it:
   ```bash
   DATABASE_URL='<app string>' python -c "import db; \
     import os; \
     conn=db._connect(); cur=conn.cursor(); cur.execute('select current_user'); print(cur.fetchone())"
   # expect: ('order_app',)
   ```

---

## 2. Backend (Render)

Easiest path: the repo ships `render.yaml`.

1. Render → **New → Blueprint** → pick this repo. It creates three services
   (`order-api` web, `order-worker`, `order-scheduler` cron), all rooted at `backend/`.
2. Fill the **`order-backend` env group** (secrets are `sync:false`):
   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the **order_app** session-pooler string (step 1.4) |
   | `MIGRATE_DATABASE_URL` | the **owner** string (step 1.1) |
   | `JWT_SECRET` | 32+ random bytes |
   | `OPENAI_API_KEY` | your OpenAI key (chatbot/opportunities degrade gracefully without it) |
   | `FRONTEND_ORIGIN` | your Vercel URL + custom domains, comma-separated |
   | `PLATFORM_DOMAIN_TARGET` | `cname.vercel-dns.com` |
   | `APP_ENV` | `production` (already set in the blueprint) |
   | `TRUST_FORWARDED_HOST` | `true` (already set) — lets the backend read the real customer host from Vercel |
3. Deploy. `preDeployCommand` runs migrations with `MIGRATE_DATABASE_URL` on each deploy.
   - **Free tier:** `preDeployCommand` isn't available — delete that line in `render.yaml`
     and run `python scripts/migrate.py` manually (step 1.2) before deploying.
4. Health check: `https://order-api.onrender.com/api/health` → `{"status":"ok"}`.
5. **Uploaded images** (`/api/admin/upload-image`) write to local disk, which is ephemeral on
   Render. Attach a **Render Disk** to `order-api` mounted at
   `/opt/render/project/src/backend/static/uploads` so images survive deploys. (A disk pins the
   web service to one instance; move uploads to object storage before scaling out.)

Manual alternative (no blueprint): create a **Web Service**, Root Directory `backend`,
Build `pip install -r requirements.txt`, Start `uvicorn main:app --host 0.0.0.0 --port $PORT`,
add the env vars above, plus a **Background Worker** (`python scripts/worker.py`) and a
**Cron Job** (`python scripts/schedule_jobs.py`, schedule `0 * * * *`).

---

## 3. Frontend (Vercel)

1. Edit `frontend/vercel.json` → set the rewrite destination to your Render URL:
   ```json
   { "source": "/api/:path*", "destination": "https://order-api.onrender.com/api/:path*" }
   ```
   (Replace `REPLACE_WITH_BACKEND_HOST`.) Commit.
2. Vercel → **New Project** → import the repo. Set **Root Directory = `frontend`**
   (Framework: Vite; build `pnpm build`; output `dist` — auto-detected).
3. Environment variables (Production):
   | Key | Value |
   |---|---|
   | `VITE_SUPABASE_URL` | your Supabase URL (only if any client feature still uses it) |
   | `VITE_SUPABASE_PUBLISHABLE_KEY` | the **publishable/anon** key (never the service key) |
   | `VITE_MAPBOX_TOKEN` | your Mapbox public token |
   `VITE_API_URL` is only used in local dev; in production the app calls same-origin `/api/*`.
4. Deploy. The SPA + `/api` proxy are now live on the Vercel URL.

---

## 4. Wire the platform + first restaurant

1. **Seed a platform super-admin** (Supabase SQL, owner connection):
   ```sql
   INSERT INTO platform_admins (email, password_hash, name)
   VALUES ('you@order.co', crypt('YourStrongPassword', gen_salt('bf')), 'Owner');
   -- needs pgcrypto: CREATE EXTENSION IF NOT EXISTS pgcrypto;
   ```
   (Or run `backend/scripts/seed_demo.py` if you prefer a scripted seed.)
2. Log in at `https://<your-vercel-domain>/platform-admin/login`, create a tenant, assign a plan.
3. **Custom domain for a restaurant:**
   1. Add the domain to the **Vercel project** (Settings → Domains) — Vercel issues TLS.
   2. Restaurant points DNS: apex `A → 76.76.21.21`, or `www`/subdomain `CNAME → cname.vercel-dns.com`.
   3. Add a verification `TXT` record `_order-verify.<domain>` (value shown by the super-admin).
   4. In super-admin, add the domain to the tenant and click **Verify** — it becomes live only
      after the DNS proof passes. Platform subdomains work the same way.

---

## 5. Verify the live deployment

```bash
# backend up
curl https://order-api.onrender.com/api/health

# tenant routing works through Vercel (host forwarded as x-forwarded-host)
curl https://<restaurant-domain>/api/menu          # -> that tenant's menu
curl https://<unconfigured-domain>/api/menu        # -> 404 "Restaurant not found for this domain"
```
Then log into a restaurant admin at `https://<restaurant-domain>/admin` and confirm you only
see that restaurant's data.

---

## Gotchas (read before launch)

- **Session pooler only** (port 5432 via the pooler host). Transaction mode (6543) breaks the
  RLS GUC / chatbot.
- **`TRUST_FORWARDED_HOST=true` is required** so the backend uses the real customer host that
  Vercel forwards. If known domains 404, confirm Vercel is sending `x-forwarded-host`.
- **Migrations run as owner, the app runs as `order_app`.** Never point `DATABASE_URL` at the
  owner role in production.
- **Render free web services sleep** and have an ephemeral disk — fine for a demo, not for
  production image uploads or low-latency.
- The Vercel custom-domain step (4.3.1) is manual per restaurant today; it can be automated
  later via the Vercel Domains API.
