import os
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

import resend
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import firestore
from google.api_core.exceptions import AlreadyExists, GoogleAPIError
from jwt_utils import create_license_jwt, verify_license_jwt

resend.api_key = os.getenv("RESEND_API_KEY", "")

ISSUE_SECRET = os.getenv("ISSUE_SECRET", "")

# Sender for license emails. Override with a verified Resend domain once DNS
# is set up (e.g. "GRID <licenses@yourdomain.com>"). The default resend.dev
# domain only delivers to the Resend account owner.
EMAIL_FROM = os.getenv("EMAIL_FROM", "GRID <licenses@resend.dev>")

# Email transport: "resend" (Resend API) or "smtp" (Gmail / any SMTP server).
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "resend").lower()
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

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

LICENSE_COLLECTION = os.getenv("LICENSE_COLLECTION", "licenses")

_db = None


def _firestore():
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email)) and len(email) <= 254


def _safe_doc_id(order_id: str) -> str:
    # Firestore document IDs cannot contain '/' and must be <= 1500 bytes.
    return order_id.replace("/", "_")[:1500]


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

    token = create_license_jwt(email, tier=tier)
    claims = verify_license_jwt(token) or {}

    record = {
        "email": email,
        "order_id": order_id,
        "tier": tier,
        "jti": claims.get("jti"),
        "max_ips": claims.get("max_ips"),
        "token": token,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }

    # Atomic idempotency: create() fails if a doc already exists for this
    # order_id, so the same order can never mint two keys — even across
    # instances (unlike the old per-instance SQLite check).
    doc_ref = _firestore().collection(LICENSE_COLLECTION).document(_safe_doc_id(order_id))
    try:
        doc_ref.create(record)
    except AlreadyExists:
        raise HTTPException(
            status_code=409,
            detail="A license has already been issued for this order",
        )
    except GoogleAPIError as exc:
        raise HTTPException(status_code=503, detail=f"License store unavailable: {exc}")

    sent = _send_license_email(email, token, tier)
    return {"token": token, "email": email, "tier": tier, "email_sent": sent}


def _license_html(token: str, tier_label: str) -> str:
    return f"""
<p>Thanks for subscribing to GRID {tier_label}!</p>
<p><strong>Your 31-day license key:</strong></p>
<pre style="background:#111;padding:16px;border-radius:8px;font-size:13px;word-break:break-all">{token}</pre>
<p>Paste it into the <strong>Pro Features</strong> page in the Expense Tracker app to activate.</p>
<p style="color:#888;font-size:12px">Key expires in 31 days. Renew by placing a new order.</p>
"""


def _send_license_email(to_email: str, token: str, tier: str) -> bool:
    """Best-effort delivery. Never raises: the key is already recorded in
    Firestore (with the token), so a delivery failure must not 500 the issue
    call — the key can be re-sent from the ledger.

    EMAIL_PROVIDER picks the transport: 'smtp' (Gmail/any SMTP via
    SMTP_USER/SMTP_PASS) or 'resend' (Resend API)."""
    tier_label = "Max" if tier == "max" else "Pro"
    subject = f"Your GRID {tier_label} License Key"
    html = _license_html(token, tier_label)
    text = (f"Your GRID {tier_label} license key (expires in 31 days):\n\n{token}\n\n"
            "Paste it into the Pro Features page in the Expense Tracker app.")
    try:
        if EMAIL_PROVIDER == "smtp":
            if not (SMTP_USER and SMTP_PASS):
                print(f"[LICENSE] SMTP not configured; {tier.upper()} key for {to_email}:\n{token}")
                return False
            msg = EmailMessage()
            msg["From"] = f"GRID <{SMTP_USER}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.set_content(text)
            msg.add_alternative(html, subtype="html")
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
            return True

        # default: Resend API
        if not resend.api_key:
            print(f"[LICENSE] {tier.upper()} key for {to_email}:\n{token}")
            return False
        resend.Emails.send({"from": EMAIL_FROM, "to": to_email,
                            "subject": subject, "html": html})
        return True
    except Exception as exc:
        print(f"[LICENSE] email send failed for {to_email}: {exc}")
        return False


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
