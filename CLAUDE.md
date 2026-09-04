# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GRID Expense Tracker — a personal-finance app with a CLI and a Streamlit web UI. Free features (expenses, income, budgets, subscriptions, goals, assets/liabilities) run **locally** against `data.json`. Paid features (AI categorization, forecasting, anomaly detection, receipt OCR, net worth, etc.) run **server-side** on two Google Cloud Run services and are gated by a JWT **license key**. Understanding the split between the local app and the two cloud services is the key to working here.

GCP project: `fair-geography-493716-q4` (number `690527435721`), region `us-central1`. The GitHub repo is **public** — secrets live in Secret Manager and gitignored `.env` files, never in code.

## Commands

```bash
# Setup
python -m venv .venv && .venv\Scripts\activate   # (source .venv/bin/activate on mac/linux)
pip install -r requirements.txt

# Run the app (prompts: CLI or Web UI)
python run.py
streamlit run CLI/app/main.py                    # web UI directly

# Smoke-test the data layer (not pytest — a script)
python test_backend.py

# Run a cloud service locally (FastAPI)
cd backend      && uvicorn server:app --reload --port 8080
cd auth-service && uvicorn main:app   --reload --port 8081

# Issue a license key by hand (prints a JWT; does NOT record/email it)
python auth-service/gen_code.py buyer@example.com pro    # or: max
```

The version string lives in `CLI/core/core_stuff.py` (`__version__`) and the README changelog table — bump both together.

## Deploy (read before pushing)

- **`backend`** auto-deploys via GitHub Actions (`.github/workflows/deploy-backend.yml`) on any push touching `backend/**`. Auth is **Workload Identity Federation (keyless)** — an org policy blocks service-account JSON keys, so do **not** reintroduce `credentials_json`; the workflow needs `permissions: id-token: write`. Cloud Run service name: `expense-backend`.
- **`auth-service` has no CI** — deploy it manually after changes:
  ```bash
  gcloud run deploy auth-service --source auth-service --region us-central1 --allow-unauthenticated --project fair-geography-493716-q4
  ```
- Cloud Run filesystems are **ephemeral** — never persist state to local files/SQLite on these services (this is why the license ledger and IP store are in Firestore). Both services run as the default compute SA, which has `roles/datastore.user`.

## Architecture

Three layers that only connect through the **license JWT** and the cloud HTTP APIs:

1. **Local app** (`run.py`, `CLI/`): `CLI/core/core_stuff.py` (`ExpenseTracker`) is the entire data layer — all CRUD reads/writes `data.json`. `CLI/app/` is the Streamlit UI. **`main.py` is the entrypoint** — an `st.navigation` router that declares every page and its URL (`/overview`, `/monthly`, `/settings`, …); `Dashboard.py` is the Overview page, the rest live in `pages/`. `theme.py` owns all styling plus the top navbar and the sidebar. Do not add a page by dropping a file in `pages/` — the `pages/` auto-discovery is off; register it in `main.py`'s `PAGE_SPECS`. `CLI/app/config.py` holds a `BACKEND_MODE` toggle and the hardcoded Cloud Run URLs the client calls. `CLI/app/streamlit_setup.py` wires session state + sync helpers.

2. **`backend`** (Cloud Run `expense-backend`): FastAPI AI/analytics. `server.py` defines endpoints; `analytics.py` (math), `ai.py` (LLM via Groq/OpenRouter), `bots.py` (CrewAI categorization crew), `ocr.py` (Google Vision). Pro/Max endpoints depend on `require_pro` / `require_max`, which decode the license JWT **statelessly** (no DB lookup) and then enforce per-key IP limits via `ip_limits.py` → Firestore `license_ips` (Pro 3 / Max 6 distinct IPs; fails open if Firestore is unreachable). `/admin/reset-activations` (header `X-Admin-Secret` = `ADMIN_RESET_SECRET`) clears a key's IPs.

