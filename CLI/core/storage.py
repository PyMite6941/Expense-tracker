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

# Accounts are a LIST — you have several, and each one is customised: two
# savings accounts at different banks will not carry the same fields.
BLANK_ACCOUNTS: list = []

# The fields every account has regardless of type. `type` is blank on purpose:
# until it is picked we do not know whether this is savings or checking, so no
# type-specific field is assumed.
BLANK_ACCOUNT: Dict[str, Any] = {"id": None, "name": "", "type": "",
                                 "expenses": [], "deposits": []}


def next_account_id(accounts: list) -> int:
    """Smallest free positive id. Ids are stable, so a transfer can point at one."""
    used = {a.get("id") for a in accounts if isinstance(a, dict)}
    i = 1
    while i in used:
        i += 1
    return i


def new_account(name: str = "", account_type: str = "", accounts: list = None) -> Dict[str, Any]:
    """A blank account record. Carries NO type fields — those arrive only as
    the user actually fills them in (see apply_account_type's fill_defaults)."""
    acc = {k: (list(v) if isinstance(v, list) else v) for k, v in BLANK_ACCOUNT.items()}
    acc["id"] = next_account_id(accounts or [])
    acc["name"] = name
    acc["type"] = str(account_type or "").lower()
    return acc

# Extra fields each account type carries, and the value they start at.
# Add a type here and it gets its defaults applied everywhere, automatically.
#
# The field sets model what these products ACTUALLY differ on, so the app can
# say something true about each one:
#   * apy vs apr  — a deposit account pays you (annual percentage YIELD, which
#                   already includes compounding); a card charges you (annual
#                   percentage RATE, which does not). Same number, opposite
#                   direction, different maths — so they are different fields
#                   and switching type swaps one for the other.
#   * compound    — daily is the US norm for savings/MMA; monthly and quarterly
#                   exist. It is the difference between a correct projection
#                   and an approximate one.
#   * fee fields  — the reason a traditional savings account can lose to a
#                   high-yield one even at the same headline rate.
#
# NOTE on money-market tiering: real MMAs often pay a different rate per balance
# band. That is modelled here as a single `apy` you set for your current tier,
# not as a rate table. Deliberate simplification — a tier table is a nested
# structure the rest of the data layer has no shape for yet.
ACCOUNT_TYPE_FIELDS: Dict[str, Dict[str, Any]] = {
    # Not chosen yet — an account keeps only the base fields until you pick.
    "": {},

    # ── Everyday / transactional ─────────────────────────────────────────────
    "checking": {
        "balance": 0.0, "currency": "usd",
        "monthly_fee": 0.0,          # maintenance fee
        "min_balance": 0.0,          # balance that waives the fee
        "overdraft_protection": False,
    },
    "interest_checking": {           # "rewards"/"high-yield" checking
        "balance": 0.0, "currency": "usd",
        "apy": 0.0, "compound": "monthly",
        "monthly_fee": 0.0, "min_balance": 0.0,
        "overdraft_protection": False,
    },
    "cash": {
        "balance": 0.0, "currency": "usd",
    },

    # ── Savings ──────────────────────────────────────────────────────────────
    "savings": {                     # traditional / brick-and-mortar
        "balance": 0.0, "currency": "usd",
        "apy": 0.0, "compound": "daily",
        "min_balance": 0.0, "monthly_fee": 0.0,
        "withdrawal_limit": 6,       # many banks still cap this per cycle
    },
    "online_savings": {              # high-yield. Usually no fee, no minimum,
        "balance": 0.0, "currency": "usd",   # but transfers out take days.
        "apy": 0.0, "compound": "daily",
        "transfer_days": 3,          # ACH settlement — why it is not spendable
    },
    "mma": {                         # money market account
        "balance": 0.0, "currency": "usd",
        "apy": 0.0, "compound": "daily",
        "min_balance": 0.0, "monthly_fee": 0.0,
        "check_writing": True,       # the thing that separates an MMA from savings
        "debit_card": True,
    },
    "cd": {                          # certificate of deposit
        "balance": 0.0, "currency": "usd",
        "apy": 0.0, "compound": "daily",
        "term_months": 12,
        "maturity_date": "",
        "early_withdrawal_penalty_months": 3,   # months of interest forfeited
    },

    # ── Credit ───────────────────────────────────────────────────────────────
    "credit": {
        "balance": 0.0, "currency": "usd",      # what you OWE (see ACCOUNT_TYPE_META)
        "credit_limit": 0.0,
        "apr": 0.0,
        "statement_day": 1,
        "due_day": 25,
        "min_payment": 0.0,
    },
}

