# GRID — Expense Tracker

Personal finance app with a CLI mode and a full Streamlit web UI. Tracks expenses, income, budgets, subscriptions, goals, recurring transactions, assets, and liabilities. AI analytics and net worth run server-side on Google Cloud Run.

**License:** All Rights Reserved © 2026 PyMite6941 — view/personal use only. See license section below.

---

## Versions

| Version | Date | Notes |
|---------|------|-------|
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
    Dashboard.py            — Streamlit main page (all tabs)
    pages/
      Pro Features.py       — license activation + AI analytics page
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
streamlit run CLI/app/Dashboard.py
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
| Spending forecast | ✓ | ✓ | ✓ |
| Anomaly detection | ✓ | ✓ | ✓ |
| Tax summary | ✓ | ✓ | ✓ |
| NL financial queries | ✓ | ✓ | ✓ |
| Advanced AI categorization (CrewAI) | — | ✓ | ✓ |
| Budget forecasting | — | ✓ | ✓ |
| Receipt OCR | — | ✓ | ✓ |
| Monthly AI report | — | ✓ | ✓ |
| Net Worth tracking (assets & liabilities) | — | — | ✓ |
| Deep analysis (DeepSeek R1) | — | — | ✓ |
| Premium PDF/CSV export | — | — | ✓ |
| Priority support | — | — | ✓ |

Max is a strict superset of Pro — all Pro features work with a Max key.

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
| `JWT_SECRET` | HS256 signing secret (must match auth-service) |
| `AI_API_KEY` | API key for NL query / budget recommendations |
| `AI_PROVIDER` | `groq` or `openrouter` (default: `groq`) |
| `AI_MODEL` | Model override (default: provider default) |
| `GROQ_API_KEY` | Groq key for CrewAI fallback in bots.py |
| `OPENROUTER_API_KEY` | OpenRouter key (preferred over Groq in bots.py) |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account JSON path (for OCR) |

### Auth service (`auth-service/`)

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | HS256 signing secret (must match backend) |
| `RESEND_API_KEY` | Resend API key for license emails |
| `ISSUE_SECRET` | Required header value for `/issue` endpoint |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `LICENSE_DB` | Path to SQLite DB (default: `licenses.db`) |

All secrets are stored in GCP Secret Manager in project `fair-geography-493716-q4`.

---

## API Endpoints

### Analytics backend

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Health check |
| POST | `/forecast` | — | Spending forecast by category |
| POST | `/detect-anomalies` | — | Z-score anomaly detection |
| POST | `/tax-summary` | — | Year-level tax summary |
| POST | `/health-score` | — | 0–100 financial health score |
| POST | `/spending-by-category` | — | Category breakdown |
| POST | `/monthly-totals` | — | Month-by-month totals |
| POST | `/savings-rate` | — | Monthly savings rate history |
| POST | `/budget-utilization` | — | Per-category budget usage |
| POST | `/income-vs-expenses` | — | Monthly income vs expenses |
| POST | `/monthly-comparison` | — | Two-month category diff |
| POST | `/upcoming-renewals` | — | Subscriptions renewing soon |
| POST | `/goal-progress` | — | Goal ETA and % complete |
| POST | `/query` | — | NL financial query (AI) |
| POST | `/recommend-budgets` | — | AI budget suggestions |
| POST | `/parse-receipt` | — | OCR receipt image |
| POST | `/net-worth` | Max JWT | Net worth snapshot |
| POST | `/advanced-categorize` | Pro/Max JWT | CrewAI categorization crew |

### Auth service

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Health check |
| POST | `/issue` | `X-Issue-Secret` header | Issue a 31-day license key |
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
