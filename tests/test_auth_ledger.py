"""auth-service/ledger.py: backend selection and the no-ledger refusal."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "auth-service")))
import ledger  # noqa: E402


def test_backend_selection(monkeypatch):
    for k in ("DATABASE_URL", "LEDGER", "K_SERVICE"):
        monkeypatch.delenv(k, raising=False)
    assert ledger.backend_name() == "none"
    monkeypatch.setenv("K_SERVICE", "auth-service")
    assert ledger.backend_name() == "firestore"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    assert ledger.backend_name() == "postgres"


def test_no_ledger_refuses_to_record(monkeypatch):
    for k in ("DATABASE_URL", "LEDGER", "K_SERVICE"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ledger.LedgerUnavailable):
        ledger.record("0xabc", {"email": "a@b.co", "tier": "pro"})
