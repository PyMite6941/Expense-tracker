# Finance Kit

Personal finance app with a CLI mode and a full Streamlit web UI. Tracks expenses, income, budgets, subscriptions, goals, recurring transactions, assets, and liabilities. AI analytics and net worth run server-side on Google Cloud Run.

**License:** All Rights Reserved © 2026 PyMite6941 — view/personal use only. See license section below.

---

## Versions

| Version | Date | Notes |
|---------|------|-------|
| v1.6 | September 2026 | **Accounts** — checking / savings / online savings / MMA / CD / credit card, each with the fields that type actually has; expenses and income charge to an account and balances are derived from them. **Privacy** — the pure-maths analytics (forecast, anomalies, net worth) now run on your machine instead of being POSTed to Cloud Run; only the AI query still transmits, and only when you press Ask. **Encryption** — TLS enforced on every connection, hosted rows encrypted at rest (AES-256-GCM), stored credentials encrypted. **Auth** — secrets fail closed, `/issue` no longer public when `ISSUE_SECRET` is unset, `X-Forwarded-For` read from the right so the device cap is enforceable, licence keys no longer written to logs, python-jose replaced with PyJWT. Renamed from GRID to Finance Kit; `st.navigation` router with real URLs; React (`web/`) client |
| v1.5 | June 2026 | Keyless Cloud Run deploys via Workload Identity Federation; deploy targets `expense-backend`; docs consolidated into a single README |
| v1.4 | June 2026 | Phone Connect (Pro) and Email Import (Max); single-file `published/` Streamlit app for cloud deployment |
| v1.3 | June 2026 | Security fixes (input caps, IntegrityError handling, CSV ID assignment, float safety); crypto payment code removed |
| v1.2 | April 10 2026 | Improved logic from v1.1; assets & liabilities; net worth (Max tier); config.py for cloud/local toggle |
| v1.1 | April 2 2026 | Expenses, income, budget, goals, subscriptions |

---

## Architecture

```
run.py                      — entry point (prompts CLI or Web UI)
CLI/
  app/
    config.py               — BACKEND_MODE toggle ("cloud" or "local")
    streamlit_setup.py      — session state init, sync helpers, backend URL wiring
    main.py                 — ENTRYPOINT: st.navigation router; declares every page + its URL
    theme.py                — shared look, top navbar, sidebar (single source of styling)
    Dashboard.py            — Overview page (/overview)
    pages/
      Monthly Summary.py    — /monthly
      Recurring Expenses.py — /recurring
      Pro Features.py       — /pro   license activation + AI analytics
      Email Import.py       — /import
      Phone Connect.py      — /phone
      Settings.py           — /settings  account, storage mode, export/backup
  core/
    core_stuff.py           — all data CRUD; reads/writes data.json
backend/
  server.py                 — FastAPI server deployed on Cloud Run
  analytics.py              — forecast, anomaly, net worth, tax, health score, etc.
  ai.py                     — NL query, category suggestion, budget recommendations
  bots.py                   — CrewAI advanced categorization crew (Pro/Max)
  ocr.py                    — Google Cloud Vision receipt parser
  Dockerfile                — Cloud Run container
auth-service/
  main.py                   — FastAPI license service (issue, validate)
  jwt_utils.py              — HS256 JWT creation and verification
  gen_code.py               — CLI tool to issue license keys after verifying payment
  Dockerfile
data.json                   — local data store (expenses, income, budget, etc.)
```

---

## Setup

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac / Linux
source .venv/bin/activate

pip install -r requirements.txt
python run.py
```

Or launch the web UI directly:

```bash
streamlit run CLI/app/main.py
```

---

## Backend Mode

`CLI/app/config.py` controls which backend is used:

```python
BACKEND_MODE = "cloud"   # uses Google Cloud Run (default)
# BACKEND_MODE = "local" # uses http://localhost:8000 and http://localhost:8001
```

Cloud Run URLs:
- Analytics backend: `https://expense-backend-690527435721.us-central1.run.app`
- Auth service: `https://auth-service-690527435721.us-central1.run.app`

To run locally:

```bash
# terminal 1 — analytics backend
cd backend && uvicorn server:app --port 8000

# terminal 2 — auth service
cd auth-service && uvicorn main:app --port 8001
```

---

## Pro & Max Tiers

License keys are 31-day HS256 JWTs. Activate on the **Pro Features** page in the web UI.

