import os
import re
import sqlite3
from datetime import datetime

import resend
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from jwt_utils import create_license_jwt, verify_license_jwt

resend.api_key = os.getenv("RESEND_API_KEY", "")

ISSUE_SECRET = os.getenv("ISSUE_SECRET", "")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8501,http://127.0.0.1:8501,https://grid-store.pages.dev",
).split(",")

app = FastAPI(title="Expense Tracker License Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "Authorization", "X-Issue-Secret"],
)

DB = os.getenv("LICENSE_DB", "licenses.db")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email)) and len(email) <= 254


def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT NOT NULL,
                order_id    TEXT UNIQUE,
                tier        TEXT NOT NULL DEFAULT 'pro',
                issued_at   TEXT NOT NULL
            )
            """
        )


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Issue license (called by the store after payment is verified externally) ──

@app.post("/issue")
async def issue(request: Request):
    """
    Issue a license key. Requires X-Issue-Secret header to prevent abuse.
    Call this after independently verifying payment (e.g. from gen_code.py).
    """
    if ISSUE_SECRET and request.headers.get("X-Issue-Secret") != ISSUE_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Issue-Secret header")

    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    tier = (body.get("tier") or "pro").strip().lower()
    order_id = (body.get("order_id") or "").strip()

    if not _valid_email(email):
        raise HTTPException(status_code=400, detail="Valid email required")
    if tier not in ("pro", "max"):
        raise HTTPException(status_code=400, detail="tier must be 'pro' or 'max'")
    if not order_id:
        raise HTTPException(status_code=400, detail="order_id required")

    # Idempotency — same order_id returns the same token
    with sqlite3.connect(DB) as conn:
        row = conn.execute(
            "SELECT id FROM licenses WHERE order_id = ?", (order_id,)
        ).fetchone()
    if row:
        raise HTTPException(
            status_code=409,
            detail="A license has already been issued for this order",
        )

    token = create_license_jwt(email, tier=tier)

    with sqlite3.connect(DB) as conn:
        conn.execute(
            "INSERT INTO licenses (email, order_id, tier, issued_at) VALUES (?,?,?,?)",
            (email, order_id, tier, datetime.utcnow().isoformat()),
        )

    _send_license_email(email, token, tier)
    return {"token": token, "email": email, "tier": tier}


def _send_license_email(to_email: str, token: str, tier: str):
    if not resend.api_key:
        print(f"[LICENSE] {tier.upper()} key for {to_email}:\n{token}")
        return
    tier_label = "Max" if tier == "max" else "Pro"
    resend.Emails.send({
        "from": "GRID <licenses@resend.dev>",
        "to": to_email,
        "subject": f"Your GRID {tier_label} License Key",
        "html": f"""
<p>Thanks for subscribing to GRID {tier_label}!</p>
<p><strong>Your 31-day license key:</strong></p>
<pre style="background:#111;padding:16px;border-radius:8px;font-size:13px;word-break:break-all">{token}</pre>
<p>Paste it into the <strong>Pro Features</strong> page in the Expense Tracker app to activate.</p>
<p style="color:#888;font-size:12px">Key expires in 31 days. Renew by placing a new order.</p>
""",
    })


# ── Validate endpoint (used by the Streamlit app) ────────────────────────────

@app.post("/validate")
async def validate_token(request: Request):
    body = await request.json()
    token = body.get("token", "")
    claims = verify_license_jwt(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid or expired license key")
    return {
        "valid": True,
        "email": claims["sub"],
        "tier": claims["tier"],
        "features": claims["features"],
    }