# Presentation + behaviour that is not a field default.
#
# `sign` is the load-bearing one: a credit balance is money owed, so it counts
# AGAINST net worth. Without this flag nothing downstream can tell a $2,000
# savings balance from a $2,000 card balance.
ACCOUNT_TYPE_META: Dict[str, Dict[str, Any]] = {
    "":                  {"label": "Not set yet",     "group": "",          "sign": "asset"},
    "checking":          {"label": "Checking",        "group": "Everyday",  "sign": "asset"},
    "interest_checking": {"label": "Interest checking","group": "Everyday", "sign": "asset"},
    "cash":              {"label": "Cash",            "group": "Everyday",  "sign": "asset"},
    "savings":           {"label": "Savings",         "group": "Savings",   "sign": "asset"},
    "online_savings":    {"label": "Online savings (high-yield)",
                                                      "group": "Savings",   "sign": "asset"},
    "mma":               {"label": "Money market (MMA)", "group": "Savings", "sign": "asset"},
    "cd":                {"label": "Certificate of deposit",
                                                      "group": "Savings",   "sign": "asset"},
    "credit":            {"label": "Credit card",     "group": "Credit",    "sign": "liability"},
}

# Constrained fields, so a form renders a dropdown instead of a free-text box
# and the stored values stay consistent enough to compute with.
ACCOUNT_FIELD_CHOICES: Dict[str, list] = {
    "compound": ["daily", "monthly", "quarterly", "annually"],
}

# Fields that are a rate expressed as a percent, so a UI can label them "%" and
# a calculation knows to divide by 100 rather than guessing from the magnitude.
ACCOUNT_RATE_FIELDS = {"apy", "apr"}


def account_types_by_group() -> Dict[str, list]:
    """Account types grouped for a picker, in a sensible order.

    Returns {group_label: [(type_key, human_label), ...]}, skipping the blank
    type — that is a state, not something you choose from a menu.
    """
    out: Dict[str, list] = {}
    for key, meta in ACCOUNT_TYPE_META.items():
        if not key:
            continue
        out.setdefault(meta["group"], []).append((key, meta["label"]))
    return out


def is_liability(account: Dict[str, Any]) -> bool:
    """True when this account's balance is money OWED, not money held."""
    meta = ACCOUNT_TYPE_META.get(str(account.get("type", "")).lower(), {})
    return meta.get("sign") == "liability"


def account_balance(account: Dict[str, Any], expenses: list, income: list) -> Dict[str, Any]:
    """What an account is actually holding, derived from what was charged to it.

    opening_balance (or `balance`, whichever the user entered) is the starting
    point; everything charged to the account moves it from there. Derived rather
    than stored, so the number can never drift away from the transactions that
    explain it.

    Sign depends on what the account IS. Spending on a credit card increases
    what you OWE; spending from checking decreases what you HOLD. Without that
    distinction a card would look like it was gaining money every purchase.
    """
    aid = account.get("id")
    opening = float(account.get("opening_balance", account.get("balance", 0)) or 0)
    charged = sum(float(e.get("price", 0) or 0)
                  for e in (expenses or []) if e.get("account_id") == aid)
    paid_in = sum(float(i.get("amount", 0) or 0)
                  for i in (income or []) if i.get("account_id") == aid)

    if is_liability(account):
        # A card: purchases add to the balance owed, payments reduce it.
        current = opening + charged - paid_in
    else:
        current = opening - charged + paid_in

    return {
        "account_id": aid,
        "opening": round(opening, 2),
        "charged": round(charged, 2),
        "paid_in": round(paid_in, 2),
        "current": round(current, 2),
        "is_liability": is_liability(account),
        "currency": str(account.get("currency", "usd")).upper(),
        "transactions": sum(1 for e in (expenses or []) if e.get("account_id") == aid)
                        + sum(1 for i in (income or []) if i.get("account_id") == aid),
    }


