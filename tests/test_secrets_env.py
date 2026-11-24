"""CLI/app/secrets_env.py: Streamlit secrets → environment variables."""
import os

import streamlit

from CLI.app import secrets_env


def _run(monkeypatch, secrets):
    monkeypatch.setattr(secrets_env, "_done", False)
    monkeypatch.setattr(streamlit, "secrets", secrets, raising=False)
    return secrets_env.load_streamlit_secrets()


def test_copies_top_level_scalars_only(monkeypatch):
    monkeypatch.delenv("FK_TEST_MODE", raising=False)
    monkeypatch.delenv("FK_TEST_NUM", raising=False)
    applied = _run(monkeypatch, {"FK_TEST_MODE": "session", "FK_TEST_NUM": 3,
                                 "auth": {"client_id": "x"}})
    assert sorted(applied) == ["FK_TEST_MODE", "FK_TEST_NUM"]
    assert os.environ["FK_TEST_MODE"] == "session" and os.environ["FK_TEST_NUM"] == "3"
    assert "auth" not in os.environ


def test_real_env_var_wins(monkeypatch):
    monkeypatch.setenv("FK_TEST_MODE", "hosted")
    assert _run(monkeypatch, {"FK_TEST_MODE": "session"}) == []
    assert os.environ["FK_TEST_MODE"] == "hosted"


def test_no_secrets_file_is_a_no_op(monkeypatch):
    class Missing:
        def __iter__(self):
            raise FileNotFoundError("no secrets.toml")
        def keys(self):
            raise FileNotFoundError("no secrets.toml")
    assert _run(monkeypatch, Missing()) == []
