import hashlib
import hmac
import os
import smtplib
import sqlite3
from datetime import datetime
from email.message import EmailMessage

from fastapi import FastAPI, Header, HTTPException, Request
from jwt_utils import create_license_jwt, verify_license_jwt

app = FastAPI(title="Expense Tracker License Service")

DB = "licenses.db"
POLAR_WEBHOOK_SECRET = os.getenv("POLAR_WEBHOOK_SECRET", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

# Map Polar.sh product names/prices to tiers.
# Update these after you create products on Polar.sh.
PRICE_TO_TIER = {
    "9":  "pro",
    "9.00": "pro",
    "19": "max",
    "19.00": "max",
}


def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT NOT NULL,
                order_id    TEXT UNIQUE,
                tier        TEXT NOT NULL DEFAULT 'pro',
                token       TEXT NOT NULL,
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


@app.post("/webhook/polar")
async def polar_webhook(request: Request, x_polar_signature: str = Header(None)):
    body = await request.body()

    if POLAR_WEBHOOK_SECRET:
        expected = hmac.new(
            POLAR_WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(f"sha256={expected}", x_polar_signature or ""):
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event_type = payload.get("type", "")
    if event_type not in ("order.completed", "subscription.active"):
        return {"status": "ignored"}

    data = payload.get("data", {})
    email = (data.get("customer") or {}).get("email") or data.get("email")
    order_id = str(data.get("id", ""))

    # Determine tier from the order amount
    amount = str(data.get("amount", data.get("total_amount", "9"))).replace(".0", "")
    tier = PRICE_TO_TIER.get(amount, "pro")

    if not email:
        raise HTTPException(status_code=400, detail="No customer email in webhook payload")

    token = create_license_jwt(email, tier=tier)

    with sqlite3.connect(DB) as conn:
        try:
            conn.execute(
                "INSERT INTO licenses (email, order_id, tier, token, issued_at) VALUES (?,?,?,?,?)",
                (email, order_id, tier, token, datetime.utcnow().isoformat()),
            )
        except sqlite3.IntegrityError:
            pass  # duplicate order

    _send_license_email(email, token, tier)
    return {"status": "ok"}


@app.post("/validate")
async def validate_token(request: Request):
    body = await request.json()
    token = body.get("token", "")
    claims = verify_license_jwt(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid or expired license key")
    return {"valid": True, "email": claims["sub"], "tier": claims["tier"], "features": claims["features"]}


def _send_license_email(to_email: str, token: str, tier: str = "pro"):
    tier_label = "Max (Lifetime)" if tier == "max" else "Pro (1 Year)"
    if not SMTP_USER:
        print(f"[LICENSE] {tier_label} key issued for {to_email}:\n{token}")
        return

    msg = EmailMessage()
    msg["Subject"] = f"Your GRID {tier_label} License Key"
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg.set_content(
        f"""\
Thank you for purchasing GRID {tier_label}!

Your license key:

{token}

Paste this into the "Pro Features" page in the app to activate.

{"Lifetime access — this key never expires." if tier == "max" else "Valid for 1 year from today."}

Questions? Reply to this email.
"""
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
