"""
Issue a license key manually — use this when a crypto buyer emails their tx hash.

Usage:
  python gen_code.py <email> <tier>

Examples:
  python gen_code.py buyer@example.com pro
  python gen_code.py buyer@example.com max
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

if len(sys.argv) != 3:
    print(__doc__)
    sys.exit(1)

email = sys.argv[1]
tier  = sys.argv[2].lower()

if tier not in ("pro", "max"):
    print(f"Error: tier must be 'pro' or 'max', got '{tier}'")
    sys.exit(1)

from jwt_utils import create_license_jwt, TIER_FEATURES, TIER_EXPIRY_DAYS

token = create_license_jwt(email, tier=tier)

print(f"\n{'='*60}")
print(f"  Tier    : {tier.upper()}")
print(f"  Email   : {email}")
print(f"  Expiry  : {'Lifetime' if tier == 'max' else '1 year'}")
print(f"  Features: {', '.join(TIER_FEATURES[tier])}")
print(f"{'='*60}")
print(f"\n{token}\n")
print("Send the token above to the buyer.\n")
