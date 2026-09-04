"""Auth-provider-agnostic tenancy: signed-in user -> organization -> storage backend.

Deliberately contains NO streamlit and NO provider SDK imports, so it can be
unit-tested headlessly and reused by the CLI, the Streamlit UI, or a future API.

How auth plugs in
-----------------
The app only ever needs a stable user id + an email. Streamlit 1.42+ ships
native OpenID Connect (`st.login()` / `st.user`), and Clerk/Google/Auth0 are all
OIDC providers — so the UI layer reads `st.user` and hands us an AuthUser. No
provider-specific code lives here.

Access model (matches the business model)
-----------------------------------------
  * FREE  = self-host locally. Storage is data.json (JsonStore); no account.
  * PAID  = Matt hosts it. Requires an entitlement purchased through the GRID
            store, which the Cloudflare worker wrote into `entitlements`.

So in hosted mode a user with no claimed entitlement gets NO storage — they are
shown an upsell, not an empty workspace.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

try:
    from .storage import JsonStore, PostgresStore, StorageBackend
except ImportError:  # allow flat imports / running as a script
    from storage import JsonStore, PostgresStore, StorageBackend


@dataclass(frozen=True)
class AuthUser:
    """Whoever is signed in. `user_id` must be stable for the provider."""
    user_id: str
    email: str
    name: Optional[str] = None

    @classmethod
    def from_oidc(cls, user) -> Optional["AuthUser"]:
        """Build from a Streamlit `st.user` (or any OIDC claims mapping).

        Prefers the provider's subject claim; falls back to email so the identity
        is never silently None.
        """
        if user is None:
            return None
        get = user.get if hasattr(user, "get") else lambda k, d=None: getattr(user, k, d)
        if not get("is_logged_in", True):
            return None
        email = (get("email") or "").strip().lower()
        user_id = (get("sub") or get("id") or email or "").strip()
        if not user_id or not email:
            return None
        return cls(user_id=user_id, email=email, name=get("name"))


class NoEntitlementError(RuntimeError):
    """Signed in, but this account has no active hosted subscription."""


def claim_and_resolve_org(dsn: str, user: AuthUser) -> Tuple[Optional[int], int]:
    """Claim any purchased entitlements, then return (org_id, n_claimed).

    Safe to call on every login: claim_entitlements() is idempotent and also
    returns the user's existing org when there is nothing new to claim.
    """
    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("select claim_entitlements(%s, %s)", (user.user_id, user.email))
        result = cur.fetchone()[0] or {}
        conn.commit()
    if result.get("error"):
        raise RuntimeError(f"claim_entitlements failed: {result['error']}")
    return result.get("org_id"), result.get("claimed", 0)


def create_org(dsn: str, user: AuthUser, name: str = None, plan: str = "free") -> int:
    """Create an organization owned by `user` and make them its admin.

    Used for self-serve/trial workspaces and for Matt's own enterprise org —
    NOT part of the purchase flow (that goes through entitlements).
    """
    import psycopg

    org_name = name or f"{user.email.split('@')[0]}'s workspace"
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "insert into organizations (name, plan, created_by) "
            "values (%s, %s::org_plan, %s) returning id",
            (org_name, plan, user.user_id),
        )
        org_id = cur.fetchone()[0]
        cur.execute(
            "insert into members (org_id, user_id, email, role) values (%s, %s, %s, 'admin') "
            "on conflict (org_id, user_id) do nothing",
            (org_id, user.user_id, user.email),
        )
        conn.commit()
    return org_id


def get_role(dsn: str, org_id: int, user: AuthUser) -> Optional[str]:
    """'admin' | 'member' | 'viewer', or None if not a member.

    Viewers are read-only — the UI should hide/disable mutations for them.
    """
    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "select role from members where org_id = %s and user_id = %s",
            (org_id, user.user_id),
        )
        row = cur.fetchone()
    return row[0] if row else None


def make_store(
    user: Optional[AuthUser] = None,
    dsn: Optional[str] = None,
    data_file: str = "data.json",
    hosted: Optional[bool] = None,
) -> StorageBackend:
    """Pick the right storage backend for this session.

    hosted=False (or no dsn)  -> JsonStore, the free self-hosted mode.
    hosted=True               -> PostgresStore scoped to the user's org.
                                 Raises NoEntitlementError if they have none.
    """
    dsn = dsn or os.getenv("ET_DATABASE_URL") or os.getenv("DATABASE_URL")
    if hosted is None:
        hosted = bool(dsn)

    if not hosted:
        return JsonStore(data_file)

    if not dsn:
        raise RuntimeError("hosted mode requires ET_DATABASE_URL")
    if user is None:
        raise RuntimeError("hosted mode requires a signed-in user")

    org_id, _claimed = claim_and_resolve_org(dsn, user)
    if org_id is None:
        raise NoEntitlementError(
            f"{user.email} has no active hosted subscription. "
            "Purchase hosting in the GRID store, or self-host for free."
        )
    return PostgresStore(dsn, org_id=org_id, created_by=user.user_id)
