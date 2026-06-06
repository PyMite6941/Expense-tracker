import os
import sqlite3
from datetime import datetime

import requests as http
import resend
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from jwt_utils import create_license_jwt, verify_license_jwt

resend.api_key = os.getenv("RESEND_API_KEY", "")

app = FastAPI(title="Expense Tracker License Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB = "licenses.db"

# USDC on Base
USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WALLET = os.getenv("WALLET_ADDRESS", "0x8069408a17B77895cb7Cd0B0D804aB46f59Bc4c3")
BASE_RPC = "https://mainnet.base.org"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

TIER_AMOUNTS = {
    "pro": 9_000_000,   # $9 USDC (6 decimals)
    "max": 20_000_000,  # $20 USDC (6 decimals)
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


# ── On-chain verification ─────────────────────────────────────────────────────

def _rpc(method: str, params: list):
    resp = http.post(BASE_RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    if "error" in result:
        raise ValueError(result["error"]["message"])
    return result["result"]


def _verify_usdc_transfer(tx_hash: str, tier: str) -> bool:
    try:
        receipt = _rpc("eth_getTransactionReceipt", [tx_hash])
        if not receipt or receipt.get("status") != "0x1":
            return False

        expected_amount = TIER_AMOUNTS[tier]
        wallet_padded = "0x000000000000000000000000" + WALLET[2:].lower()

        for log in receipt.get("logs", []):
            if log.get("address", "").lower() != USDC_CONTRACT.lower():
                continue
            topics = log.get("topics", [])
            if len(topics) < 3:
                continue
            if topics[0].lower() != TRANSFER_TOPIC.lower():
                continue
            if topics[2].lower() != wallet_padded.lower():
                continue
            amount = int(log.get("data", "0x0"), 16)
            if amount >= expected_amount:
                return True
        return False
    except Exception:
        return False


# ── Crypto purchase endpoint ──────────────────────────────────────────────────

@app.post("/issue-crypto")
async def issue_crypto(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    tier = (body.get("tier") or "pro").strip().lower()
    tx_hash = (body.get("tx_hash") or "").strip()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    if tier not in ("pro", "max"):
        raise HTTPException(status_code=400, detail="tier must be 'pro' or 'max'")
    if not tx_hash.startswith("0x") or len(tx_hash) < 60:
        raise HTTPException(status_code=400, detail="Invalid tx hash format")

    # Check this tx hasn't already been used
    with sqlite3.connect(DB) as conn:
        row = conn.execute("SELECT id FROM licenses WHERE order_id = ?", (tx_hash,)).fetchone()
    if row:
        raise HTTPException(status_code=409, detail="This transaction has already been used to issue a key")

    if not _verify_usdc_transfer(tx_hash, tier):
        raise HTTPException(
            status_code=402,
            detail=f"Could not verify a ${TIER_AMOUNTS[tier] // 1_000_000} USDC transfer to the payment address. "
                   "Make sure you're on Base network and the transaction is confirmed.",
        )

    token = create_license_jwt(email, tier=tier)

    with sqlite3.connect(DB) as conn:
        conn.execute(
            "INSERT INTO licenses (email, order_id, tier, token, issued_at) VALUES (?,?,?,?,?)",
            (email, tx_hash, tier, token, datetime.utcnow().isoformat()),
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
<p style="color:#888;font-size:12px">Key expires in 31 days. Renew by sending another payment and claiming again.</p>
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
    return {"valid": True, "email": claims["sub"], "tier": claims["tier"], "features": claims["features"]}
