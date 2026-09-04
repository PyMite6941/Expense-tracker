import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

log = logging.getLogger(__name__)

ALGORITHM = "HS256"

# Secrets that must never sign a real license. The repo is public, so anything
# committed here is public too — a service that silently fell back to one of
# these would mint keys any reader of the repo could forge.
_KNOWN_BAD_SECRETS = {
    "change-me-in-production",
    "replace-with-a-long-random-string",
    "secret",
    "changeme",
}
_MIN_SECRET_LEN = 32


def _load_signing_secret() -> str:
    """Return the HS256 signing secret, or refuse to start.

    Fails CLOSED. This used to default to "change-me-in-production" and only
    log a warning, so a missing Secret Manager binding produced a service that
    booted healthy and accepted licenses forged with a secret published in this
    repo. Set ALLOW_INSECURE_JWT_SECRET=1 to bypass for local development only.
    """
    secret = (os.getenv("JWT_SECRET") or "").strip()
    dev_ok = os.getenv("ALLOW_INSECURE_JWT_SECRET", "").lower() in ("1", "true", "yes")

    if not secret:
        problem = "JWT_SECRET is not set"
    elif secret.lower() in _KNOWN_BAD_SECRETS:
        problem = "JWT_SECRET is a well-known placeholder value"
    elif len(secret) < _MIN_SECRET_LEN:
        problem = f"JWT_SECRET is shorter than {_MIN_SECRET_LEN} characters"
    else:
        return secret

    if dev_ok:
        log.warning("%s — continuing anyway because ALLOW_INSECURE_JWT_SECRET is set. "
                    "NEVER set that flag on a deployed service.", problem)
        return secret or "insecure-development-secret"

    raise RuntimeError(
        f"{problem}. auth-service signs license keys with it, so it refuses to "
        "start without a real one. Set JWT_SECRET (32+ chars, matching the "
        "backend service) or, for local development only, set "
        "ALLOW_INSECURE_JWT_SECRET=1."
    )


SECRET_KEY = _load_signing_secret()

TIER_FEATURES = {
    "pro": [
        "advanced_categorization",
        "anomaly_detection",
        "budget_forecasting",
        "receipt_ocr",
        "monthly_report",
        "bot_connect",
        "smart_budget_advisor",
        "expense_narrative",
        "cash_flow_forecast",
    ],
    "max": [
        "advanced_categorization",
        "anomaly_detection",
        "budget_forecasting",
        "receipt_ocr",
        "monthly_report",
        "bot_connect",
        "smart_budget_advisor",
        "expense_narrative",
        "cash_flow_forecast",
        "deep_analysis",
        "multi_project",
        "export_premium",
        "priority_support",
        "net_worth",
        "email_parsing",
        "debt_planner",
        "investment_readiness",
        "financial_coach",
        "spending_dna",
    ],
}

TIER_EXPIRY_DAYS = {
    "pro": 31,
    "max": 31,
}

# Maximum distinct IPs (devices) a license of each tier may activate on.
# The same IP reconnecting never counts twice — only distinct IPs are capped.
TIER_IP_LIMITS = {
    "pro": 3,
    "max": 6,
}

def create_license_jwt(email: str, tier: str = "pro") -> str:
    tier = tier.lower()
    if tier not in TIER_FEATURES:
        raise ValueError(f"Unknown tier: {tier}")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "features": TIER_FEATURES[tier],
        "tier": tier,
        # jti uniquely identifies this key so the backend can track its IPs;
        # max_ips is the signed, tamper-proof activation cap for the tier.
        "jti": uuid.uuid4().hex,
        "max_ips": TIER_IP_LIMITS[tier],
        "iat": now,
        "exp": now + timedelta(days=TIER_EXPIRY_DAYS[tier]),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_license_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
