"""Accounts — create, edit and remove the accounts money actually sits in.

The type dropdown drives the form: pick "Money market" and you get the fields an
MMA has, pick "Credit card" and you get a limit and an APR instead. Nothing is
stored unless you type it, so an account carries only the fields that mean
something for it.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import streamlit as st

from CLI.app.streamlit_setup import init_st, sync_data
from CLI.app.theme import page_setup, section, render_sidebar
from CLI.core.storage import (account_balance, unassigned_total,
                              ACCOUNT_TYPE_FIELDS, ACCOUNT_TYPE_META,
                              ACCOUNT_FIELD_CHOICES, ACCOUNT_RATE_FIELDS,
                              account_types_by_group, apply_account_type,
                              is_liability, new_account)

page_setup("Accounts", "🏦")
init_st()
render_sidebar()

st.title("🏦 Accounts")
st.caption("Where your money lives. Tie expenses, deposits and subscriptions to "
           "an account so you can see what each one is actually doing.")

tracker = st.session_state.tracker
CURRENCIES = ["usd", "eur", "gbp", "jpy", "thb", "cad", "aud", "chf", "sgd", "inr"]


def _load():
    return tracker.open_file()


def _save(accounts):
    blob = _load()
    tracker.write_file(blob["data"], accounts)
    sync_data()


# The picker: grouped so "Savings" products sit together rather than in one
# undifferentiated list. Value is the type key, label is the human name.
_GROUPED = account_types_by_group()
_TYPE_KEYS, _TYPE_LABELS = [], {}
for _group, _items in _GROUPED.items():
    for _key, _label in _items:
        _TYPE_KEYS.append(_key)
        _TYPE_LABELS[_key] = f"{_group} · {_label}"


def _field_widget(field: str, default, key: str, current=None):
    """Render one type field, choosing the widget from what the field means.

    Returns the value, or None when the user left it blank — the caller drops
    Nones so an untouched field never lands in the record.
    """
    value = current if current is not None else None
    label = field.replace("_", " ").capitalize()

    if field in ACCOUNT_FIELD_CHOICES:
        opts = ["— not set —"] + ACCOUNT_FIELD_CHOICES[field]
        idx = opts.index(value) if value in opts else 0
        picked = st.selectbox(label, opts, index=idx, key=key)
        return None if picked == opts[0] else picked

    if isinstance(default, bool):
        opts = ["— not set —", "Yes", "No"]
        idx = 0 if value is None else (1 if value else 2)
        picked = st.selectbox(label, opts, index=idx, key=key)
        return None if picked == opts[0] else (picked == "Yes")

    if field in ACCOUNT_RATE_FIELDS:
        return st.number_input(f"{label} (%)", min_value=0.0, max_value=100.0,
                               step=0.01, format="%.2f",
                               value=float(value) if value is not None else 0.0,
                               key=key,
                               help="Leave at 0 to store nothing for this field.") or None

    if isinstance(default, int) and not isinstance(default, bool):
        got = st.number_input(label, min_value=0, step=1,
                              value=int(value) if value is not None else 0, key=key)
        return got or None

    if isinstance(default, float):
        got = st.number_input(label, step=0.01, format="%.2f",
                              value=float(value) if value is not None else 0.0, key=key)
        return got or None

    got = st.text_input(label, value=str(value) if value is not None else "", key=key)
    return got.strip() or None


def _type_form(account_type: str, prefix: str, existing: dict = None):
    """Every field this type offers. Returns only the ones with a value."""
    existing = existing or {}
    fields = ACCOUNT_TYPE_FIELDS.get(account_type, {})
    if not fields:
        st.caption("Pick a type above to see the fields it carries.")
        return {}

    entered = {}
    cols = st.columns(2)
    for i, (field, default) in enumerate(fields.items()):
        with cols[i % 2]:
            if field == "currency":
                cur = existing.get("currency", "usd")
                entered["currency"] = st.selectbox(
                    "Currency", CURRENCIES,
                    index=CURRENCIES.index(cur) if cur in CURRENCIES else 0,
                    key=f"{prefix}_currency")
                continue
            got = _field_widget(field, default, f"{prefix}_{field}", existing.get(field))
            if got is not None:
                entered[field] = got
    return entered


tab_list, tab_new = st.tabs(["Your accounts", "Create an account"])

# ── Create ───────────────────────────────────────────────────────────────────
with tab_new:
    section("Create an account", "The type decides which fields you get.")

    new_type = st.selectbox(
        "Account type", _TYPE_KEYS,
        format_func=lambda k: _TYPE_LABELS.get(k, k),
        key="new_account_type",
        help="Changing this swaps the fields below.",
    )
    meta = ACCOUNT_TYPE_META.get(new_type, {})
    if meta.get("sign") == "liability":
        st.info("A credit card's balance is money **owed**, so it counts against "
                "your net worth rather than for it.", icon="💳")

    new_name = st.text_input("Account name", placeholder="e.g. Ally Online Savings",
                             key="new_account_name")

    st.divider()
    st.caption("Fill in only what applies — anything you leave alone is not stored.")
    entered = _type_form(new_type, "new")

    if st.button("Create account", type="primary", key="create_account"):
        blob = _load()
        accounts = list(blob.get("accounts") or [])
        if not new_name.strip():
            st.error("Give the account a name so you can tell it apart.")
        elif any(str(a.get("name", "")).strip().lower() == new_name.strip().lower()
                 for a in accounts):
            st.error(f"You already have an account called “{new_name.strip()}”.")
        else:
            acc = new_account(new_name.strip(), new_type, accounts)
            acc.update(entered)
            apply_account_type(acc)
            accounts.append(acc)
            _save(accounts)
            st.success(f"Created **{acc['name']}**.")
            st.rerun()

# ── List / edit ──────────────────────────────────────────────────────────────
with tab_list:
    accounts = list(_load().get("accounts") or [])

    if not accounts:
        st.info("No accounts yet — add your first on the **Create an account** tab.",
                icon="🏦")
    else:
        _blob = _load()
        _exp = _blob["data"].get("expenses") or []
        _inc = _blob["data"].get("income") or []
        _bal = {a["id"]: account_balance(a, _exp, _inc) for a in accounts}

        held = sum(b["current"] for b in _bal.values() if not b["is_liability"])
        owed = sum(b["current"] for b in _bal.values() if b["is_liability"])
        k = st.columns(3)
        k[0].metric("Held", f"{held:,.2f}")
        k[1].metric("Owed", f"{owed:,.2f}")
        k[2].metric("Net", f"{held - owed:,.2f}", delta=f"{held - owed:+,.0f}")
        st.caption("Balances are derived from what you have charged to each "
                   "account, starting from the balance you entered — so they "
                   "cannot drift away from the transactions that explain them.")

        _un = unassigned_total(_exp, _inc)
        if _un["expenses"] or _un["income"]:
            st.info(
                f"**{_un['expenses']:,.2f}** of spending and "
                f"**{_un['income']:,.2f}** of income are not assigned to any "
                "account, so they do not move a balance. Set an account when "
                "you add them, or leave them — they still count in your totals.",
                icon="\U0001F9FE",
            )
        st.divider()

        for acc in accounts:
            meta = ACCOUNT_TYPE_META.get(acc.get("type", ""), {})
            label = meta.get("label", acc.get("type") or "Not set yet")
            icon = "💳" if is_liability(acc) else "🏦"
            _b = _bal.get(acc["id"], {})
            _cur_txt = (f" · {_b.get('current', 0):,.2f} {_b.get('currency','')}"
                        + (" owed" if _b.get("is_liability") else ""))
            with st.expander(f"{icon}  {acc.get('name') or '(unnamed)'} — {label}{_cur_txt}"):
                if _b.get("transactions"):
                    m = st.columns(4)
                    m[0].metric("Opening", f"{_b['opening']:,.2f}")
                    m[1].metric("Charged", f"{_b['charged']:,.2f}")
                    m[2].metric("Paid in", f"{_b['paid_in']:,.2f}")
                    m[3].metric("Now", f"{_b['current']:,.2f}")
                    st.caption(f"{_b['transactions']} transaction(s) charged to this account.")
                else:
                    st.caption("Nothing charged to this account yet. Pick it on "
                               "the **Manage** tab when adding an expense.")
                shown = {kk: vv for kk, vv in acc.items()
                         if kk not in ("id", "name", "type", "expenses", "deposits")}
                if shown:
                    st.caption(" · ".join(
                        f"**{kk.replace('_',' ')}**: "
                        f"{vv}{'%' if kk in ACCOUNT_RATE_FIELDS else ''}"
                        for kk, vv in sorted(shown.items())))
                else:
                    st.caption("No details entered yet.")

                st.markdown("**Edit**")
                edit_type = st.selectbox(
                    "Account type", _TYPE_KEYS,
                    index=_TYPE_KEYS.index(acc["type"]) if acc.get("type") in _TYPE_KEYS else 0,
                    format_func=lambda k: _TYPE_LABELS.get(k, k),
                    key=f"edit_type_{acc['id']}")
                edit_name = st.text_input("Account name", value=acc.get("name", ""),
                                          key=f"edit_name_{acc['id']}")

                if edit_type != acc.get("type"):
                    probe = apply_account_type({**acc, "type": edit_type})
                    if probe["removed"]:
                        st.warning(
                            "Switching type will drop: "
                            + ", ".join(f"**{kk.replace('_',' ')}** ({vv})"
                                        for kk, vv in probe["removed"].items()),
                            icon="⚠️")

                edited = _type_form(edit_type, f"edit_{acc['id']}", acc)

                c_save, c_del, _ = st.columns([1, 1, 3])
                if c_save.button("Save changes", key=f"save_{acc['id']}", type="primary"):
                    updated = {"id": acc["id"], "name": edit_name.strip() or acc.get("name", ""),
                               "type": edit_type,
                               "expenses": acc.get("expenses", []),
                               "deposits": acc.get("deposits", [])}
                    updated.update(edited)
                    apply_account_type(updated)
                    _save([updated if a["id"] == acc["id"] else a for a in accounts])
                    st.success("Saved.")
                    st.rerun()

                if c_del.button("Delete", key=f"del_{acc['id']}"):
                    st.session_state["_del_account"] = acc["id"]

                if st.session_state.get("_del_account") == acc["id"]:
                    st.warning(f"Delete **{acc.get('name')}**? This cannot be undone.",
                               icon="⚠️")
                    y, n, _ = st.columns([1, 1, 3])
                    if y.button("Yes, delete", key=f"confirm_del_{acc['id']}", type="primary"):
                        _save([a for a in accounts if a["id"] != acc["id"]])
                        st.session_state.pop("_del_account", None)
                        st.rerun()
                    if n.button("Cancel", key=f"cancel_del_{acc['id']}"):
                        st.session_state.pop("_del_account", None)
                        st.rerun()