| Feature | Free | Pro ($9/mo) | Max ($20/mo) |
|---------|------|-------------|--------------|
| Expense / income / budget CRUD | ✓ | ✓ | ✓ |
| Charts, monthly summaries, CSV/PDF export | ✓ | ✓ | ✓ |
| Budget utilisation, savings rate, health score | ✓ | ✓ | ✓ |
| Goal progress & renewal alerts | ✓ | ✓ | ✓ |
| Tax summary | ✓ | ✓ | ✓ |
| Spending forecast | — | ✓ | ✓ |
| Anomaly detection | — | ✓ | ✓ |
| NL financial queries | — | ✓ | ✓ |
| AI budget recommendations | — | ✓ | ✓ |
| Advanced AI categorization (CrewAI) | — | ✓ | ✓ |
| Receipt OCR | — | ✓ | ✓ |
| Smart budget advisor | — | ✓ | ✓ |
| Expense narrative | — | ✓ | ✓ |
| Cash-flow forecast | — | ✓ | ✓ |
| Phone Connect (Telegram / Discord bots) | — | ✓ | ✓ |
| Net Worth tracking (assets & liabilities) | — | — | ✓ |
| Debt elimination planner | — | — | ✓ |
| Investment readiness check | — | — | ✓ |
| Financial goal coach | — | — | ✓ |
| Spending DNA analysis | — | — | ✓ |
| Email Import (inbox receipt parsing) | — | — | ✓ |
| Premium PDF/CSV export | — | — | ✓ |
| Priority support | — | — | ✓ |

Max is a strict superset of Pro — all Pro features work with a Max key.

**What "Free" means here:** the whole local app — every CRUD operation, all
charts and exports, and the pure-maths analytics — runs offline against
`data.json` with no key and no account. The paid tiers cover the features that
cost money to run: anything calling an LLM, the Vision OCR API, or the CrewAI
agents. Those are metered per-key and rate-limited server-side.

