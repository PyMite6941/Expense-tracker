"""Expose Streamlit secrets as environment variables.

The app reads its configuration from the environment (STORAGE_MODE,
ET_DATABASE_URL, BACKEND_URL, ...) so the same code runs locally, in Docker and
on any host. Streamlit Community Cloud keeps configuration in its Secrets panel
(st.secrets) instead. This copies top-level string/number secrets into
os.environ so both work, without the rest of the code knowing which host it is
on.

Rules:
  * A real environment variable always wins — a secret never overrides it.
  * Only top-level scalars are copied. Sections such as [auth] (st.login's
    OIDC config) stay in st.secrets, where Streamlit reads them itself.
  * No secrets file is fine (local runs): this silently does nothing.
"""
from __future__ import annotations

import os

_done = False


def load_streamlit_secrets() -> list[str]:
    """Copy top-level Streamlit secrets into os.environ. Returns the names set."""
    global _done
    if _done:
        return []
    _done = True
    try:
        import streamlit as st
        items = dict(st.secrets)          # raises if there is no secrets file
    except Exception:
        return []
    applied = []
    for name, value in items.items():
        if isinstance(value, (str, int, float, bool)) and name not in os.environ:
            os.environ[name] = str(value)
            applied.append(name)
    return applied
