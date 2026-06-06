import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"

TIER_FEATURES = {
    # Pro — Expense Tracker only. AI runs server-side (CrewAI, OCR, forecasting).
    "pro": [
        "advanced_categorization",   # CrewAI 3-agent crew
        "anomaly_detection",         # IsolationForest outlier flagging
        "budget_forecasting",        # LinearRegression next-month prediction
        "receipt_ocr",               # Google Cloud Vision receipt parsing
        "monthly_report",            # AI-generated PDF spending report
    ],
    # Max — heavier compute across multiple projects. Justifies higher hosting cost.
    "max": [
        "advanced_categorization",
        "anomaly_detection",
        "budget_forecasting",
        "receipt_ocr",
        "monthly_report",
        "deep_analysis",             # DeepSeek R1 full model — more tokens, slower, expensive
        "multi_project",             # reserved — not active yet
        "export_premium",            # PDF/CSV with AI commentary per category
        "priority_support",
    ],
}

TIER_EXPIRY_DAYS = {
    "pro": 31,   # monthly subscription — renew each billing cycle
    "max": 31,   # monthly subscription — renew each billing cycle
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