Payment is USDC on Base network via the store at [grid-store.pages.dev](https://grid-store.pages.dev). After payment, email the tx hash to `greshamd27@gmail.com` with subject `USDC Sub — Pro` or `USDC Sub — Max`. License key arrives by email within a few hours.

To issue a key manually (after verifying payment):

```bash
cd auth-service
python gen_code.py <email> <pro|max>
```

---

## Environment Variables

### Backend (`backend/`)

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | **Required.** HS256 verification secret; must be byte-identical to auth-service. The service **refuses to start** without a real one (see below) |
| `AI_API_KEY` | API key for NL query / budget recommendations |
| `AI_PROVIDER` | `groq` or `openrouter` (default: `groq`) |
| `AI_MODEL` | Model override (default: provider default) |
| `GROQ_API_KEY` | Groq key for CrewAI fallback in bots.py |
| `OPENROUTER_API_KEY` | OpenRouter key (preferred over Groq in bots.py) |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account JSON path (for OCR). Leave unset on Cloud Run |
| `ADMIN_RESET_SECRET` | Shared secret for `/admin/reset-activations`. Unset = endpoint disabled (503) |
| `TRUSTED_PROXY_HOPS` | Trusted proxies in front of Cloud Run (default `0`). See below |
| `IP_LIMIT_FAIL_OPEN` | `true` (default) allows requests when Firestore is unreachable |

`backend/.env.example` is the committed template listing all of these.

### Auth service (`auth-service/`)

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | **Required.** HS256 signing secret; must match backend. Service **refuses to start** without a real one |
| `ISSUE_SECRET` | **Required for `/issue`.** Expected `X-Issue-Secret` header value. Unset = `/issue` returns 503 and mints nothing |
| `RESEND_API_KEY` | Resend API key for license emails |
| `EMAIL_PROVIDER` | `resend` (default) or `smtp` |
| `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` | Email transport settings |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `LICENSE_COLLECTION` | Firestore collection for the license ledger (default: `licenses`) |
| `TRUSTED_PROXY_HOPS` | Trusted proxies in front of Cloud Run (default `0`) |

All secrets are stored in GCP Secret Manager. Project details are kept out of this repo.
`auth-service/.env.example` is the committed template.

> The license ledger lives in **Firestore**, not SQLite — Cloud Run filesystems
> are ephemeral, so a local DB would lose every issued key on restart.

### Secrets fail closed

Both services validate `JWT_SECRET` at startup and **raise rather than boot** if it
is missing, under 32 characters, or a known placeholder. It previously defaulted
to `change-me-in-production` with only a log warning — which, in a public repo,
meant a missing Secret Manager binding produced a service that looked healthy and
honoured licences anyone could forge. A missing secret is now a visible crash, by
design. For local development only, `ALLOW_INSECURE_JWT_SECRET=1` bypasses the
check; never set it on a deployed service.

Generate a secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`X-Forwarded-For` is read from the **right-hand** side in both services, because
a caller can send their own header and Google appends to it — the leftmost entry
is attacker-controlled. `TRUSTED_PROXY_HOPS` (default `0`, correct for a direct
`*.run.app` URL) shifts which entry is trusted; raise it only when you put a
custom load balancer or Cloudflare in front. Setting it too high lets callers
spoof their IP, evade rate limits, and share one licence across unlimited devices.

---

## API Endpoints

### Analytics backend

Every endpoint is rate-limited on the real client IP. Endpoints marked **Pro** or
**Max** require `Authorization: Bearer <license JWT>`; they also enforce the
per-key device/IP activation cap (Pro 3, Max 6).

Pure-maths endpoints are public because they cost nothing to serve. Everything
that calls an LLM, Google Vision, or CrewAI is gated — that is what the tiers pay for.

| Method | Path | Auth | Limit | Description |
|--------|------|------|-------|-------------|
| GET | `/health` | — | 120/min | Health check |
| POST | `/tax-summary` | — | 30/min | Year-level tax summary |
| POST | `/health-score` | — | 30/min | 0–100 financial health score |
| POST | `/spending-by-category` | — | 60/min | Category breakdown |
| POST | `/monthly-totals` | — | 60/min | Month-by-month totals |
| POST | `/savings-rate` | — | 60/min | Monthly savings rate history |
| POST | `/budget-utilization` | — | 60/min | Per-category budget usage |
| POST | `/income-vs-expenses` | — | 60/min | Monthly income vs expenses |
| POST | `/monthly-comparison` | — | 60/min | Two-month category diff |
| POST | `/upcoming-renewals` | — | 60/min | Subscriptions renewing soon |
| POST | `/goal-progress` | — | 60/min | Goal ETA and % complete |
| POST | `/forecast` | **Pro** | 20/min | Spending forecast by category |
| POST | `/detect-anomalies` | **Pro** | 20/min | Z-score anomaly detection |
| POST | `/query` | **Pro** | 10/min | NL financial query (AI) |
| POST | `/recommend-budgets` | **Pro** | 10/min | AI budget suggestions |
| POST | `/parse-receipt` | **Pro** | 5/min | OCR receipt image (Google Vision) |
| POST | `/advanced-categorize` | **Pro** | 5/min | CrewAI categorization crew |
| POST | `/smart-budget-advisor` | **Pro** | 10/min | AI budget advisor |
| POST | `/expense-narrative` | **Pro** | 10/min | Plain-English spending narrative |
| POST | `/cash-flow-forecast` | **Pro** | 10/min | AI cash-flow projection |
| POST | `/net-worth` | **Max** | 20/min | Net worth snapshot |
| POST | `/debt-planner` | **Max** | 10/min | Debt elimination plan |
| POST | `/investment-readiness` | **Max** | 10/min | Investment readiness check |
| POST | `/financial-coach` | **Max** | 10/min | Financial goal coaching |
| POST | `/spending-dna` | **Max** | 10/min | Spending personality analysis |
| POST | `/admin/reset-activations` | `X-Admin-Secret` | 5/min | Clear a key's registered IPs |

### Auth service

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Health check |
| POST | `/issue` | `X-Issue-Secret` header | Issue a 31-day license key (trusted/manual path). Returns 503 if `ISSUE_SECRET` is unset |
| POST | `/redeem` | — (payment is the proof) | Verify a Base USDC tx hash on-chain, then auto-issue. The tx hash is the `order_id`, so one payment redeems exactly once |
| POST | `/validate` | — | Validate a JWT and return claims |

---

## Data File

`data.json` stores all local data. Fields seeded on first run:

```json
{
  "expenses": [],
  "income": [],
  "budget": [],
  "subscriptions": [],
  "goals": [],
  "recurring_expenses": [],
  "recurring_income": [],
  "assets": [],
  "liabilities": []
}
```

Asset fields: `id`, `name`, `type` (liquid/investment/real_estate/vehicle/other), `value`, `currency`, `notes`

Liability fields: `id`, `name`, `type` (mortgage/student_loan/car_loan/credit_card/personal_loan/other), `balance`, `currency`, `interest_rate`, `notes`

---

## License

Copyright © 2026 PyMite6941. All Rights Reserved.

You **may**: view this code for learning purposes, run the program for personal use, draw on the general concepts to write your own implementation from scratch.

You **may not**: copy, reproduce, or use this code in other projects; modify or create derivative works; distribute or republish this code; use this code for commercial purposes.

Any other use requires explicit written permission from PyMite6941.
