"""Statements — import a bank or card CSV export.

Flow: upload -> preview (auto-detected columns, cleaned merchant names,
categories, duplicates flagged) -> edit in the table -> import in one write.
Everything runs locally; nothing about the statement leaves the machine.
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pandas as pd
import streamlit as st

from CLI.app.streamlit_setup import init_st, sync_data
from CLI.app.theme import page_setup, render_sidebar, section, upsell

page_setup("Import statement", "🧾")
init_st()
render_sidebar()

st.title("🧾 Import a bank statement")
st.caption("Drop in the CSV your bank or card exports. Columns, date format and "
           "signs are detected for you; merchants are cleaned up and categorized; "
           "anything you've already imported is skipped. Processed on your device.")

tracker = st.session_state.tracker
CURRENCIES = ["usd", "eur", "gbp", "cad", "aud", "jpy", "thb", "chf", "sgd", "inr", "nzd", "sek"]

up = st.file_uploader("Statement (.csv)", type=["csv", "txt"])

with st.expander("Options", expanded=False):
    c1, c2, c3 = st.columns(3)
    currency = c1.selectbox("Currency", CURRENCIES, format_func=str.upper)
    accounts = st.session_state.get("accounts_list") or []
    acct_opts = [None] + [a.get("id") for a in accounts]
    acct_names = {a.get("id"): a.get("name") or f"Account {a.get('id')}" for a in accounts}
    account_id = c2.selectbox("Charge to account", acct_opts,
                              format_func=lambda i: "— none —" if i is None else acct_names[i])
    date_choice = c3.radio("Date order", ["Auto", "Month first (US)", "Day first"],
                           horizontal=False)
    sign_choice = st.radio("Amounts", ["Auto", "Purchases are negative (bank account)",
                                       "Purchases are positive (credit card)"], horizontal=True)

dayfirst = {"Auto": None, "Month first (US)": False, "Day first": True}[date_choice]
outflow_positive = {"Auto": None, "Purchases are negative (bank account)": False,
                    "Purchases are positive (credit card)": True}[sign_choice]

if not up:
    section("Works with", "Any bank that exports CSV")
    st.markdown(
        "- A single **Amount** column, or separate **Debit / Credit** (Money out / Money in)\n"
        "- US, UK and European formats — `01/31/2026`, `31/01/2026`, `2026-01-31`, `1.234,56`\n"
        "- Header rows don't need to be on line 1 — account details above them are skipped\n"
        "- Categories learn from you: re-tag a merchant once and future imports follow")
    st.stop()

raw = up.getvalue()
key = hashlib.sha256(raw + repr((dayfirst, outflow_positive)).encode()).hexdigest()
if st.session_state.get("_stmt_key") != key:
    st.session_state["_stmt_key"] = key
    st.session_state["_stmt_preview"] = tracker.preview_bank_statement(
        raw, dayfirst=dayfirst, outflow_positive=outflow_positive)
preview = st.session_state["_stmt_preview"]

if not preview["success"]:
    st.error(f"Couldn't read this file: {preview['message']}")
    st.info("Check that it's the CSV export (not a PDF statement) and that it has a "
            "date column and an amount or debit/credit column.")
    st.stop()

meta = preview["meta"]
txns = preview["transactions"]
if meta["ambiguous_dates"]:
    st.warning("Dates like 03/04 could be March 4 or 3 April. We read them as "
               "**month first**; change *Date order* under Options if that's wrong.", icon="📅")
if meta["sign_guessed"]:
    st.warning("Most amounts are positive, so this looks like a **credit-card** export "
               "and purchases were treated as money out. Change *Amounts* under Options "
               "if that's wrong.", icon="↕️")
if meta["currency"] and meta["currency"] != currency:
    st.info(f"The file says its currency is {meta['currency'].upper()}; that will be used.")

out_total = sum(-t["amount"] for t in txns if t["amount"] < 0 and not t["duplicate"])
in_total = sum(t["amount"] for t in txns if t["amount"] > 0 and not t["duplicate"])
m = st.columns(5)
m[0].metric("Transactions", len(txns))
m[1].metric("Money out", f"{out_total:,.2f}")
m[2].metric("Money in", f"{in_total:,.2f}")
m[3].metric("Already imported", meta["duplicates"])
m[4].metric("Uncategorized", meta["uncategorized"])

df = pd.DataFrame(txns)
df.insert(0, "include", ~df["duplicate"])
df["date"] = pd.to_datetime(df["date"])
SOURCE_LABEL = {"rule": "Your rule", "history": "Learned", "bank": "Bank",
                "keyword": "Auto", "none": "—"}
df["how"] = df["category_source"].map(SOURCE_LABEL)

edited = st.data_editor(
    df[["include", "date", "merchant", "amount", "category", "how", "duplicate", "description"]],
    hide_index=True, width='stretch', num_rows="fixed",
    column_config={
        "include": st.column_config.CheckboxColumn("Import", width="small"),
        "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
        "merchant": st.column_config.TextColumn("Name"),
        "amount": st.column_config.NumberColumn("Amount", format="%.2f",
                                                help="Negative = money out"),
        "category": st.column_config.TextColumn("Category"),
        "how": st.column_config.TextColumn("Categorized by", disabled=True, width="small"),
        "duplicate": st.column_config.CheckboxColumn("Seen before", disabled=True, width="small"),
        "description": st.column_config.TextColumn("Bank's text", disabled=True),
    },
    key=f"stmt_editor_{key[:12]}",
)

if meta["uncategorized"] and not set(st.session_state.get("pro_features", [])) & {"advanced_categorization"}:
    upsell("AI categorization", "Pro",
           detail=f"{meta['uncategorized']} transactions didn't match a rule. Pro sorts the "
                  "leftovers with AI and explains your spending patterns.")

n_selected = int(edited["include"].sum())
if st.button(f"Import {n_selected} transactions", type="primary", disabled=n_selected == 0):
    rows = []
    for orig, (_, e) in zip(txns, edited.iterrows()):
        rows.append({**orig,
                     "include": bool(e["include"]),
                     "duplicate": False,  # the user decided via the checkbox
                     "date": pd.Timestamp(e["date"]).strftime("%Y-%m-%d"),
                     "merchant": str(e["merchant"] or orig["merchant"]),
                     "amount": float(e["amount"]),
                     "category": str(e["category"] or "Uncategorized")})
    result = tracker.commit_bank_import(rows, meta["currency"] or currency, account_id,
                                        source_name=up.name)
    sync_data()
    st.session_state.pop("_stmt_key", None)
    st.success(result["message"])
    st.page_link("pages/Monthly Summary.py", label="See this month's budget vs actual →", icon="📅")

if meta["skipped_rows"]:
    st.caption(f"Skipped {len(meta['skipped_rows'])} non-transaction line(s) "
               f"(e.g. totals or pending items): rows {', '.join(map(str, meta['skipped_rows'][:10]))}"
               + ("…" if len(meta["skipped_rows"]) > 10 else ""))
st.caption("Columns used: " + ", ".join(f"{k} → “{v}”" for k, v in meta["columns"].items())
           + f" · date format {meta['date_format']}")
