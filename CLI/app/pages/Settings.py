"""Settings — account, storage mode, and data export.

This page owns the pivot between the two ways the product runs:

  LOCAL  (free, self-hosted)  data.json on this machine. No account.
  PUBLIC (paid, Matt-hosted)  the user's organization in Neon. REQUIRES an
                              account saved here plus an entitlement bought
                              from the GRID store.

Switching either direction is done from this page, and offers to carry the
data across so nothing is stranded in the mode you left.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import streamlit as st

from CLI.app.theme import page_setup, section, render_sidebar
from CLI.app.streamlit_setup import init_st, sync_data
from CLI.app.config import DATABASE_URL, STORE_URL, LICENSE_STORE_URL
from CLI.core.core_stuff import ExpenseTracker
from CLI.core.storage import JsonStore, PostgresStore, normalize_blob
from CLI.core.tenancy import (AuthUser, NoEntitlementError, claim_and_resolve_org,
                              create_org, get_role)

page_setup("Settings — Finance Kit", "⚙️")
init_st()

render_sidebar()
LISTS = ["expenses", "income", "budget", "subscriptions", "goals",
         "recurring_expenses", "recurring_income", "assets", "liabilities"]


def _tracker() -> ExpenseTracker:
    return st.session_state.tracker


def _is_hosted() -> bool:
    return isinstance(getattr(_tracker(), "store", None), PostgresStore)


def _saved_account():
    """The account saved on this device, if any."""
    acct = st.session_state.get("account")
    if acct:
        return AuthUser(user_id=acct["user_id"], email=acct["email"], name=acct.get("name"))
    return None


# ══════════════════════════════════════════════════════════════════════════
tab_account, tab_mode, tab_privacy, tab_export = st.tabs(
    ["Account", "Storage", "Privacy & encryption", "Export & Backup"])

# ── ACCOUNT ──────────────────────────────────────────────────────────────
with tab_account:
    section("Account",
            "An account is required only for the public (hosted) site. "
            "Running locally needs no account at all.")

    user = _saved_account()
    if user:
        st.success(f"Signed in as **{user.email}**")
        c1, c2 = st.columns(2)
        with c1:
            if st.session_state.get("org_id"):
                st.metric("Organization", f"#{st.session_state['org_id']}")
        with c2:
            if st.session_state.get("role"):
                st.metric("Role", st.session_state["role"].title())
        if st.session_state.get("role") == "viewer":
            st.info("You have **viewer** access — this workspace is read-only for you.")
        if st.button("Sign out", type="secondary"):
            for k in ("account", "org_id", "role", "tracker"):
                st.session_state.pop(k, None)
            st.rerun()
    else:
        st.caption("Save an account to unlock the hosted site.")
        with st.form("save_account"):
            email = st.text_input("Email", placeholder="you@company.com",
                                  help="Must match the email used at purchase.")
            uid = st.text_input(
                "User ID (optional)", placeholder="leave blank to use your email",
                help="If you sign in with an identity provider, paste its user id. "
                     "Otherwise your email is used as a stable id.")
            submitted = st.form_submit_button("Save account", type="primary")
        if submitted:
            email = (email or "").strip().lower()
            if "@" not in email:
                st.error("Enter a valid email address.")
            else:
                st.session_state["account"] = {
                    "user_id": (uid or "").strip() or email,
                    "email": email,
                    "name": None,
                }
                st.success("Account saved on this device.")
                st.rerun()

        st.divider()
        st.caption(
            "Don't have hosted access yet? Buy it in the GRID store — your "
            "entitlement is linked to the email you purchase with.")
        st.link_button("Get hosted access", STORE_URL, type="primary")

# ── STORAGE MODE ─────────────────────────────────────────────────────────
with tab_mode:
    hosted = _is_hosted()
    section("Where your data lives",
            "Switch between running locally for free and using the hosted site.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Local** — free, self-hosted")
        st.caption("Stored in `data.json` on this machine. Works offline. No account.")
        st.write("✅ Active" if not hosted else "○ Inactive")
    with c2:
        st.markdown("**Public site** — hosted")
        st.caption("Your organization's data in the cloud, shared with your team.")
        st.write("✅ Active" if hosted else "○ Inactive")

    st.divider()
    user = _saved_account()

    if not hosted:
        section("Switch to the public site")
        if not user:
            st.warning("Save an account on the **Account** tab first — the public "
                       "site requires one.")
        elif not DATABASE_URL:
            st.error("This build has no hosted database configured "
                     "(`ET_DATABASE_URL` is unset).")
        else:
            copy_up = st.checkbox(
                "Copy my local data to the hosted workspace", value=True,
                help="Appends everything in data.json to your organization. "
                     "Your local file is left untouched.")
            if st.button("Switch to hosted", type="primary"):
                try:
                    org_id, claimed = claim_and_resolve_org(DATABASE_URL, user)
                    if org_id is None:
                        raise NoEntitlementError(
                            f"No active hosted subscription for {user.email}.")
                    local_loaded = _tracker().open_file() if copy_up else None
                    store = PostgresStore(DATABASE_URL, org_id=org_id,
                                          created_by=user.user_id)
                    if copy_up and local_loaded:
                        local_data = local_loaded["data"]
                        # store.read() returns the WRAPPED blob. Merging into it
                        # directly put the lists at the top level, where write()
                        # never looked — the copy silently moved nothing.
                        cloud_blob = store.read()
                        cloud = cloud_blob.get("finance_data") or {}
                        for key in LISTS:
                            merged = list(cloud.get(key) or [])
                            for item in local_data.get(key) or []:
                                merged.append({k: v for k, v in item.items() if k != "id"})
                            cloud[key] = merged
                        # Carry the local accounts up only if the org has none yet,
                        # so switching modes can't clobber an existing workspace.
                        cloud_accounts = cloud_blob.get("accounts_data") or {}
                        if not cloud_accounts.get("type"):
                            cloud_accounts = local_loaded.get("accounts") or cloud_accounts
                        store.write({"finance_data": cloud,
                                     "accounts_data": cloud_accounts})
                    st.session_state.tracker = ExpenseTracker(store=store)
                    st.session_state.org_id = org_id
                    st.session_state.role = get_role(DATABASE_URL, org_id, user)
                    for k in LISTS:
                        st.session_state.pop(k, None)
                    init_st()
                    st.success(f"Now using the hosted workspace (org #{org_id}).")
                    st.rerun()
                except NoEntitlementError as exc:
                    st.error(str(exc))
                    st.link_button("Get hosted access", STORE_URL, type="primary")
                except Exception as exc:
                    st.error(f"Could not switch: {exc}")
    else:
        section("Switch back to local")
        copy_down = st.checkbox(
            "Download a copy of the hosted data into my local file", value=True,
            help="Overwrites data.json with what's currently in the cloud.")
        if st.button("Switch to local", type="primary"):
            try:
                cloud_loaded = _tracker().open_file() if copy_down else None
                local = ExpenseTracker(store=JsonStore("data.json"))
                if copy_down and cloud_loaded:
                    # Bring the accounts down with the lists, not just the lists.
                    local.write_file(cloud_loaded["data"],
                                     cloud_loaded.get("accounts"))
                st.session_state.tracker = local
                for k in ("org_id", "role", *LISTS):
                    st.session_state.pop(k, None)
                init_st()
                st.success("Switched back to local storage.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not switch: {exc}")

# ── PRIVACY & ENCRYPTION ─────────────────────────────────────────────────
with tab_privacy:
    section("What leaves this machine",
            "Written to match what the code actually does. If it says nothing "
            "is sent, nothing is sent.")

    st.markdown("**Running locally (free / self-hosted)**")
    st.success(
        "Your finances never leave this computer. Expenses, income, budgets, "
        "goals, accounts — all of it lives in `data.json` here. Every figure on "
        "the dashboard, including the forecast, the anomaly scan and net worth, "
        "is calculated **on this machine**.",
        icon="🔒",
    )
    st.caption(
        "Those three used to be sent to the analytics server to be computed. "
        "They are pure arithmetic and needed no server, so they were moved back "
        "here — the data no longer goes anywhere to produce them."
    )

    st.divider()
    st.markdown("**The one thing that is sent, and only when you ask**")
    st.warning(
        "**Ask About Your Finances** is the single feature that transmits your "
        "records. Answering a question in plain English needs a language model, "
        "and that model runs on a server. Pressing Ask sends a summary of your "
        "expenses, income, budgets, subscriptions and goals to the AI provider "
        "configured for this build.\n\n"
        "Nothing is sent unless you press it. If you never use it, nothing "
        "ever leaves.",
        icon="🤖",
    )

    st.divider()
    st.markdown("**Stored credentials**")
    _cred_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".bot_config.json"))
    _has_creds = os.path.exists(_cred_path)
    try:
        from CLI.core.secure_store import is_encrypted as _is_enc
        import json as _json
        _enc = _has_creds and _is_enc(_json.load(open(_cred_path, encoding="utf-8")))
    except Exception:
        _enc = False
    if not _has_creds:
        st.caption("No stored credentials yet. Phone Connect and Email Import "
                   "save theirs encrypted when you configure them.")
    elif _enc:
        st.success("Your Gmail app password and bot tokens are **encrypted at "
                   "rest** (AES-256-GCM). The key is held in a separate file, so "
                   "neither one is useful on its own.", icon="🔑")
    else:
        st.warning("Credentials are still stored in plain text from an older "
                   "build. Re-save them on Phone Connect or Email Import and "
                   "they will be encrypted.", icon="⚠️")
    st.caption(
        "Being straight about the limit: the app has to decrypt these "
        "unattended so the bots can run, so the key sits on this machine. That "
        "protects the file if it is synced to OneDrive, lands in a backup, or "
        "is committed by accident — it does not protect against someone who "
        "already has your user account."
    )

    st.divider()
    section("Server-side encryption",
            "Applies only if you sign up for the hosted site.")
    st.markdown(
        "Using the hosted site is the **only** way any of your finances reach a "
        "server for storage. It is opt-in: you create an account on the "
        "**Account** tab and switch over on **Storage**. Until you do that, "
        "there is no server copy of anything."
    )
    st.markdown("**In transit**")
    st.success(
        "Every connection is encrypted, and now enforced rather than assumed. "
        "The app refuses a non-https backend URL (localhost excepted, for "
        "development), and the database connection has TLS forced on. libpq "
        "defaults to `prefer`, which quietly drops to an unencrypted "
        "connection if the server permits one \u2014 that default is now overridden.",
        icon="\U0001F510",
    )

    st.markdown("**At rest**")
    try:
        from CLI.core.secure_store import encryption_enabled as _enc_on
        _on = _enc_on()
    except Exception:
        _on = False
    if _on:
        st.success(
            "Encryption key configured. Hosted rows are stored as AES-256-GCM "
            "ciphertext.",
            icon="\U0001F510",
        )
    else:
        st.info(
            "**Key not configured on this deployment.** The encryption layer "
            "and the migration are written "
            "(`db/migrations/005_encrypt_at_rest.sql`), but hosted storage will "
            "not encrypt until `ET_ENCRYPTION_KEY` is set. Local mode is "
            "unaffected \u2014 it never uploads anything to encrypt.",
            icon="\U0001F3D7",
        )
    st.caption(
        "Each row is encrypted with its table and id bound into the ciphertext, "
        "so a row cannot be lifted from one table or organisation and replayed "
        "into another. Tampering is detected rather than silently decrypting "
        "to nonsense."
    )

    with st.expander("What this does and does not protect"):
        st.markdown(
            "**Protects:** a leaked database credential, a stolen or copied "
            "backup, a snapshot that ends up somewhere it should not, or "
            "anyone with read access to the database. In every one of those "
            "cases the rows are ciphertext."
        )
        st.markdown(
            "**Does not protect against the application itself.** Finance Kit "
            "holds the key, because the server has to compute net worth, "
            "forecasts and anomalies for hosted users \u2014 it cannot total "
            "what it cannot read. This is encryption at rest, not "
            "zero-knowledge: anyone with both the database *and* the app's key "
            "can read the data."
        )
        st.markdown(
            "That is a deliberate trade, and it is why there is no passphrase. "
            "A passphrase-derived key would mean the server could compute "
            "nothing for you, and losing the passphrase would mean losing the "
            "data outright, with no reset possible."
        )


# ── EXPORT ───────────────────────────────────────────────────────────────
with tab_export:
    section("Export & backup",
            "Take your data with you. Everything here works in both modes.")

    _loaded = _tracker().open_file()
    data = _loaded["data"]
    accounts = _loaded.get("accounts") or {}
    counts = {k: len(data.get(k) or []) for k in LISTS}
    st.caption(" · ".join(f"{k.replace('_', ' ')}: **{v}**"
                          for k, v in counts.items() if v))
    if not any(counts.values()):
        st.info("Nothing to export yet.")

    st.markdown("**Full backup**")
    st.caption("Every list plus your accounts, in one JSON file — the same "
               "format the app stores, so it restores exactly.")
    # Export the WHOLE blob, not just the finance half. Exporting only the lists
    # silently dropped accounts from a file labelled "full backup".
    st.download_button(
        "Download full backup (.json)",
        data=json.dumps({"finance_data": data, "accounts_data": accounts},
                        indent=2, default=str),
        file_name="grid-expense-backup.json",
        mime="application/json",
        type="primary",
    )

    st.divider()
    st.markdown("**Spreadsheet export**")
    which = st.selectbox("List", [k for k in LISTS if counts.get(k)] or LISTS,
                         format_func=lambda s: s.replace("_", " ").title())
    rows = data.get(which) or []
    if rows:
        import pandas as pd
        df = pd.DataFrame(rows)
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        st.download_button(f"Download {which}.csv", data=buf.getvalue(),
                           file_name=f"{which}.csv", mime="text/csv")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("This list is empty.")

    st.divider()
    st.markdown("**Restore from backup**")
    st.caption("Replaces everything in the CURRENT mode "
               f"({'hosted workspace' if _is_hosted() else 'local file'}).")
    up = st.file_uploader("Backup file", type=["json"], label_visibility="collapsed")
    if up is not None:
        try:
            # normalize_blob accepts BOTH the wrapped shape and the older flat
            # one. Reading raw keys off `incoming` only worked for flat files —
            # uploading the app's own data.json found nothing in every list and
            # silently overwrote everything with empties, reporting success.
            incoming = normalize_blob(json.load(up))
            incoming_data = incoming["finance_data"]
            incoming_accounts = incoming["accounts_data"]
            found = {k: len(incoming_data.get(k) or []) for k in LISTS}
            if any(found.values()):
                st.write("Found: " + ", ".join(f"{k} ({v})" for k, v in found.items() if v))
            else:
                st.warning("That file contains no records. Restoring it would "
                           "empty this workspace.", icon="⚠️")
            if incoming_accounts.get("type"):
                st.write(f"Account type in file: **{incoming_accounts['type']}**")
            if st.button("Restore — overwrite current data", type="primary"):
                merged = {k: incoming_data.get(k) or [] for k in LISTS}
                _tracker().write_file(merged, incoming_accounts)
                for k in LISTS:
                    st.session_state.pop(k, None)
                init_st()
                st.success("Restored.")
                st.rerun()
        except json.JSONDecodeError:
            st.error("That isn't valid JSON.")
        except Exception as exc:
            st.error(f"Could not restore: {exc}")

    st.divider()
    st.markdown("**Tidy up**")
    st.caption("Scans a list for rows that are identical in every field and "
               "removes the extras. Moved here from the dashboard — it is "
               "maintenance, not something you read at a glance.")
    dup_cols = st.columns(4)
    for i, dup_list in enumerate(["expenses", "income", "subscriptions", "goals"]):
        if dup_cols[i].button(f"De-duplicate {dup_list}", key=f"dedup_{dup_list}"):
            res = _tracker().check_for_duplicates(dup_list)
            if res["success"]:
                st.success(res["message"])
                for k in LISTS:
                    st.session_state.pop(k, None)
                init_st()
                st.rerun()
            else:
                st.info(res["message"])
