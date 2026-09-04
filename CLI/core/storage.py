"""Storage backends for the expense tracker data layer.

The entire app funnels reads/writes through two methods on ExpenseTracker
(`open_file` / `write_file`). Those delegate to a StorageBackend, so the same
app can run against a local JSON file (free, self-hosted) or a hosted
multi-tenant database (paid SaaS) without touching any CRUD logic.

Backends:
  * JsonStore     — local `data.json`. Default; identical to the original behavior.
  * PostgresStore — org-scoped Neon Postgres for hosted mode.

Contract:
  read()  -> dict   the raw stored blob ({} if none yet)
  write(data: dict) persist the full blob

Blob shape (since accounts were added):

    {"finance_data": {<the nine lists>}, "accounts_data": {...}}

Files written before accounts existed are a bare, unwrapped finance dict.
`normalize_blob` accepts either and always returns the wrapped shape, so old
files keep loading and backends only ever see one contract on write.

This module — not the CRUD layer — owns what a VALID stored blob looks like:
the empty shapes, the per-account-type field defaults, the upgrade from the
legacy unwrapped file, and the guarantee that every key a caller expects is
present. `ExpenseTracker.open_file` / `write_file` are thin delegations to it.
Keeping that here means the shape is defined once, is testable without touching
the domain layer, and both backends agree on it by construction.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


# ---------------------------------------------------------------------------
# Blob shape
# ---------------------------------------------------------------------------

# The nine finance lists, empty.
BLANK_FINANCE: Dict[str, list] = {
    "expenses": [], "income": [], "budget": [], "subscriptions": [], "goals": [],
    "recurring_expenses": [], "recurring_income": [], "assets": [], "liabilities": [],
}

# A new account. `type` is blank on purpose: until it is picked we do not know
# whether this is savings or checking, so no type-specific field is assumed.
BLANK_ACCOUNT: Dict[str, Any] = {"type": "", "expenses": [], "deposits": []}

# Extra fields each account type carries, and the value they start at.
# Add a type here and it gets its defaults applied everywhere, automatically.
ACCOUNT_TYPE_FIELDS: Dict[str, Dict[str, Any]] = {
    "":         {},
    "checking": {"balance": 0.0, "currency": "usd"},
    "savings":  {"balance": 0.0, "currency": "usd", "interest_rate": 0.0, "compound": "monthly"},
    "credit":   {"balance": 0.0, "currency": "usd", "credit_limit": 0.0,
                 "interest_rate": 0.0, "statement_day": 1},
    "cash":     {"balance": 0.0, "currency": "usd"},
}

# Every field any type can add, so a leftover from a previous type is spottable.
_ALL_TYPE_FIELDS = {f for fields in ACCOUNT_TYPE_FIELDS.values() for f in fields}


def is_wrapped(blob: Any) -> bool:
    """True if this is the current two-half shape rather than a legacy file."""
    return isinstance(blob, dict) and ("finance_data" in blob or "accounts_data" in blob)


def apply_account_type(account: Dict[str, Any]) -> Dict[str, Any]:
    """Give an account exactly the fields its `type` calls for.

    Returns {'success', 'data', 'removed'} — `removed` carries any field dropped
    because it belonged to a *different* type, so a UI can warn before a type
    change silently bins a value the user entered.

    Fields no type claims (a name, an id, notes) are never touched. An
    unrecognised type changes nothing and reports success=False, so a typo
    cannot wipe an account.
    """
    for field, default in BLANK_ACCOUNT.items():
        if field not in account:
            account[field] = list(default) if isinstance(default, list) else default

    account_type = str(account.get("type", "")).lower()
    account["type"] = account_type

    if account_type not in ACCOUNT_TYPE_FIELDS:
        return {"success": False, "data": account, "removed": {},
                "message": f"Unknown account type: {account_type}"}

    type_fields = ACCOUNT_TYPE_FIELDS[account_type]

    # Drop fields owned by a different type — otherwise a checking account keeps
    # an interest rate and nothing downstream can tell what it actually has.
    removed = {}
    for field in list(account):
        if field in _ALL_TYPE_FIELDS and field not in type_fields:
            removed[field] = account.pop(field)

    for field, default in type_fields.items():
        account.setdefault(field, default)

    return {"success": True, "data": account, "removed": removed}


def normalize_blob(blob: Any) -> Dict[str, Any]:
    """Coerce anything a backend hands back into a complete, valid blob.

    Accepts the wrapped shape, the legacy unwrapped finance dict, or junk, and
    always returns {"finance_data": ..., "accounts_data": ...} with every
    expected key present.

    This is deliberately PURE — it never writes. The previous version persisted
    a repaired blob during `open_file`, which in hosted mode meant a plain read
    bumped `organizations.data_version` and could fail a co-worker's in-flight
    save for no reason (see 003_concurrency.sql). Repairs now ride along on the
    next real write instead.
    """
    if not isinstance(blob, dict):
        blob = {}

    if is_wrapped(blob):
        finance = blob.get("finance_data")
        accounts = blob.get("accounts_data")
    else:
        # A file written before accounts existed is the finance half by itself.
        finance = blob
        accounts = None

    if not isinstance(finance, dict):
        finance = {}
    for key, empty in BLANK_FINANCE.items():
        if not isinstance(finance.get(key), list):
            finance[key] = list(empty)

    if not isinstance(accounts, dict) or not accounts:
        accounts = dict(BLANK_ACCOUNT)
    apply_account_type(accounts)

    return {"finance_data": finance, "accounts_data": accounts}


class StorageBackend(ABC):
    """A pluggable place to keep one account's finance data."""

    @abstractmethod
    def read(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def write(self, data: Dict[str, Any]) -> None:
        ...


class JsonStore(StorageBackend):
    """Local single-user storage backed by a JSON file (the free/self-host mode)."""

    def __init__(self, filename: str = "data.json") -> None:
        self.filename = filename

    def read(self) -> Dict[str, Any]:
        try:
            with open(self.filename, "r") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def write(self, data: Dict[str, Any]) -> None:
        with open(self.filename, "w") as file:
            json.dump(data, file)


# ---------------------------------------------------------------------------
# Hosted multi-tenant backend (Neon Postgres). One instance == one org.
#
# Correctness:
#   * `organizations.data_version` gives optimistic concurrency — a write from a
#     stale snapshot raises ConcurrentModificationError instead of silently
#     clobbering a co-worker.
#   * write() is diff-based: only changed rows are inserted/updated/deleted, so
#     row ids, created_at and the audit trail survive across saves.
#   * Every mutation is recorded in audit_log (before/after jsonb).
#
# Performance (this matters a lot — a remote Neon region can be 300-500ms RTT):
#   * read() is ONE round trip. All nine tables plus the version come back in a
#     single jsonb_build_object result.
#   * write() diffs against the snapshot captured by read() rather than
#     re-SELECTing, and batches every insert/update/delete/audit into
#     multi-row statements. A save is a handful of round trips, not ~20.
#   * The connection is cached on the instance and re-established if dropped.
#
# Requires: pip install "psycopg[binary]"
# ---------------------------------------------------------------------------

# Maps each data.json list key -> (table, [(json_field, db_column), ...]).
# Column names match 001_enterprise_schema.sql; a few differ from the JSON keys
# (subscriptions.startDate -> start_date, goals.monthContribution -> month_contribution).
_TABLE_SPEC = {
    "expenses":           ("expenses",           [("price", "price"), ("purchased", "purchased"), ("tags", "tags"), ("date", "date"), ("currency", "currency"), ("notes", "notes")]),
    "income":             ("income",             [("amount", "amount"), ("source", "source"), ("date", "date"), ("currency", "currency"), ("notes", "notes")]),
    "budget":             ("budgets",            [("category", "category"), ("amount", "amount"), ("currency", "currency")]),
    "subscriptions":      ("subscriptions",      [("name", "name"), ("price", "price"), ("currency", "currency"), ("startDate", "start_date")]),
    "goals":              ("goals",              [("name", "name"), ("amount", "amount"), ("startDate", "start_date"), ("monthContribution", "month_contribution"), ("currency", "currency")]),
    "recurring_expenses": ("recurring_expenses", [("amount", "amount"), ("purchased", "purchased"), ("tags", "tags"), ("currency", "currency")]),
    "recurring_income":   ("recurring_income",   [("amount", "amount"), ("source", "source"), ("currency", "currency")]),
    "assets":             ("assets",             [("name", "name"), ("type", "type"), ("value", "value"), ("currency", "currency"), ("notes", "notes")]),
    "liabilities":        ("liabilities",        [("name", "name"), ("type", "type"), ("balance", "balance"), ("currency", "currency"), ("interest_rate", "interest_rate"), ("notes", "notes")]),
}


class ConcurrentModificationError(RuntimeError):
    """Raised when another writer changed this org's data since it was loaded.

    The caller should reload (open_file) and re-apply the change. Surfacing this
    is the point: it converts a silent lost update into a visible, retryable error.
    """


def _build_read_sql() -> str:
    """One query returning {version, accounts, <each list>} as a single jsonb object."""
    parts = [
        "'version', (select data_version from organizations where id = %(org)s)",
        "'accounts', (select coalesce(accounts_data, '{}'::jsonb) "
        "from organizations where id = %(org)s)",
    ]
    for json_key, (table, fields) in _TABLE_SPEC.items():
        cols = ", ".join(["id"] + [db for _, db in fields])
        parts.append(
            f"'{json_key}', (select coalesce(jsonb_agg(to_jsonb(x) order by x.id), '[]'::jsonb) "
            f"from (select {cols} from {table} where org_id = %(org)s) x)"
        )
    return "select jsonb_build_object(" + ", ".join(parts) + ")"


_READ_SQL = _build_read_sql()


class PostgresStore(StorageBackend):
    """Org-scoped Postgres storage for hosted (paid) mode.

    Every read/write is filtered by org_id, so one store instance only ever
    sees a single tenant's finance data.
    """

    def __init__(self, dsn: str, org_id: int, created_by: str = None) -> None:
        self.dsn = dsn
        self.org_id = org_id
        self.created_by = created_by  # auth user id stamped on rows + audit_log
        self._version = None          # data_version observed at last read()
        self._snapshot = None         # {list_key: {id: {field: value}}} from last read()
        self._conn = None             # reused across calls (see _session)

    # -- connection -----------------------------------------------------------

    @staticmethod
    def _psycopg():
        try:
            import psycopg  # psycopg 3
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                'PostgresStore needs psycopg: pip install "psycopg[binary]"'
            ) from exc
        return psycopg

    def _session(self, fn):
        """Run fn(conn) in a transaction on a REUSED connection.

        Transparently re-establishes the connection if it dropped (Neon
        scale-to-zero, idle timeouts).
        """
        psycopg = self._psycopg()
        for attempt in (1, 2):
            try:
                if self._conn is None or self._conn.closed:
                    self._conn = psycopg.connect(self.dsn)
                with self._conn:            # transaction: commit / rollback
                    return fn(self._conn)
            except (psycopg.OperationalError, psycopg.InterfaceError):
                try:
                    if self._conn is not None:
                        self._conn.close()
                except Exception:
                    pass
                self._conn = None
                if attempt == 2:
                    raise

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
        self._conn = None

    # -- read -----------------------------------------------------------------

    @staticmethod
    def _is_wrapped(data: Dict[str, Any]) -> bool:
        return isinstance(data, dict) and ("finance_data" in data or "accounts_data" in data)

    @classmethod
    def _finance_half(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Return just the nine finance lists from either blob shape.

        CRITICAL: write() diffs `data` against the last snapshot and DELETES any
        row it cannot find. Handed the wrapped blob unchanged, every
        `data.get("expenses")` would miss, every list would look empty, and the
        diff would wipe the org's entire dataset. Always unwrap first.
        """
        if cls._is_wrapped(data):
            inner = data.get("finance_data")
            return inner if isinstance(inner, dict) else {}
        return data if isinstance(data, dict) else {}

    @classmethod
    def _accounts_half(cls, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return the accounts half, or None if this blob doesn't carry one.

        None means "leave whatever is stored alone" — a legacy unwrapped write
        must not blank out an org's accounts.
        """
        if cls._is_wrapped(data):
            inner = data.get("accounts_data")
            return inner if isinstance(inner, dict) else None
        return None

    def read(self) -> Dict[str, Any]:
        def _do(conn):
            with conn.cursor() as cur:
                cur.execute(_READ_SQL, {"org": self.org_id})
                raw = cur.fetchone()[0]

            if raw.get("version") is None:
                raise RuntimeError(f"organization {self.org_id} does not exist")
            self._version = raw["version"]

            data, snapshot = {}, {}
            for json_key, (_table, fields) in _TABLE_SPEC.items():
                items, snap = [], {}
                for r in raw.get(json_key) or []:
                    rid = r["id"]
                    payload = {jf: r.get(db) for jf, db in fields}
                    items.append({"id": rid, **payload})
                    snap[rid] = payload
                data[json_key] = items
                snapshot[json_key] = snap
            self._snapshot = snapshot
            accounts = raw.get("accounts")
            return {
                "finance_data": data,
                "accounts_data": accounts if isinstance(accounts, dict) else {},
            }

        return self._session(_do)

    def _fetch_snapshot(self, cur) -> Dict[str, Dict[int, Dict[str, Any]]]:
        """Fallback when write() is called without a preceding read()."""
        cur.execute(_READ_SQL, {"org": self.org_id})
        raw = cur.fetchone()[0]
        return {
            json_key: {
                r["id"]: {jf: r.get(db) for jf, db in fields}
                for r in (raw.get(json_key) or [])
            }
            for json_key, (_t, fields) in _TABLE_SPEC.items()
        }

    # -- write ----------------------------------------------------------------

    def write(self, data: Dict[str, Any]) -> None:
        from psycopg.types.json import Json

        # Unwrap before anything touches the diff — see _finance_half().
        accounts = self._accounts_half(data)
        data = self._finance_half(data)

        def _do(conn):
            with conn.cursor() as cur:
                # 1. Optimistic lock.
                if self._version is None:
                    cur.execute(
                        "select data_version from organizations where id = %s",
                        (self.org_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise RuntimeError(f"organization {self.org_id} does not exist")
                    self._version = row[0]

                # accounts_data rides along on the same guarded UPDATE, so it is
                # covered by the identical version check as the finance tables —
                # a stale writer cannot land half a save. None = the caller sent
                # a legacy unwrapped blob, so leave the stored accounts alone.
                if accounts is None:
                    cur.execute(
                        "update organizations set data_version = data_version + 1 "
                        "where id = %s and data_version = %s",
                        (self.org_id, self._version),
                    )
                else:
                    cur.execute(
                        "update organizations set data_version = data_version + 1, "
                        "accounts_data = %s where id = %s and data_version = %s",
                        (Json(accounts), self.org_id, self._version),
                    )
                if cur.rowcount == 0:
                    raise ConcurrentModificationError(
                        f"org {self.org_id} was modified by another user since it was "
                        f"loaded (expected data_version {self._version}). "
                        "Reload and re-apply the change."
                    )
                next_version = self._version + 1

                # 2. Diff against the snapshot from read() — no re-SELECT needed,
                #    because the version check just proved nothing else changed.
                snapshot = self._snapshot
                if snapshot is None:
                    snapshot = self._fetch_snapshot(cur)

                audit_rows = []  # (action, entity, entity_id, before, after)

                for json_key, (table, fields) in _TABLE_SPEC.items():
                    existing = snapshot.get(json_key, {})
                    items = data.get(json_key) or []
                    db_cols = [db for _, db in fields]

                    seen, inserts, updates = set(), [], []
                    for item in items:
                        iid = item.get("id")
                        payload = {jf: item.get(jf) for jf, _ in fields}
                        if iid in existing:
                            seen.add(iid)
                            if not _rows_equal(existing[iid], payload):
                                updates.append(
                                    (*[payload[jf] for jf, _ in fields], iid, self.org_id)
                                )
                                audit_rows.append(
                                    ("update", table, iid, existing[iid], payload)
                                )
                        else:
                            inserts.append(payload)

                    # Batched multi-row INSERT ... RETURNING id (one round trip).
                    if inserts:
                        col_list = ", ".join(["org_id", "created_by", *db_cols])
                        tuple_sql = "(" + ", ".join(["%s"] * (2 + len(db_cols))) + ")"
                        params = []
                        for p in inserts:
                            params.extend(
                                [self.org_id, self.created_by, *[p[jf] for jf, _ in fields]]
                            )
                        cur.execute(
                            f"insert into {table} ({col_list}) values "
                            + ", ".join([tuple_sql] * len(inserts))
                            + " returning id",
                            params,
                        )
                        for (new_id,), p in zip(cur.fetchall(), inserts):
                            audit_rows.append(("create", table, new_id, None, p))

                    if updates:
                        set_clause = ", ".join(f"{db} = %s" for db in db_cols)
                        cur.executemany(
                            f"update {table} set {set_clause} where id = %s and org_id = %s",
                            updates,
                        )

                    gone = [i for i in existing if i not in seen]
                    if gone:
                        cur.execute(
                            f"delete from {table} where org_id = %s and id = any(%s)",
                            (self.org_id, gone),
                        )
                        for g in gone:
                            audit_rows.append(("delete", table, g, existing[g], None))

                # 3. One batched audit insert for the whole save.
                if audit_rows:
                    tuple_sql = "(" + ", ".join(["%s"] * 7) + ")"
                    params = []
                    for action, entity, entity_id, before, after in audit_rows:
                        params.extend([
                            self.org_id, self.created_by, action, entity, entity_id,
                            Json(before) if before is not None else None,
                            Json(after) if after is not None else None,
                        ])
                    cur.execute(
                        "insert into audit_log (org_id, actor, action, entity, entity_id, before, after) "
                        "values " + ", ".join([tuple_sql] * len(audit_rows)),
                        params,
                    )

            return next_version

        # _session commits; only advance our baseline on success.
        self._version = self._session(_do)
        # Ids changed (new rows); force a fresh snapshot on the next read.
        self._snapshot = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _scalars_equal(a, b) -> bool:
    """Tolerant compare: 500 == 500.0, and None only equals None."""
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-9
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a) == str(b)


def _rows_equal(db_row: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    return all(_scalars_equal(db_row.get(k), payload.get(k)) for k in payload)