3. **`auth-service`** (Cloud Run `auth-service`): mints/records/emails license keys. `jwt_utils.py` builds the HS256 JWT carrying `sub`/`tier`/`features`/`jti`/`max_ips`/`exp`; `TIER_FEATURES` + `TIER_IP_LIMITS` define the tiers. `_issue_license()` in `main.py` is the single mint+record+email path, used by both `/issue` (manual/trusted, requires `X-Issue-Secret`) and `/redeem` (public, auto-issue). Records go to Firestore collection `licenses` with **doc id = order_id** (or the tx hash) so `create()` gives atomic, cross-instance idempotency. Email is **best-effort** (never 500s issuance) via `EMAIL_PROVIDER` = `smtp` (Gmail `SMTP_USER`/`SMTP_PASS`) or `resend`; the full token is stored so a key can be re-sent from the ledger.

**Cross-service contract:** both services read `JWT_SECRET` from Secret Manager and must use the **same value** — auth-service signs, backend verifies. If they diverge, every key fails verification.

**Both services now FAIL CLOSED on secrets (changed 2026-09-01).** `JWT_SECRET` used to default to `"change-me-in-production"` with only a log warning, so a missing Secret Manager binding produced a service that booted healthy and honoured licences forged with a placeholder published in this public repo. Both now `raise RuntimeError` at import unless `JWT_SECRET` is set, ≥32 chars, and not a known placeholder. Consequences to know before deploying:
- **A missing/short secret is now a crash-loop, not a silent downgrade.** That is deliberate. Check Cloud Run logs for the `JWT_SECRET is …` message.
- Local runs without the secret need `ALLOW_INSECURE_JWT_SECRET=1`. **Never set it on a deployed service.**
- `ISSUE_SECRET` is likewise required: unset now makes `/issue` return 503 instead of minting licences for anyone who asks.
- `X-Forwarded-For` is read from the **right**, not the left, in both services (`TRUSTED_PROXY_HOPS`, default `0` for a direct `*.run.app` URL). Raise it only if you put a custom LB/Cloudflare in front — setting it too high lets callers spoof their IP and evade both rate limits and the per-licence device cap.
- `backend/.env.example` and `auth-service/.env.example` are the committed templates listing every variable. Keep them free of real values.

**Automatic crypto issuance:** `auth-service/onchain.py` verifies a Base USDC payment from a tx hash via a **public Base RPC** (`https://mainnet.base.org`, no API key) — checks it's a confirmed USDC transfer to the store wallet ≥ the tier price. `/redeem` runs this, then `_issue_license(order_id=tx_hash)`. The web-store buy page (`portfolio/store/web-store`, separate repo) calls `/redeem` for Pro/Max tiers; other products keep a manual flow. `onchain.py` constants (wallet, accepted USDC contracts, min confirmations) are env-overridable.

## Hosted / enterprise mode (multi-tenant)

A fourth layer sits alongside the three above, added 2026-07-22. It does **not**
change the free product: `STORAGE_MODE` (in `CLI/app/config.py`, env-driven)
selects the storage backend and defaults to `local`.

- **Free / self-host** → `JsonStore` → `data.json`. No account, no DB, offline. Unchanged.
- **Paid / hosted** → `PostgresStore` → **Neon Postgres**, one organization per customer.

**Why Neon and not Supabase:** Matt hit the Supabase free-project limit. Neon's
free tier allows ~100 projects. Everything is plain Postgres — there is no
`auth.users`, no `auth.uid()`, and **no RLS**. That is deliberate: only the Python
backend and the Cloudflare worker ever connect (both server-side with the
connection string), so **tenancy is enforced in the app layer** by scoping every
query to `org_id`. Neon RLS is available later as defense-in-depth.

Key pieces:
- `CLI/core/storage.py` — `StorageBackend` (ABC), `JsonStore`, `PostgresStore`.
  `core_stuff.py`'s `open_file`/`write_file` delegate to `self.store`; that
  two-method chokepoint is why none of the ~40 CRUD methods needed changes.