def unassigned_total(expenses: list, income: list) -> Dict[str, float]:
    """Money not charged to any account — so the gap is visible rather than silent."""
    return {
        "expenses": round(sum(float(e.get("price", 0) or 0)
                              for e in (expenses or []) if not e.get("account_id")), 2),
        "income": round(sum(float(i.get("amount", 0) or 0)
                            for i in (income or []) if not i.get("account_id")), 2),
    }


# Every field any type can add, so a leftover from a previous type is spottable.
_ALL_TYPE_FIELDS = {f for fields in ACCOUNT_TYPE_FIELDS.values() for f in fields}


def is_wrapped(blob: Any) -> bool:
    """True if this is the current two-half shape rather than a legacy file."""
    return isinstance(blob, dict) and ("finance_data" in blob or "accounts_data" in blob)


def apply_account_type(account: Dict[str, Any], fill_defaults: bool = False) -> Dict[str, Any]:
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

    # Defaults are OPT-IN. An account stores only the fields actually entered,
    # so a savings account with no monthly fee simply has no `monthly_fee` key
    # rather than a misleading 0.0 nobody typed. The form uses the defaults as
    # starting values; the record does not inherit them.
    if fill_defaults:
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

    accounts = _normalize_accounts(accounts)

    # Drop links to accounts that no longer exist. Deleting an account must not
    # leave expenses pointing at a ghost — they become unassigned, which is
    # honest, rather than silently counting towards a balance nobody can see.
    live_ids = {a.get("id") for a in accounts}
    for key in ("expenses", "income"):
        for row in finance.get(key) or []:
            if row.get("account_id") is not None and row.get("account_id") not in live_ids:
                row["account_id"] = None

    return {"finance_data": finance, "accounts_data": accounts}


def _normalize_accounts(accounts: Any) -> list:
    """Coerce the accounts half into a clean list of account records.

    Handles three shapes:
      * a list          — the current one
      * a single dict   — the shape accounts_data had when it was one account;
                          promoted to a one-item list, or dropped if it was
                          still the untouched blank
      * anything else   — treated as no accounts

    Ids are repaired here rather than trusted, because a transfer will point at
    one and a duplicate or missing id would silently retarget it.
    """
    if isinstance(accounts, dict):
        # Legacy single-account shape. An untouched blank carries nothing worth
        # keeping, so it becomes an empty list rather than a phantom account.
        meaningful = accounts.get("type") or accounts.get("name")             or accounts.get("expenses") or accounts.get("deposits")
        accounts = [accounts] if meaningful else []
    if not isinstance(accounts, list):
        return []

    cleaned, seen = [], set()
    for entry in accounts:
        if not isinstance(entry, dict):
            continue
        acc = dict(entry)
        for field, default in BLANK_ACCOUNT.items():
            if field not in acc:
                acc[field] = list(default) if isinstance(default, list) else default
        for list_field in ("expenses", "deposits"):
            if not isinstance(acc.get(list_field), list):
                acc[list_field] = []
        acc["type"] = str(acc.get("type") or "").lower()
        # Strip fields belonging to a different type, but do NOT fill defaults:
        # an account keeps only what was actually entered.
        apply_account_type(acc)
        aid = acc.get("id")
        if not isinstance(aid, int) or aid in seen:
            aid = next_account_id(cleaned)
            acc["id"] = aid
        seen.add(aid)
        cleaned.append(acc)
    return cleaned


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
    # account_id: which account this was charged to / paid into. Nullable, so
    # every existing row stays valid and using accounts stays optional.
    "expenses":           ("expenses",           [("price", "price"), ("purchased", "purchased"), ("tags", "tags"), ("date", "date"), ("currency", "currency"), ("notes", "notes"), ("account_id", "account_id")]),
    "income":             ("income",             [("amount", "amount"), ("source", "source"), ("date", "date"), ("currency", "currency"), ("notes", "notes"), ("account_id", "account_id")]),
    "budget":             ("budgets",            [("category", "category"), ("amount", "amount"), ("currency", "currency")]),
    "subscriptions":      ("subscriptions",      [("name", "name"), ("price", "price"), ("currency", "currency"), ("startDate", "start_date")]),
    "goals":              ("goals",              [("name", "name"), ("amount", "amount"), ("startDate", "start_date"), ("monthContribution", "month_contribution"), ("currency", "currency")]),
    "recurring_expenses": ("recurring_expenses", [("amount", "amount"), ("purchased", "purchased"), ("tags", "tags"), ("currency", "currency")]),
    "recurring_income":   ("recurring_income",   [("amount", "amount"), ("source", "source"), ("currency", "currency")]),
    "assets":             ("assets",             [("name", "name"), ("type", "type"), ("value", "value"), ("currency", "currency"), ("notes", "notes")]),
    "liabilities":        ("liabilities",        [("name", "name"), ("type", "type"), ("balance", "balance"), ("currency", "currency"), ("interest_rate", "interest_rate"), ("notes", "notes")]),
}


