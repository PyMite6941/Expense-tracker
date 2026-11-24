"""Entrypoint for the PUBLIC deployment (Streamlit Community Cloud).

Community Cloud looks for `streamlit_app.py` at the repo root by default, so
deploying the repo needs no settings at all. This runs the full app
(CLI/app/main.py) with one difference: storage defaults to "session", a
private temp file per browser session. Without that, every visitor would read
and write the same data.json on the server.

Configuration comes from the host's Secrets panel (see
.streamlit/secrets.toml.example). A secret or environment variable named
STORAGE_MODE overrides the default. With no override, the mode switches to
"hosted" by itself once ET_DATABASE_URL and an [auth] section are both set:
visitors with a paid hosted entitlement get a saved cloud workspace, everyone
else keeps the free not-saved demo.

Run locally exactly as hosted:   streamlit run streamlit_app.py
Run the normal self-hosted app:  streamlit run CLI/app/main.py
"""
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from CLI.app.secrets_env import load_streamlit_secrets  # noqa: E402

load_streamlit_secrets()                     # secrets first, so they win


def _hosting_configured() -> bool:
    """Paid hosting needs a database AND sign-in. Until both exist, the public
    site is a free demo that keeps nothing (the free plan is self-hosting)."""
    if not (os.getenv("ET_DATABASE_URL") or os.getenv("DATABASE_URL")):
        return False
    try:
        import streamlit as st
        return "auth" in st.secrets
    except Exception:
        return False


os.environ.setdefault("STORAGE_MODE", "hosted" if _hosting_configured() else "session")

runpy.run_path(os.path.join(ROOT, "CLI", "app", "main.py"), run_name="__main__")
