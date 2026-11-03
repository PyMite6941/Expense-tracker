"""
Licence ledger: one record per order id (or USDC tx hash), written atomically
so a single payment can never mint two keys.

Backend is picked from the environment:

- ``DATABASE_URL`` set  -> Postgres (Neon via Vercel Storage, or any Postgres).
- else running on Cloud Run (``K_SERVICE``) or ``LEDGER=firestore`` -> Firestore.
- else -> no ledger. ``record()`` raises ``LedgerUnavailable``; callers decide
  whether that is fatal (it is for /redeem: without a ledger a tx hash could be
  replayed forever).
"""
import json
import logging
import os

log = logging.getLogger(__name__)

LICENSE_COLLECTION = os.getenv("LICENSE_COLLECTION", "licenses")


class AlreadyRecorded(Exception):
    pass


class LedgerUnavailable(Exception):
    pass


def backend_name() -> str:
    if os.getenv("DATABASE_URL", "").strip():
        return "postgres"
    if os.getenv("LEDGER", "").lower() == "firestore" or os.getenv("K_SERVICE"):
        return "firestore"
    return "none"


_DDL = """
CREATE TABLE IF NOT EXISTS licenses (
    order_id   text PRIMARY KEY,
    email      text NOT NULL,
    tier       text NOT NULL,
    jti        text,
    record     jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
)
"""
_ddl_done = False


def _pg_record(order_id: str, record: dict) -> None:
    global _ddl_done
    try:
        import psycopg
    except ImportError as exc:
        raise LedgerUnavailable("psycopg is not installed") from exc
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=8) as conn:
            if not _ddl_done:
                conn.execute(_DDL)
                _ddl_done = True
            row = conn.execute(
                "INSERT INTO licenses (order_id, email, tier, jti, record) "
                "VALUES (%s, %s, %s, %s, %s::jsonb) "
                "ON CONFLICT (order_id) DO NOTHING RETURNING order_id",
                (order_id, record["email"], record["tier"], record.get("jti"),
                 json.dumps(record)),
            ).fetchone()
    except psycopg.Error as exc:
        raise LedgerUnavailable(str(exc).splitlines()[0]) from exc
    if row is None:
        raise AlreadyRecorded(order_id)


def _fs_record(order_id: str, record: dict) -> None:
    try:
        from google.cloud import firestore
        from google.api_core.exceptions import AlreadyExists, GoogleAPIError
    except ImportError as exc:
        raise LedgerUnavailable("google-cloud-firestore is not installed") from exc
    # Firestore document IDs cannot contain '/' and must be <= 1500 bytes.
    doc_id = order_id.replace("/", "_")[:1500]
    try:
        firestore.Client().collection(LICENSE_COLLECTION).document(doc_id).create(record)
    except AlreadyExists as exc:
        raise AlreadyRecorded(order_id) from exc
    except GoogleAPIError as exc:
        raise LedgerUnavailable(str(exc)) from exc


def record(order_id: str, record: dict) -> None:
    """Atomically store ``record`` under ``order_id``.

    Raises ``AlreadyRecorded`` if the id exists, ``LedgerUnavailable`` if there
    is no usable store.
    """
    name = backend_name()
    if name == "postgres":
        return _pg_record(order_id, record)
    if name == "firestore":
        return _fs_record(order_id, record)
    raise LedgerUnavailable("no licence ledger configured (set DATABASE_URL)")