def require_tls(dsn: str) -> str:
    """Return the DSN with TLS forced on.

    libpq's default sslmode is `prefer`: it attempts TLS and SILENTLY drops to
    an unencrypted connection if the server allows one. For a connection
    carrying somebody's entire financial history that default is not good
    enough, and it fails open — you would never notice.

    `require` encrypts but does not verify the server certificate;
    `verify-full` also checks the hostname, which is what you want against a
    managed provider like Neon. Set ET_DB_SSLMODE to override (for a local
    Postgres on a socket, say).
    """
    import os as _os
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    if not dsn:
        return dsn
    mode = _os.getenv("ET_DB_SSLMODE", "require")

    # key=value form
    if "://" not in dsn:
        import re as _re
        if _re.search(r"sslmode\s*=\s*(disable|allow|prefer)", dsn, _re.I):
            return _re.sub(r"sslmode\s*=\s*\w+", f"sslmode={mode}", dsn, flags=_re.I)
        return dsn if "sslmode=" in dsn else f"{dsn} sslmode={mode}"

    parts = urlparse(dsn)
    query = parse_qs(parts.query, keep_blank_values=True)
    current = (query.get("sslmode") or [""])[0].lower()
    # `disable` and `allow` mean no encryption, or encryption only if the server
    # insists. Honouring either would make this function pointless, so they are
    # upgraded. ET_DB_SSLMODE is the deliberate escape hatch.
    if current in ("", "disable", "allow", "prefer"):
        query["sslmode"] = [mode]
        parts = parts._replace(query=urlencode(query, doseq=True))
    return urlunparse(parts)


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
        "'accounts_enc', (select accounts_enc from organizations where id = %(org)s)",
    ]
    for json_key, (table, fields) in _TABLE_SPEC.items():
        # `enc` comes back too: a row written with encryption on has its
        # values there and NULL in the typed columns. Both shapes are read
        # so a database can be migrated without downtime.
        cols = ", ".join(["id", "enc"] + [db for _, db in fields])
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
        # TLS is forced on here, not assumed from whatever was in the env var.
        self.dsn = require_tls(dsn)
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

    # -- encryption -----------------------------------------------------------

    @staticmethod
    def _enc_on() -> bool:
        """Whether at-rest encryption is configured for this deployment."""
        try:
            from .secure_store import encryption_enabled
        except ImportError:
            from secure_store import encryption_enabled
        return encryption_enabled()

    def _aad(self, table: str) -> str:
        """Context bound into every ciphertext.

        Table plus org, NOT the row id: an identity id does not exist until
        after the INSERT that would need it, and binding org+table already stops
        the attacks that matter — lifting a row into another tenant, or into a
        different table. Reordering rows inside your own org is not an attack.
        """
        return f"{table}:{self.org_id}"

    def _decode_row(self, raw: dict, table: str, fields) -> dict:
        """One stored row -> its field payload.

        Prefers `enc`. Falls back to the typed columns so rows written before
        encryption was switched on keep loading.
        """
        blob = raw.get("enc")
        if blob:
            try:
                from .secure_store import decrypt_row
            except ImportError:
                from secure_store import decrypt_row
            # psycopg hands bytea back as memoryview/bytes; via jsonb it is a
            # \x-prefixed hex string.
            if isinstance(blob, str):
                blob = bytes.fromhex(blob[2:] if blob.startswith("\\x") else blob)
            payload = decrypt_row(blob, aad=self._aad(table))
            return {jf: payload.get(jf) for jf, _db in fields}
        return {jf: raw.get(db) for jf, db in fields}

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
            # A LIST is the current shape; dict is the pre-list one. Checking
            # only for dict meant every write silently dropped the accounts —
            # they never reached the database at all.
            return inner if isinstance(inner, (dict, list)) else None
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
                    payload = self._decode_row(r, _table, fields)
                    items.append({"id": rid, **payload})
                    snap[rid] = payload
                data[json_key] = items
                snapshot[json_key] = snap
            self._snapshot = snapshot
            # Accounts hold bank names, balances and rates, so they are
            # encrypted alongside everything else. accounts_data remains for
            # rows written before encryption was switched on.
            enc_accounts = raw.get("accounts_enc")
            if enc_accounts:
                try:
                    from .secure_store import decrypt_row
                except ImportError:
                    from secure_store import decrypt_row
                blob = enc_accounts
                if isinstance(blob, str):
                    blob = bytes.fromhex(blob[2:] if blob.startswith("\\x") else blob)
                accounts = decrypt_row(blob, aad=self._aad("organizations")).get("accounts", [])
            else:
                accounts = raw.get("accounts")
            return {
                "finance_data": data,
                "accounts_data": accounts if isinstance(accounts, (dict, list)) else {},
            }

        return self._session(_do)

    def _fetch_snapshot(self, cur) -> Dict[str, Dict[int, Dict[str, Any]]]:
        """Fallback when write() is called without a preceding read()."""
        cur.execute(_READ_SQL, {"org": self.org_id})
        raw = cur.fetchone()[0]
        return {
            json_key: {
                r["id"]: self._decode_row(r, table, fields)
                for r in (raw.get(json_key) or [])
            }
            for json_key, (table, fields) in _TABLE_SPEC.items()
        }

    # -- write ----------------------------------------------------------------

    def write(self, data: Dict[str, Any]) -> None:
        from psycopg.types.json import Json

        # Unwrap before anything touches the diff — see _finance_half().
        accounts = self._accounts_half(data)
        data = self._finance_half(data)
        encrypting = self._enc_on()
        if encrypting:
            try:
                from .secure_store import encrypt_row as _encrypt_row
            except ImportError:
                from secure_store import encrypt_row as _encrypt_row

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
                    if encrypting:
                        cur.execute(
                            "update organizations set data_version = data_version + 1, "
                            "accounts_enc = %s, accounts_data = '{}'::jsonb "
                            "where id = %s and data_version = %s",
                            (_encrypt_row({"accounts": accounts},
                                          aad=self._aad("organizations")),
                             self.org_id, self._version),
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
                        # With encryption on, values go into `enc` and the typed
                        # columns are left NULL (migration 005 drops their NOT
                        # NULL). With it off, behaviour is exactly as before.
                        if encrypting:
                            col_list = ", ".join(["org_id", "created_by", "enc"])
                            tuple_sql = "(%s, %s, %s)"
                            params = []
                            for p in inserts:
                                params.extend([self.org_id, self.created_by,
                                               _encrypt_row(p, aad=self._aad(table))])
                        else:
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
                        if encrypting:
                            cur.executemany(
                                f"update {table} set enc = %s where id = %s and org_id = %s",
                                [(_encrypt_row(
                                    {jf: row[i] for i, (jf, _) in enumerate(fields)},
                                    aad=self._aad(table)), row[-2], row[-1])
                                 for row in updates],
                            )
                        else:
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
                    def _audit_payload(value, entity_table):
                        # The audit trail stores the BEFORE and AFTER of every
                        # field. Left as plain jsonb it would hold a readable
                        # copy of everything the `enc` column encrypts, which
                        # would make the encryption pointless. So it is wrapped
                        # the same way, in a shape that is obviously ciphertext.
                        if value is None:
                            return None
                        if not encrypting:
                            return Json(value)
                        import base64 as _b64
                        return Json({"enc": _b64.b64encode(
                            _encrypt_row(value, aad=self._aad(entity_table))).decode()})

                    for action, entity, entity_id, before, after in audit_rows:
                        params.extend([
                            self.org_id, self.created_by, action, entity, entity_id,
                            _audit_payload(before, entity),
                            _audit_payload(after, entity),
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
