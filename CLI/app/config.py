# Backend mode — "cloud" uses Google Cloud Run (default), "local" runs the backend on this machine
BACKEND_MODE = "cloud"

CLOUD_BACKEND_URL  = "https://expense-backend-690527435721.us-central1.run.app"
CLOUD_AUTH_URL     = "https://auth-service-690527435721.us-central1.run.app"

LOCAL_BACKEND_URL  = "http://localhost:8000"
LOCAL_AUTH_URL     = "http://localhost:8001"

# ---------------------------------------------------------------------------
# Storage mode — where the user's finance data lives.
#
#   "local"  (default) : data.json on this machine. The FREE, self-hosted mode.
#                        No account, no database, works offline.
#   "hosted"           : multi-tenant Neon Postgres, one organization per
#                        customer. The PAID mode Matt runs for enterprises.
#                        Requires ET_DATABASE_URL and a signed-in user holding
#                        an entitlement purchased through the GRID store.
#
# Set STORAGE_MODE=hosted in the environment on the servers Matt hosts; leave it
# alone for self-hosted installs.
# ---------------------------------------------------------------------------
import os

STORAGE_MODE = os.getenv("STORAGE_MODE", "local").strip().lower()
HOSTED_MODE  = STORAGE_MODE == "hosted"

# Neon connection string. Never hardcode it — read from the environment.
DATABASE_URL = os.getenv("ET_DATABASE_URL") or os.getenv("DATABASE_URL")

# ---------------------------------------------------------------------------
# Where to send someone who hits a paywall.
#
# Defined ONCE here because every gate in the app needs it. They used to be
# scattered string literals, and most gates had no link at all — the app told
# people a feature was locked without telling them where to unlock it.
#
# STORE_URL         the shop front (hosted access, all products)
# LICENSE_STORE_URL the Pro/Max licence-key page — runs the Base-USDC redeem
#                   flow and hands back the JWT you paste into Pro Features
# ---------------------------------------------------------------------------
STORE_URL = os.getenv("GRID_STORE_URL", "https://grid-store.pages.dev")
LICENSE_STORE_URL = os.getenv("GRID_LICENSE_URL", f"{STORE_URL}/codes")
