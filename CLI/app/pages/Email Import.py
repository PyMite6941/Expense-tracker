import json
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from CLI.app.streamlit_setup import init_st, sync_data
from CLI.core.core_stuff import ExpenseTracker

init_st()

st.set_page_config(page_title='Email Import', page_icon='📧')
st.title('📧 Email Import')
st.caption('Automatically find purchase receipts in your inbox and import them — Max feature.')

# ── License gate ───────────────────────────────────────────────────────────────

_features = st.session_state.get('pro_features', [])
if 'email_parsing' not in _features:
    st.warning(
        '**Email Import requires a Max license.**\n\n'
        'Activate your Max license key on the ⭐ Pro Features page to unlock this.'
    )
    st.stop()

# ── Config persistence (stored in .bot_config.json alongside phone connect) ────

_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '.bot_config.json')
)


def _load_cfg() -> dict:
    try:
        if os.path.exists(_CONFIG_PATH):
            return json.loads(open(_CONFIG_PATH).read())
    except Exception:
        pass
    return {}


def _save_cfg(cfg: dict) -> None:
    with open(_CONFIG_PATH, 'w') as fh:
        json.dump(cfg, fh, indent=2)


cfg = _load_cfg()

# ── Email credentials ──────────────────────────────────────────────────────────

st.subheader('Email Account')

IMAP_PRESETS = {
    'Gmail':         ('imap.gmail.com',      993),
    'Outlook/Hotmail': ('outlook.office365.com', 993),
    'Yahoo Mail':    ('imap.mail.yahoo.com',  993),
    'iCloud':        ('imap.mail.me.com',     993),
    'Custom':        ('',                      993),
}

preset = st.selectbox('Email provider', list(IMAP_PRESETS.keys()),
                      index=0, help='Select your provider to auto-fill the IMAP server.')

default_server, default_port = IMAP_PRESETS[preset]

with st.form('email_config_form'):
    col1, col2 = st.columns([3, 1])
    imap_server = col1.text_input('IMAP Server',
                                  value=cfg.get('email_imap_server', default_server) or default_server)
    imap_port   = col2.number_input('Port', value=cfg.get('email_imap_port', default_port) or default_port,
                                    min_value=1, max_value=65535, step=1)
    email_addr  = st.text_input('Email Address', value=cfg.get('email_address', ''))
    email_pass  = st.text_input(
        'Password / App Password',
        value=cfg.get('email_password', ''),
        type='password',
        help='For Gmail/Yahoo/Outlook, generate an **App Password** instead of using your main password.',
    )
    days_back   = st.slider('Scan last N days', min_value=7, max_value=180, value=30)
    max_emails  = st.number_input('Max emails to scan', min_value=10, max_value=500, value=150, step=10)
    save_btn    = st.form_submit_button('Save & Scan', type='primary')

with st.expander('Gmail App Password instructions', expanded=False):
    st.markdown(
        """
1. Go to your Google Account → **Security**.
2. Under *How you sign in to Google*, choose **2-Step Verification** (must be enabled).
3. At the bottom of the page, select **App passwords**.
4. Choose *Mail* + *Windows Computer* (or any device), click **Generate**.
5. Copy the 16-character password shown and paste it above.
        """
    )

# ── Scan emails ────────────────────────────────────────────────────────────────

if save_btn:
    if not imap_server or not email_addr or not email_pass:
        st.error('Please fill in the IMAP server, email address, and password.')
        st.stop()

    # Persist credentials
    cfg.update({
        'email_imap_server': imap_server,
        'email_imap_port':   int(imap_port),
        'email_address':     email_addr,
        'email_password':    email_pass,
    })
    _save_cfg(cfg)

    with st.spinner(f'Connecting to {imap_server} and scanning up to {max_emails} emails from the last {days_back} days…'):
        try:
            # Import from the backend module
            backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)
            from email_parser import fetch_expense_emails

            found = fetch_expense_emails(
                imap_server=imap_server,
                imap_port=int(imap_port),
                email_address=email_addr,
                password=email_pass,
                days_back=days_back,
                max_emails=int(max_emails),
            )
            st.session_state['email_import_results'] = found
        except ConnectionError as exc:
            st.error(f'Connection failed: {exc}')
            st.stop()
        except Exception as exc:
            st.error(f'Scan error: {exc}')
            st.stop()

# ── Display and import results ─────────────────────────────────────────────────

results = st.session_state.get('email_import_results')

if results is None:
    st.info('Configure your email credentials above and click **Save & Scan** to find receipts.')
    st.stop()

if not results:
    st.success('No receipt-like emails found in the selected period.', icon='✅')
    st.stop()

st.success(f'Found **{len(results)}** potential expense(s). Review and select which to import.', icon='📬')

# Build a displayable dataframe (strip internal _ keys)
_display_cols = ['_select', 'date', 'purchased', 'price', 'currency', 'tags', '_subject', '_from']

rows = []
for r in results:
    rows.append({
        'date':      r['date'],
        'purchased': r['purchased'],
        'price':     r['price'],
        'currency':  r['currency'],
        'tags':      r['tags'],
        'subject':   r.get('_subject', ''),
        'from':      r.get('_from', ''),
    })

df = pd.DataFrame(rows)

st.markdown('**Select expenses to import:**')

# Per-row checkboxes via data editor
edited = st.data_editor(
    df,
    use_container_width=True,
    num_rows='fixed',
    column_config={
        'price':    st.column_config.NumberColumn('Amount', format='%.2f'),
        'date':     st.column_config.TextColumn('Date'),
        'tags':     st.column_config.SelectboxColumn(
            'Category',
            options=['Food','Shopping','Travel','Subscriptions','Utilities',
                     'Healthcare','Education','Entertainment','Other'],
        ),
    },
    key='email_import_editor',
)

# Let user pick rows via a multi-select below the table
selected_indices = st.multiselect(
    'Select rows to import (by row number, 0-indexed)',
    options=list(range(len(results))),
    default=list(range(len(results))),
    format_func=lambda i: f"{rows[i]['date']}  {rows[i]['purchased']}  {rows[i]['price']:.2f} {rows[i]['currency']}",
)

col_import, col_clear = st.columns([1, 5])

with col_import:
    if st.button('Import Selected', type='primary', disabled=not selected_indices):
        tracker: ExpenseTracker = st.session_state.get('tracker') or ExpenseTracker()
        imported = 0
        errors = []
        for idx in selected_indices:
            row = edited.iloc[idx]
            try:
                result = tracker.add_expenses(
                    price=float(row['price']),
                    purchased=str(row['purchased']),
                    tags=str(row['tags']),
                    currency=str(row['currency']).lower(),
                    date=str(row['date']),
                    notes=results[idx].get('notes', 'Imported from email'),
                )
                if result.get('success'):
                    imported += 1
                else:
                    errors.append(f"Row {idx}: {result.get('message')}")
            except Exception as exc:
                errors.append(f"Row {idx}: {exc}")

        if imported:
            st.success(f'Imported {imported} expense(s) successfully.', icon='✅')
            sync_data()
            st.session_state.pop('email_import_results', None)
            st.rerun()
        if errors:
            for e in errors:
                st.error(e)

with col_clear:
    if st.button('Clear Results'):
        st.session_state.pop('email_import_results', None)
        st.rerun()
