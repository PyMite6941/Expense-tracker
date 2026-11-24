"""Entrypoint for the PUBLIC deployment (Streamlit Community Cloud).

Community Cloud looks for `streamlit_app.py` at the repo root by default, so
deploying the repo needs no settings at all. This runs the full app
(CLI/app/main.py) with one difference: storage defaults to "session", a
private temp file per browser session. Without that, every visitor would read
and write the same data.json on the server.

Configuration comes from the host's Secrets panel (see
.streamlit/secrets.toml.example). A secret or environment variable named
STORAGE_MODE overrides the default here, e.g. "hosted" once a Neon database
and sign-in are configured.

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
os.environ.setdefault("STORAGE_MODE", "session")

runpy.run_path(os.path.join(ROOT, "CLI", "app", "main.py"), run_name="__main__")