- `CLI/core/tenancy.py` — `AuthUser`, `make_store()`, `claim_and_resolve_org()`,
  `create_org()`, `get_role()`. Pure Python, **no streamlit / no provider SDK**,
  so it is unit-testable and works for CLI, UI, or a future API.
- `db/migrations/00{1,2,3}_*.sql` — schema, entitlements, concurrency. Applied to Neon.

**PostgresStore invariants — do not regress these:**
- `write()` is **diff-based** (insert/update/delete only what changed), so row
  ids, `created_at` and the audit trail survive saves. Never go back to
  delete-all-and-reinsert.
- `organizations.data_version` gives **optimistic concurrency**. A write from a
  stale snapshot raises `ConcurrentModificationError` instead of silently
  clobbering a co-worker. UI should catch it, reload, and re-apply.
- `read()` is **one round trip** (`jsonb_build_object` over all nine tables) and
  caches the snapshot that `write()` diffs against. This matters: a remote Neon
  region is ~250ms RTT, and the naive version cost ~11s per operation.
- Every mutation is written to `audit_log` (before/after jsonb, batched).

**Purchase → access:** the GRID store's `grid-store-worker` `/redeem` verifies the
USDC payment, mints the license JWT, records it in the Supabase licenses store
(unchanged), and **also upserts an `entitlements` row into Neon** (secret
`ET_DATABASE_URL`). Entitlements are keyed by **email** because the buyer has no
account at purchase time; on first login the app calls
`claim_entitlements(user_id, email)`, which creates/upgrades their org. Idempotent
on `order_id`. A signed-in user with no entitlement gets an upsell, not a workspace.

**Auth** is OIDC via Streamlit's native `st.login()` / `st.user` (1.42+), so Clerk,
Google or Auth0 all work without provider-specific code — `AuthUser.from_oidc()`
maps the claims.

## Notable gotchas

- **Two unrelated "license" concepts:** the app only accepts auth-service **JWTs**. The web-store's Cloudflare Worker `GRID-XXXXX` keys (and the separate `$34` "expense-tracker" repo-access product) are a different system the app does **not** understand — don't conflate them.
- `python-jose` provides the importable `jose` package, but a stale conflicting `jose` may sit in the local `.venv`; don't rely on it for ad-hoc JWT scripts (compute HS256 with stdlib `hmac` instead).
- `.gitignore` no longer blanket-excludes `*.json` (changed 2026-09-01). That rule gave only incidental cover to real secrets while also excluding `web/package.json`, `web/package-lock.json` and `web/vercel.json` — without which the Vercel build of `web/` cannot run at all. Secrets and user data are now listed **by name** (`.env*`, `key.json`, `*credentials*.json`, `*.pem`, `data.json`, `backups/`, `licenses.db`); `*.md`, `*.csv` and `*.pdf` are still excluded and `README.md` is force-tracked. When adding a new secret file, add it to `.gitignore` explicitly — nothing broad is catching it now.
- **All paid/LLM endpoints are now gated + rate-limited.** `slowapi` is wired up (`limiter` keyed on the real client IP via `X-Forwarded-For`); every LLM/CrewAI/OCR endpoint carries a `@limiter.limit(...)` and a license dependency. Pro/Max endpoints use `require_pro`/`require_max` (feature check + IP-activation limit); the 7 tiered AI endpoints (`/smart-budget-advisor`, `/expense-narrative`, `/cash-flow-forecast`, `/debt-planner`, `/investment-readiness`, `/financial-coach`, `/spending-dna`) use `_require_feature(...)`, which **also** enforces the per-key IP limit and each is capped at `10/minute`. Pure-math analytics endpoints (health-score, savings-rate, etc.) are public but rate-limited (no LLM cost).
- `published/app.py` is a standalone single-file Streamlit app for Streamlit Community Cloud; it imports `CLI.core.core_stuff` from the repo root and calls the same Cloud Run services. Each session uses an ephemeral tempfile, so its data does not persist.
