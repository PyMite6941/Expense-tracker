"""
Per-license IP activation limits.

Each license key (identified by its JWT ``jti``) may be used from at most a
fixed number of distinct client IPs — Pro: 3, Max: 6 by default. The
authoritative cap travels in the signed token's ``max_ips`` claim, so it
cannot be tampered with client-side.

State lives in Postgres when ``DATABASE_URL`` is set (table ``license_ips``,
used on Vercel with Neon), otherwise in Firestore (collection ``license_ips``,
used on Cloud Run), so the limit holds across instances and restarts. If the
store is unavailable the check fails OPEN (allows the request) so a storage blip never locks out a
paying customer — set ``IP_LIMIT_FAIL_OPEN=false`` to fail closed instead.
"""
import hashlib
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_COLLECTION = os.getenv("IP_LIMIT_COLLECTION", "license_ips")
_FAIL_OPEN = os.getenv("IP_LIMIT_FAIL_OPEN", "true").lower() != "false"
DEFAULT_TIER_LIMITS = {"pro": 3, "max": 6}

_client = None
_unavailable = False


def _get_client():
    """Lazily create a Firestore client; cache 'unavailable' so a missing
    backend doesn't trigger a slow retry on every request."""
    global _client, _unavailable
    if _unavailable:
        return None
    if _client is None:
        try:
            from google.cloud import firestore
            _client = firestore.Client()
        except Exception as exc:  # missing creds, no database, import error…
            log.warning("Firestore unavailable; IP limiting disabled: %s", exc)
            _unavailable = True
            return None
    return _client


# ── Postgres (DATABASE_URL) ──────────────────────────────────────────────────

_PG_DDL = """
CREATE TABLE IF NOT EXISTS license_ips (
    key_id     text NOT NULL,
    ip         text NOT NULL,
    tier       text,
    sub        text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (key_id, ip)
)
"""
_pg_ready = False


def _pg_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _pg_connect():
    global _pg_ready
    import psycopg
    conn = psycopg.connect(_pg_url(), connect_timeout=5)
    if not _pg_ready:
        conn.execute(_PG_DDL)
        conn.commit()
        _pg_ready = True
    return conn


def _pg_check(claims: dict, ip: str, limit: int):
    key_id = key_id_from_claims(claims)
    with _pg_connect() as conn:
        # Serialise concurrent first-uses of one key so two new IPs can't both
        # slip in under the cap.
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (key_id,))
        known = conn.execute("SELECT 1 FROM license_ips WHERE key_id = %s AND ip = %s",
                             (key_id, ip)).fetchone()
        count = conn.execute("SELECT count(*) FROM license_ips WHERE key_id = %s",
                             (key_id,)).fetchone()[0]
        if known:
            return True, count, limit
        if count >= limit:
            return False, count, limit
        conn.execute("INSERT INTO license_ips (key_id, ip, tier, sub) VALUES (%s, %s, %s, %s) "
                     "ON CONFLICT DO NOTHING",
                     (key_id, ip, claims.get("tier"), claims.get("sub")))
        return True, count + 1, limit


def key_id_from_claims(claims: dict) -> str:
    """Stable per-license id. Prefers the JWT ``jti``; falls back to a hash
    of stable claims for legacy tokens issued before ``jti`` existed."""
    jti = claims.get("jti")
    if jti:
        return str(jti)
    raw = f"{claims.get('sub', '')}|{claims.get('iat', '')}|{claims.get('tier', '')}"
    return "legacy-" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def max_ips_for(claims: dict) -> int:
    """Authoritative cap from the signed token, with a tier-based fallback."""
    cap = claims.get("max_ips")
    if isinstance(cap, int) and cap > 0:
        return cap
    return DEFAULT_TIER_LIMITS.get(str(claims.get("tier", "")).lower(), 3)


def check_and_register_ip(claims: dict, ip: str):
    """Returns ``(allowed: bool, count: int, limit: int)``.

    - Known IP for this key  -> allowed, nothing changes.
    - New IP and under the cap -> registered, allowed.
    - New IP and at the cap   -> rejected.
    """
    limit = max_ips_for(claims)
    if not ip:
        return True, 0, limit  # can't identify the client; don't punish them

    if _pg_url():
        try:
            return _pg_check(claims, ip, limit)
        except Exception as exc:
            log.warning("IP limit check (postgres) errored (%s); failing %s",
                        exc, "open" if _FAIL_OPEN else "closed")
            return _FAIL_OPEN, 0, limit

    client = _get_client()
    if client is None:
        return _FAIL_OPEN, 0, limit

    try:
        from google.cloud import firestore
        key_id = key_id_from_claims(claims)
        doc_ref = client.collection(_COLLECTION).document(key_id)

        @firestore.transactional
        def _txn(txn):
            snap = doc_ref.get(transaction=txn)
            data = snap.to_dict() if snap.exists else {}
            ips = dict(data.get("ips", {}))
            if ip in ips:
                return True, len(ips), limit
            if len(ips) >= limit:
                return False, len(ips), limit
            ips[ip] = datetime.now(timezone.utc).isoformat()
            txn.set(doc_ref, {
                "ips": ips,
                "tier": claims.get("tier"),
                "sub": claims.get("sub"),
                "max_ips": limit,
                "updated": datetime.now(timezone.utc).isoformat(),
            }, merge=True)
            return True, len(ips), limit

        return _txn(client.transaction())
    except Exception as exc:
        log.warning("IP limit check errored (%s); failing %s",
                    exc, "open" if _FAIL_OPEN else "closed")
        return _FAIL_OPEN, 0, limit


def reset_key(key_id: str) -> bool:
    """Clear all registered IPs for a license — for support / device-change
    resets. Returns True on success."""
    if _pg_url():
        try:
            with _pg_connect() as conn:
                conn.execute("DELETE FROM license_ips WHERE key_id = %s", (key_id,))
            return True
        except Exception as exc:
            log.warning("Failed to reset activations for %s: %s", key_id, exc)
            return False
    client = _get_client()
    if client is None:
        return False
    try:
        client.collection(_COLLECTION).document(key_id).delete()
        return True
    except Exception as exc:
        log.warning("Failed to reset activations for %s: %s", key_id, exc)
        return False
