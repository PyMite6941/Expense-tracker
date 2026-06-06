import logging
import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

log = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
if SECRET_KEY == "change-me-in-production":
    log.warning(
        "JWT_SECRET is using the insecure default. "
        "Set JWT_SECRET in your environment before deploying."
    )
ALGORITHM = "HS256"

TIER_FEATURES = {
    "pro": [
        "advanced_categorization",
        "anomaly_detection",
        "budget_forecasting",
        "receipt_ocr",
        "monthly_report",
    ],
    "max": [
        "advanced_categorization",
        "anomaly_detection",
        "budget_forecasting",
        "receipt_ocr",
        "monthly_report",
        "deep_analysis",
        "multi_project",
        "export_premium",
        "priority_support",
        "net_worth",
    ],
}

TIER_EXPIRY_DAYS = {
    "pro": 31,
    "max": 31,
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
        "iat": now,
        "exp": now + timedelta(days=TIER_EXPIRY_DAYS[tier]),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_license_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
