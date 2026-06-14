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
streamlit run CLI/app/Dashboard.py               # web UI directly

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

1. **Local app** (`run.py`, `CLI/`): `CLI/core/core_stuff.py` (`ExpenseTracker`) is the entire data layer — all CRUD reads/writes `data.json`. `CLI/app/` is the Streamlit UI (`Dashboard.py` + `pages/`, including `Pro Features.py`, `Phone Connect.py`, `Email Import.py`). `CLI/app/config.py` holds a `BACKEND_MODE` toggle and the hardcoded Cloud Run URLs the client calls. `CLI/app/streamlit_setup.py` wires session state + sync helpers.

2. **`backend`** (Cloud Run `expense-backend`): FastAPI AI/analytics. `server.py` defines endpoints; `analytics.py` (math), `ai.py` (LLM via Groq/OpenRouter), `bots.py` (CrewAI categorization crew), `ocr.py` (Google Vision). Pro/Max endpoints depend on `require_pro` / `require_max`, which decode the license JWT **statelessly** (no DB lookup) and then enforce per-key IP limits via `ip_limits.py` → Firestore `license_ips` (Pro 3 / Max 6 distinct IPs; fails open if Firestore is unreachable). `/admin/reset-activations` (header `X-Admin-Secret` = `ADMIN_RESET_SECRET`) clears a key's IPs.

3. **`auth-service`** (Cloud Run `auth-service`): mints/records/emails license keys. `jwt_utils.py` builds the HS256 JWT carrying `sub`/`tier`/`features`/`jti`/`max_ips`/`exp`; `TIER_FEATURES` + `TIER_IP_LIMITS` define the tiers. `_issue_license()` in `main.py` is the single mint+record+email path, used by both `/issue` (manual/trusted, requires `X-Issue-Secret`) and `/redeem` (public, auto-issue). Records go to Firestore collection `licenses` with **doc id = order_id** (or the tx hash) so `create()` gives atomic, cross-instance idempotency. Email is **best-effort** (never 500s issuance) via `EMAIL_PROVIDER` = `smtp` (Gmail `SMTP_USER`/`SMTP_PASS`) or `resend`; the full token is stored so a key can be re-sent from the ledger.

**Cross-service contract:** both services read `JWT_SECRET` from Secret Manager and must use the **same value** — auth-service signs, backend verifies. If they diverge, every key fails verification.

**Automatic crypto issuance:** `auth-service/onchain.py` verifies a Base USDC payment from a tx hash via a **public Base RPC** (`https://mainnet.base.org`, no API key) — checks it's a confirmed USDC transfer to the store wallet ≥ the tier price. `/redeem` runs this, then `_issue_license(order_id=tx_hash)`. The web-store buy page (`portfolio/store/web-store`, separate repo) calls `/redeem` for Pro/Max tiers; other products keep a manual flow. `onchain.py` constants (wallet, accepted USDC contracts, min confirmations) are env-overridable.

## Notable gotchas

- **Two unrelated "license" concepts:** the app only accepts auth-service **JWTs**. The web-store's Cloudflare Worker `GRID-XXXXX` keys (and the separate `$34` "expense-tracker" repo-access product) are a different system the app does **not** understand — don't conflate them.
- `python-jose` provides the importable `jose` package, but a stale conflicting `jose` may sit in the local `.venv`; don't rely on it for ad-hoc JWT scripts (compute HS256 with stdlib `hmac` instead).
- `.gitignore` excludes `*.json`, `*.md`, `*.csv`, `*.pdf`, `.env` — `README.md` is force-tracked; `configs.toml` and `*.env.example` are committed templates (keep them empty of real values).
- Several backend endpoints (`/query`, `/recommend-budgets`, `/parse-receipt`) are currently **unauthenticated and unrated** (`slowapi` is a dependency but not wired up) — a known cost-abuse gap; gating them is a pending product decision.
- `published/app.py` is a standalone single-file Streamlit app for Streamlit Community Cloud; it imports `CLI.core.core_stuff` from the repo root and calls the same Cloud Run services. Each session uses an ephemeral tempfile, so its data does not persist.
