"""
Expense Tracker — published single-file Streamlit app.
Uses st.navigation() so the entire app lives in this one file.
Deploy this file (or the published/ directory) to Streamlit Cloud.
"""
import datetime as _dt
import json
import os
import sys

import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st

# ── Path bootstrap (allows importing CLI.core from the repo root) ──────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_BACKEND = os.path.join(_ROOT, 'backend')
for _p in (_ROOT, _BACKEND, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from CLI.core.core_stuff import ExpenseTracker  # noqa: E402

# ── Cloud endpoints ────────────────────────────────────────────────────────────
CLOUD_BACKEND = "https://expense-backend-690527435721.us-central1.run.app"
CLOUD_AUTH    = "https://auth-service-690527435721.us-central1.run.app"

# ── Shared constants ───────────────────────────────────────────────────────────
CURRENCIES = ['USD','EUR','GBP','JPY','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','BTC','ETH','Other']
CATEGORIES = ['Food','Transport','Entertainment','Utilities','Bills','Shopping','Health','Travel','Subscriptions','Education','Other']

# ══════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_tracker() -> ExpenseTracker:
    if 'tracker' not in st.session_state:
        import tempfile
        fd, path = tempfile.mkstemp(suffix='.json', prefix='pub_expense_')
        os.close(fd)
        st.session_state.pub_data_file = path
        st.session_state.tracker = ExpenseTracker(filename=path)
    return st.session_state.tracker


def _load_key(key: str) -> list:
    t = _get_tracker()
    loaders = {
        'expenses':           t.view_total_expenses,
        'income':             t.view_income,
        'budget':             t.view_all_budget,
        'subscriptions':      t.view_subscriptions,
        'goals':              t.view_all_goals,
        'recurring_expenses': t.view_recurring_expenses,
        'recurring_income':   t.view_recurring_income,
        'assets':             t.view_assets,
        'liabilities':        t.view_liabilities,
    }
    try:
        res = loaders[key]()
        return res['data'] if res.get('success') else []
    except Exception:
        return []


_DATA_KEYS = ['expenses','income','budget','subscriptions','goals',
              'recurring_expenses','recurring_income','assets','liabilities']


def _init():
    """Populate session state; call at the top of every page function."""
    _get_tracker()
    for k in _DATA_KEYS:
        if k not in st.session_state:
            st.session_state[k] = _load_key(k)
    if 'current_month' not in st.session_state:
        st.session_state.current_month = _dt.datetime.now().strftime('%Y-%m')
    if 'pro_features' not in st.session_state and st.session_state.get('pro_token'):
        _restore_license()


def _sync():
    # Only drop the cached data lists, NOT the tracker — dropping tracker would
    # cause _get_tracker() to create a brand-new temp file and lose all data.
    for k in _DATA_KEYS:
        st.session_state.pop(k, None)
    _init()


def _restore_license():
    try:
        r = requests.post(f'{CLOUD_AUTH}/validate',
                          json={'token': st.session_state['pro_token']}, timeout=5)
        if r.ok:
            d = r.json()
            st.session_state.update({
                'pro_features': d.get('features', []),
                'pro_tier':     d.get('tier', 'pro'),
                'pro_email':    d.get('email', ''),
            })
    except Exception:
        pass


def _has(feature: str) -> bool:
    return feature in st.session_state.get('pro_features', [])


def _require(feature: str, label: str = 'Pro'):
    if not _has(feature):
        st.warning(f'**This feature requires a {label} license.**\n\nGo to ⚙️ Settings → License to activate your key.', icon='🔒')
        st.stop()


def _api(endpoint: str, payload: dict, token: str = None, timeout: int = 30):
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    try:
        return requests.post(f'{CLOUD_BACKEND}{endpoint}', json=payload,
                             headers=headers, timeout=timeout)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return None


def _export_json() -> bytes:
    return json.dumps(_get_tracker().open_file()['data'], indent=2).encode()


def _import_json(raw: bytes):
    _get_tracker().write_file(json.loads(raw))
    _sync()


def _license_badge():
    tier  = st.session_state.get('pro_tier', '')
    email = st.session_state.get('pro_email', '')
    if tier:
        icon = '👑' if tier == 'max' else '⭐'
        st.sidebar.success(f'{icon} {tier.upper()} — {email}')
    else:
        st.sidebar.info('No license active.\nGo to ⚙️ Settings to activate.', icon='🔒')


def _cfg_path() -> str:
    return os.path.join(_ROOT, '.bot_config.json')


def _load_cfg() -> dict:
    p = _cfg_path()
    try:
        if os.path.exists(p):
            with open(p) as f:
                return json.loads(f.read())
    except Exception:
        pass
    return {}


def _save_cfg(cfg: dict):
    with open(_cfg_path(), 'w') as f:
        json.dump(cfg, f, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def page_home():
    _init(); _license_badge()
    st.title('💰 Expense Tracker')
    st.caption('Track income, expenses, budgets, goals, and subscriptions — all in one place.')

    cm    = st.session_state.current_month
    label = _dt.datetime.strptime(cm, '%Y-%m').strftime('%B %Y')
    m_exp = [e for e in st.session_state.expenses if e.get('date','').startswith(cm)]
    m_inc = [i for i in st.session_state.income   if i.get('date','').startswith(cm)]
    te    = sum(e.get('price',0) for e in m_exp)
    ti    = sum(i.get('amount',0) for i in m_inc)
    net   = ti - te

    c1,c2,c3,c4 = st.columns(4)
    c1.metric(f'Expenses — {label}', f'${te:,.2f}')
    c2.metric(f'Income — {label}',   f'${ti:,.2f}')
    c3.metric('Net this month',      f'${net:+,.2f}', delta_color='normal' if net >= 0 else 'inverse')
    c4.metric('All-time expenses',   f'${sum(e.get("price",0) for e in st.session_state.expenses):,.2f}')

    st.divider()
    col_imp, col_exp = st.columns(2)

    with col_imp:
        st.subheader('📥 Import Data')
        st.caption('Restore a previously exported `data.json`.')
        up = st.file_uploader('Upload data.json', type=['json'], label_visibility='collapsed')
        if up and st.button('Load this file', type='primary'):
            try:
                _import_json(up.read())
                st.success('Data loaded.'); st.rerun()
            except Exception as e:
                st.error(f'Import failed: {e}')

    with col_exp:
        st.subheader('📤 Export Data')
        st.caption('Download all your data to back it up.')
        st.download_button('Download data.json', _export_json(),
                           'expense_tracker_data.json', 'application/json')

    if not st.session_state.expenses and not st.session_state.income:
        st.divider()
        with st.expander('👋 Getting Started', expanded=True):
            st.markdown(
                """
1. **📊 Dashboard** — Add expenses, income, budgets, goals, and subscriptions.
2. **📅 Monthly Summary** — Charts and totals for any month.
3. **🔄 Recurring** — Detect and manage recurring transactions.
4. **⭐ Pro Features** — Analytics, AI categorization, and health score.
5. **📱 Phone Connect** *(Pro)* — Control the tracker via Telegram or Discord.
6. **📧 Email Import** *(Max)* — Auto-import receipts from your inbox.
7. **⚙️ Settings** — Activate your license key and manage data.

> Data lives in your **browser session** — export it regularly to save it.
                """
            )
    else:
        st.divider()
        st.subheader('Recent Activity')
        recent = sorted(st.session_state.expenses, key=lambda x: x.get('date',''), reverse=True)[:8]
        for e in recent:
            c1,c2,c3,c4 = st.columns([3,2,2,2])
            c1.write(f"**{e.get('purchased','—')}**")
            c2.write(f"{e.get('price',0):.2f} {e.get('currency','').upper()}")
            c3.write(e.get('tags',''))
            c4.write(e.get('date',''))


def page_dashboard():
    _init(); _license_badge()
    st.title('📊 Dashboard')

    tab_ov, tab_add, tab_edit, tab_del, tab_exp, tab_inc, tab_sub, tab_assets = st.tabs([
        'Overview','Add','Edit','Delete','Expenses','Income','Subscriptions','Assets & Liabilities',
    ])

    # ── Overview ───────────────────────────────────────────────────────────────
    with tab_ov:
        cm   = st.session_state.current_month
        me   = [e for e in st.session_state.expenses if e.get('date','').startswith(cm)]
        mi   = [i for i in st.session_state.income   if i.get('date','').startswith(cm)]
        te, ti = sum(e['price'] for e in me), sum(i['amount'] for i in mi)
        c1,c2,c3 = st.columns(3)
        c1.metric('Monthly Expenses', f'${te:,.2f}')
        c2.metric('Monthly Income',   f'${ti:,.2f}')
        net = ti - te
        c3.metric('Net', f'${net:+,.2f}', delta_color='normal' if net >= 0 else 'inverse')

        if st.session_state.budget:
            st.subheader('Budget Status')
            cat_spent: dict = {}
            for e in me:
                tag = e.get('tags', 'Other')
                cat_spent[tag] = cat_spent.get(tag, 0) + e['price']
            for b in st.session_state.budget:
                spent = cat_spent.get(b['category'],0)
                limit = float(b.get('amount', b.get('limit',0)))
                pct   = min(spent/limit, 1.0) if limit > 0 else 0.0
                cl, cb = st.columns([1,3])
                cl.write(f"**{b['category']}**")
                cl.caption(f"{spent:.2f} / {limit:.2f} {b.get('currency','USD').upper()}")
                cb.progress(pct)
                if spent > limit:   cb.error(f"Over by {spent-limit:.2f}", icon='🚨')
                elif pct >= 0.9:    cb.warning(f"{int(pct*100)}% used", icon='⚠️')

        st.divider()
        st.subheader('Net-Worth Snapshot')
        if not _has('net_worth'):
            st.info('Net Worth is a **Max** feature. Activate a Max license in ⚙️ Settings.')
        else:
            r = _api('/net-worth', {'expenses':st.session_state.expenses,'income':st.session_state.income,
                     'subscriptions':st.session_state.subscriptions,'goals':st.session_state.goals,
                     'assets':st.session_state.assets,'liabilities':st.session_state.liabilities},
                     token=st.session_state.get('pro_token'))
            nw = r.json() if (r and r.ok) else {}
            if nw.get('success'):
                cur = nw['base_currency']
                c1,c2,c3,c4 = st.columns(4)
                c1.metric('Total Assets',      f"{nw['total_assets']:,.2f} {cur}")
                c2.metric('Total Liabilities', f"{nw['total_liabilities']:,.2f} {cur}")
                c3.metric('Net Cash Flow',     f"{nw['net_cash_flow']:,.2f} {cur}")
                c4.metric('Net Worth',         f"{nw['estimated_net_worth']:,.2f} {cur}")
            else:
                st.info('Net-worth snapshot unavailable.')

        st.divider()
        st.subheader('Spending Forecast')
        if st.session_state.expenses:
            if st.button('Refresh Forecast', key='ov_forecast_btn'):
                with st.spinner('Calculating…'):
                    r = _api('/forecast', {'expenses':st.session_state.expenses,'base_currency':'USD'})
                    st.session_state['ov_forecast'] = r.json() if (r and r.ok) else {}
            fc = st.session_state.get('ov_forecast')
            if fc is None:
                st.info('Click **Refresh Forecast** to load.')
            elif fc.get('success') and fc.get('forecasts'):
                st.caption(f"Based on {fc['based_on_months']} month(s) of history")
                cols = st.columns(3)
                for i,(cat,info) in enumerate(fc['forecasts'].items()):
                    arrow = '↑' if info['trend']=='increasing' else '↓' if info['trend']=='decreasing' else '→'
                    cols[i%3].metric(f'{cat} {arrow}', f"{info['next_month_forecast']:,.2f}",
                                     f"avg {info['current_avg']:,.2f}")
            else:
                st.info('Not enough history for a forecast yet.')

        st.divider()
        st.subheader('Unusual Expenses')
        if st.session_state.expenses:
            if st.button('Scan for Anomalies', key='ov_anomaly_btn'):
                with st.spinner('Scanning…'):
                    r = _api('/detect-anomalies', {'expenses':st.session_state.expenses,'z_threshold':2.5})
                    st.session_state['ov_anomalies'] = r.json() if (r and r.ok) else {}
            ad = st.session_state.get('ov_anomalies')
            if ad is None:
                st.info('Click **Scan for Anomalies** to check.')
            else:
                for a in ad.get('anomalies',[]):
                    st.warning(f"**{a.get('purchased','—')}** — {a['price']:.2f} {a.get('currency','').upper()} "
                               f"(z={a['z_score']}, +{a['deviation']:.2f} vs avg)", icon='🚨')
                if not ad.get('anomalies'):
                    st.success('No unusual expenses detected.', icon='✅')

        st.divider()
        st.subheader('Ask About Your Finances')
        q = st.text_input('Ask anything…', max_chars=500, key='dash_nl_q')
        if st.button('Ask', key='dash_nl_btn') and q.strip():
            with st.spinner('Thinking…'):
                r = _api('/query', {'question':q,'data':{'expenses':st.session_state.expenses,
                         'income':st.session_state.income,'budget':st.session_state.budget}})
                st.session_state['nl_ans'] = r.json().get('answer','') if (r and r.ok) else 'Unavailable — AI key may not be configured.'
        if st.session_state.get('nl_ans'):
            st.markdown(st.session_state['nl_ans'])

    # ── Add ────────────────────────────────────────────────────────────────────
    with tab_add:
        choice = st.selectbox('What to add?', ['Expense','Income','Budget','Subscription','Goal'])
        t = _get_tracker()

        if choice == 'Expense':
            with st.expander('Re-add a recurring expense', expanded=False):
                for idx, re in enumerate(st.session_state.recurring_expenses):
                    c1,c2,c3 = st.columns([3,2,1])
                    c1.write(f"**{re['purchased']}**"); c2.write(f"{re['amount']:.2f} {re['currency'].upper()}")
                    if c3.button('Re-add', key=f'readd_{idx}'):
                        t.add_expenses(re['amount'],re['purchased'],re['tags'],re['currency'],
                                       str(_dt.date.today()),'Re-added')
                        _sync(); st.rerun()
            with st.form('add_exp', clear_on_submit=True):
                c1,c2 = st.columns(2)
                name   = c1.text_input('What was purchased?')
                amount = c2.number_input('Amount', min_value=0.0, step=0.01)
                cat    = st.selectbox('Category', CATEGORIES)
                c3,c4 = st.columns(2)
                curr   = c3.selectbox('Currency', CURRENCIES)
                date   = c4.date_input('Date', value=_dt.date.today())
                notes  = st.text_input('Notes')
                recur  = st.checkbox('Mark as recurring')
                if st.form_submit_button('Add Expense', type='primary'):
                    res = t.add_recurring_expense(amount,name,cat,curr) if recur else \
                          t.add_expenses(amount,name,cat,curr,str(date),notes)
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])

        elif choice == 'Income':
            with st.form('add_inc', clear_on_submit=True):
                c1,c2 = st.columns(2)
                source = c1.text_input('Income source')
                amount = c2.number_input('Amount', min_value=0.0, step=0.01)
                c3,c4 = st.columns(2)
                curr   = c3.selectbox('Currency', CURRENCIES)
                date   = c4.date_input('Date', value=_dt.date.today())
                notes  = st.text_input('Notes')
                recur  = st.checkbox('Mark as recurring')
                if st.form_submit_button('Add Income', type='primary'):
                    res = t.add_recurring_income(amount,source,curr) if recur else \
                          t.add_income(amount,source,str(date),curr,notes)
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])

        elif choice == 'Budget':
            with st.form('add_bud', clear_on_submit=True):
                cat    = st.selectbox('Category', CATEGORIES)
                c1,c2 = st.columns(2)
                amount = c1.number_input('Monthly Limit', min_value=0.0, step=0.01)
                curr   = c2.selectbox('Currency', CURRENCIES)
                if st.form_submit_button('Add Budget', type='primary'):
                    res = t.create_budget(cat, amount, curr)
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])

        elif choice == 'Subscription':
            with st.form('add_sub', clear_on_submit=True):
                name   = st.text_input('Name')
                c1,c2,c3 = st.columns(3)
                price  = c1.number_input('Price', min_value=0.0, step=0.01)
                curr   = c2.selectbox('Currency', CURRENCIES)
                date   = c3.date_input('Start date', value=_dt.date.today())
                if st.form_submit_button('Add Subscription', type='primary'):
                    res = t.add_subscriptions(name,price,curr,str(date))
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])

        elif choice == 'Goal':
            with st.form('add_goal', clear_on_submit=True):
                name   = st.text_input('Goal name')
                c1,c2 = st.columns(2)
                target = c1.number_input('Target amount', min_value=0.0, step=0.01)
                contrib= c2.number_input('Monthly contribution', min_value=0.0, step=0.01)
                c3,c4 = st.columns(2)
                curr   = c3.selectbox('Currency', CURRENCIES)
                date   = c4.date_input('Start date', value=_dt.date.today())
                if st.form_submit_button('Add Goal', type='primary'):
                    res = t.create_goal(name,target,str(date),contrib,curr)
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])

    # ── Edit ───────────────────────────────────────────────────────────────────
    with tab_edit:
        choice = st.selectbox('What to edit?', ['Expense','Income','Budget','Subscription'], key='edit_ch')
        t = _get_tracker()

        if choice == 'Expense':
            with st.form('edit_exp'):
                c1,c2 = st.columns(2)
                eid  = c1.number_input('Expense ID', min_value=1, step=1)
                name = c2.text_input('New name (blank=keep)')
                c3,c4 = st.columns(2)
                amt  = c3.number_input('New amount (0=keep)', min_value=0.0, step=0.01)
                cat  = c4.selectbox('Category', CATEGORIES)
                c5,c6 = st.columns(2)
                curr = c5.selectbox('Currency', CURRENCIES)
                date = c6.date_input('Date', value=_dt.date.today())
                notes= st.text_input('Notes')
                if st.form_submit_button('Save', type='primary'):
                    res = t.edit_expenses(int(eid),amt or None,name or None,cat,str(date),curr,notes or None)
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])

        elif choice == 'Income':
            with st.form('edit_inc'):
                c1,c2 = st.columns(2)
                iid    = c1.number_input('Income ID', min_value=1, step=1)
                source = c2.text_input('New source (blank=keep)')
                c3,c4 = st.columns(2)
                amt   = c3.number_input('New amount (0=keep)', min_value=0.0, step=0.01)
                curr  = c4.selectbox('Currency', CURRENCIES)
                date  = st.date_input('Date', value=_dt.date.today())
                notes = st.text_input('Notes')
                if st.form_submit_button('Save', type='primary'):
                    res = t.edit_income(int(iid),amt or None,source or None,str(date),curr,notes or None)
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])

        elif choice == 'Budget':
            with st.form('edit_bud'):
                prev = st.text_input('Current category name')
                c1,c2 = st.columns(2)
                new_cat= c1.selectbox('New category', CATEGORIES)
                amt    = c2.number_input('New limit', min_value=0.0, step=0.01)
                curr   = st.selectbox('Currency', CURRENCIES)
                if st.form_submit_button('Save', type='primary'):
                    res = t.update_budget(prev,new_cat,amt,curr)
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])

        elif choice == 'Subscription':
            with st.form('edit_sub'):
                name     = st.text_input('Current subscription name')
                new_name = st.text_input('New name (blank=keep)')
                c1,c2 = st.columns(2)
                price  = c1.number_input('New price (0=keep)', min_value=0.0, step=0.01)
                curr   = c2.selectbox('Currency', CURRENCIES)
                if st.form_submit_button('Save', type='primary'):
                    res = t.edit_subscription(name,price=price or None,name=new_name or None,currency=curr)
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])

    # ── Delete ─────────────────────────────────────────────────────────────────
    with tab_del:
        choice = st.selectbox('What to delete?', ['Expense','Income','Budget','Subscription'], key='del_ch')
        t = _get_tracker()
        if choice == 'Expense':
            with st.form('del_exp'):
                eid = st.number_input('Expense ID', min_value=1, step=1)
                if st.form_submit_button('Delete', type='primary'):
                    res = t.delete_expenses(int(eid))
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])
        elif choice == 'Income':
            with st.form('del_inc'):
                iid = st.number_input('Income ID', min_value=1, step=1)
                if st.form_submit_button('Delete', type='primary'):
                    res = t.delete_income(int(iid))
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])
        elif choice == 'Budget':
            with st.form('del_bud'):
                cat = st.text_input('Category to delete')
                if st.form_submit_button('Delete', type='primary'):
                    res = t.delete_budget(cat)
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])
        elif choice == 'Subscription':
            with st.form('del_sub'):
                name = st.text_input('Subscription name')
                if st.form_submit_button('Delete', type='primary'):
                    res = t.delete_subscription(name)
                    if res['success']: st.success(res['message']); _sync(); st.rerun()
                    else: st.error(res['message'])

    # ── Expenses list ──────────────────────────────────────────────────────────
    with tab_exp:
        st.subheader('All Expenses')
        search = st.text_input('Search', key='exp_srch')
        items  = st.session_state.expenses
        if search:
            items = [e for e in items if search.lower() in e.get('tags','').lower()
                     or search.lower() in e.get('purchased','').lower()
                     or search.lower() in (e.get('notes') or '').lower()]
        for e in items:
            c1,c2,c3,c4 = st.columns([3,2,2,2])
            c1.write(f"**#{e['id']} {e.get('purchased','—')}**")
            c2.write(f"{e['price']:.2f} {e.get('currency','').upper()}")
            c3.write(e.get('tags','')); c4.write(e.get('date',''))
            st.divider()
        if not items:
            st.info('No expenses found.' if not search else f'No results for "{search}".')
        t = _get_tracker()
        res = t.export_to_csv('expenses','/tmp/pub_exp.csv')
        if res['success']:
            st.download_button('Export CSV', res['data'].to_csv(index=False).encode(),'expenses.csv','text/csv')
        pdf = t.export_to_pdf('expenses','/tmp/pub_exp.pdf')
        if pdf['success']:
            st.download_button('Export PDF', pdf['data'],'expenses.pdf','application/pdf')

    # ── Income list ────────────────────────────────────────────────────────────
    with tab_inc:
        st.subheader('All Income')
        search = st.text_input('Search', key='inc_srch')
        items  = st.session_state.income
        if search:
            items = [i for i in items if search.lower() in i.get('source','').lower()
                     or search.lower() in (i.get('notes') or '').lower()]
        for i in items:
            c1,c2,c3,c4 = st.columns([3,2,2,2])
            c1.write(f"**#{i['id']} {i.get('source','—')}**")
            c2.write(f"{i['amount']:.2f} {i.get('currency','').upper()}")
            c3.write(i.get('date','')); c4.write(i.get('notes',''))
            st.divider()
        if not items:
            st.info('No income found.' if not search else f'No results for "{search}".')
        t = _get_tracker()
        res = t.export_to_csv('income','/tmp/pub_inc.csv')
        if res['success']:
            st.download_button('Export CSV', res['data'].to_csv(index=False).encode(),'income.csv','text/csv')

    # ── Subscriptions ──────────────────────────────────────────────────────────
    with tab_sub:
        st.subheader('Subscriptions')
        subs = st.session_state.subscriptions
        if subs:
            for s in subs:
                c1,c2 = st.columns([3,2])
                c1.write(f"**{s.get('name','—')}**")
                c2.write(f"{float(s.get('price',0)):.2f} {s.get('currency','').upper()}")
            r = _api('/upcoming-renewals',{'subscriptions':subs,'days_ahead':30})
            if r and r.ok:
                for u in r.json().get('upcoming',[]):
                    st.info(f"**{u['name']}** renews on {u.get('next_renewal','?')} — {float(u['price']):.2f} {u.get('currency','').upper()}")
        else:
            st.info('No subscriptions yet.')

    # ── Assets & Liabilities ───────────────────────────────────────────────────
    with tab_assets:
        if not _has('net_worth'):
            st.info('Assets & Liabilities is a **Max** feature. Activate a Max license in ⚙️ Settings.')
        else:
            col_a, col_b = st.columns(2)
            t = _get_tracker()
            with col_a:
                st.subheader('Assets')
                for a in st.session_state.assets:
                    c1,c2,c3 = st.columns([3,2,1])
                    c1.write(f"**{a['name']}** · {a['type']}")
                    c2.write(f"{a['value']:,.2f} {a['currency'].upper()}")
                    if c3.button('✕', key=f'da_{a["id"]}'):
                        t.delete_asset(a['id']); _sync(); st.rerun()
                with st.form('add_asset',clear_on_submit=True):
                    st.write('Add Asset')
                    aname  = st.text_input('Name')
                    atype  = st.selectbox('Type',['liquid','investment','real_estate','vehicle','other'])
                    c1,c2 = st.columns(2)
                    aval   = c1.number_input('Value',min_value=0.0,step=0.01)
                    acurr  = c2.selectbox('Currency',CURRENCIES,key='a_c')
                    anotes = st.text_input('Notes')
                    if st.form_submit_button('Add') and aname and aval > 0:
                        res = t.add_asset(aname,atype,aval,acurr,anotes)
                        if res['success']: _sync(); st.rerun()
            with col_b:
                st.subheader('Liabilities')
                for l in st.session_state.liabilities:
                    c1,c2,c3 = st.columns([3,2,1])
                    c1.write(f"**{l['name']}** · {l['type']}")
                    c2.write(f"{l['balance']:,.2f} {l['currency'].upper()}")
                    if c3.button('✕', key=f'dl_{l["id"]}'):
                        t.delete_liability(l['id']); _sync(); st.rerun()
                with st.form('add_liab',clear_on_submit=True):
                    st.write('Add Liability')
                    lname  = st.text_input('Name',key='ln')
                    ltype  = st.selectbox('Type',['mortgage','student_loan','car_loan','credit_card','personal_loan','other'])
                    c1,c2 = st.columns(2)
                    lbal   = c1.number_input('Balance',min_value=0.0,step=0.01)
                    lrate  = c2.number_input('Interest %',min_value=0.0,max_value=100.0,step=0.01)
                    lcurr  = st.selectbox('Currency',CURRENCIES,key='l_c')
                    lnotes = st.text_input('Notes',key='ln2')
                    if st.form_submit_button('Add') and lname and lbal > 0:
                        res = t.add_liability(lname,ltype,lbal,lcurr,lrate/100,lnotes)
                        if res['success']: _sync(); st.rerun()


def page_monthly():
    _init(); _license_badge()
    st.title('📅 Monthly Summary')

    all_months = sorted(set(
        e.get('date','')[:7] for e in st.session_state.expenses + st.session_state.income
        if len(e.get('date','')) >= 7
    ), reverse=True)

    if not all_months:
        st.info('No data yet. Add expenses or income on the Dashboard.'); return

    month = st.selectbox('Select month', all_months,
                         format_func=lambda m: pd.to_datetime(m).strftime('%B %Y'))
    exps = [e for e in st.session_state.expenses if e.get('date','').startswith(month)]
    incs = [i for i in st.session_state.income   if i.get('date','').startswith(month)]
    te   = sum(e['price']  for e in exps)
    ti   = sum(i['amount'] for i in incs)
    net  = ti - te

    c1,c2,c3 = st.columns(3)
    c1.metric('Total Expenses', f'${te:,.2f}')
    c2.metric('Total Income',   f'${ti:,.2f}')
    c3.metric('Net Savings',    f'${net:+,.2f}', delta_color='normal' if net >= 0 else 'inverse')

    st.divider()
    cl, cr = st.columns(2)

    with cl:
        st.subheader('Expenses by Category')
        if exps:
            by_cat: dict = {}
            for e in exps: by_cat[e.get('tags','Other')] = by_cat.get(e.get('tags','Other'),0) + e['price']
            df = pd.DataFrame({'Category':list(by_cat.keys()),'Amount':list(by_cat.values())}).sort_values('Amount',ascending=False)
            st.dataframe(df, hide_index=True, use_container_width=True)
            fig, ax = plt.subplots(figsize=(4,4))
            ax.pie(df['Amount'], labels=df['Category'], autopct='%1.1f%%', startangle=90)
            st.pyplot(fig); plt.close(fig)
        else:
            st.info('No expenses this month.')

    with cr:
        st.subheader('Income by Source')
        if incs:
            by_src: dict = {}
            for i in incs: by_src[i.get('source','Other')] = by_src.get(i.get('source','Other'),0) + i['amount']
            df = pd.DataFrame({'Source':list(by_src.keys()),'Amount':list(by_src.values())}).sort_values('Amount',ascending=False)
            st.dataframe(df, hide_index=True, use_container_width=True)
            fig, ax = plt.subplots(figsize=(4,4))
            ax.pie(df['Amount'], labels=df['Source'], autopct='%1.1f%%', startangle=90)
            st.pyplot(fig); plt.close(fig)
        else:
            st.info('No income this month.')

    if len(all_months) > 1:
        st.divider(); st.subheader('Monthly Comparison')
        rows = []
        for m in all_months:
            me = sum(e['price']  for e in st.session_state.expenses if e.get('date','').startswith(m))
            mi = sum(i['amount'] for i in st.session_state.income   if i.get('date','').startswith(m))
            rows.append({'Month': pd.to_datetime(m).strftime('%b %Y'), 'Expenses':me,'Income':mi,'Savings':mi-me})
        dfm = pd.DataFrame(rows)
        st.dataframe(dfm, hide_index=True, use_container_width=True)
        fig, ax = plt.subplots(figsize=(10,4))
        dfm.plot(x='Month', y=['Expenses','Income'], kind='bar', ax=ax)
        ax.set_ylabel('Amount ($)'); plt.xticks(rotation=45,ha='right'); plt.tight_layout()
        st.pyplot(fig); plt.close(fig)

        st.subheader('Savings Trend')
        fig2, ax2 = plt.subplots(figsize=(10,3))
        ax2.plot(dfm['Month'], dfm['Savings'], color='green', marker='o', linewidth=2, label='Savings')
        ax2.axhline(0, color='red', linestyle='--', linewidth=1)
        ax2.set_ylabel('Savings ($)'); ax2.legend()
        plt.xticks(rotation=45, ha='right'); plt.tight_layout()
        st.pyplot(fig2); plt.close(fig2)

    st.divider(); st.subheader('Export')
    c1,c2 = st.columns(2)
    t = _get_tracker()
    r = t.export_to_csv('expenses','/tmp/pub_ms.csv')
    if r['success']: c1.download_button('Expenses CSV', r['data'].to_csv(index=False).encode(),'expenses.csv','text/csv')
    r = t.export_to_pdf('expenses','/tmp/pub_ms.pdf')
    if r['success']: c2.download_button('Expenses PDF', r['data'],'expenses.pdf','application/pdf')


def page_recurring():
    _init(); _license_badge()
    st.title('🔄 Recurring Expenses')
    t = _get_tracker()

    st.subheader('Detected Recurring Patterns')
    detected = t.detect_recurring_expenses()
    if detected.get('success') and detected.get('data'):
        for e in detected['data']:
            with st.expander(f"{e['purchased']} — {e['price']} {e['currency'].upper()}"):
                c1,c2 = st.columns(2)
                c1.write(f"**Category:** {e.get('category','?')}")
                c1.write(f"**Frequency:** every {e.get('frequency_days','?')} days")
                c1.write(f"**Occurrences:** {e.get('occurrences','?')}")
                c2.write(f"**Last seen:** {e.get('last_date','?')}")
                c2.write(f"**Next expected:** {e.get('next_expected_date','?')}")
                if st.button('Save to Recurring', key=f"sv_{e['purchased']}_{e['price']}"):
                    res = t.add_recurring_expense(e['price'],e['purchased'],e.get('category','Other'),e['currency'])
                    if res['success']: st.success('Saved.'); _sync(); st.rerun()
                    else: st.error(res['message'])
    else:
        st.info('No patterns detected yet. Expenses that repeat at a similar interval will appear here.')

    st.divider(); st.subheader('Saved Recurring Expenses')
    for item in st.session_state.recurring_expenses:
        with st.expander(f"{item['purchased']} — {item['amount']} {item['currency'].upper()}"):
            c1,c2,c3 = st.columns([3,1,1])
            c1.write(f"Category: **{item.get('tags','?')}**")
            if c2.button('Re-add', key=f"ra_{item['purchased']}_{item['amount']}"):
                t.add_expenses(item['amount'],item['purchased'],item.get('tags','Other'),
                               item['currency'],str(_dt.date.today()),'Re-added')
                _sync(); st.rerun()
            if c3.button('Delete', key=f"dr_{item['purchased']}_{item['amount']}"):
                data = t.open_file()['data']
                data['recurring_expenses'] = [r for r in data['recurring_expenses']
                    if not (r['purchased']==item['purchased'] and r['amount']==item['amount'])]
                t.write_file(data); _sync(); st.rerun()
    if not st.session_state.recurring_expenses:
        st.caption('No saved recurring expenses.')

    st.divider(); st.subheader('Add Recurring Expense')
    with st.form('add_rec', clear_on_submit=True):
        c1,c2 = st.columns(2)
        purchased = c1.text_input('Description')
        amount    = c2.number_input('Amount', min_value=0.01, step=0.01)
        c3,c4 = st.columns(2)
        tags   = c3.selectbox('Category', CATEGORIES)
        curr   = c4.selectbox('Currency', CURRENCIES)
        if st.form_submit_button('Add', type='primary') and purchased and tags:
            res = t.add_recurring_expense(amount,purchased,tags,curr)
            if res['success']: st.success('Added.'); _sync(); st.rerun()
            else: st.error(res['message'])


def page_pro():
    _init(); _license_badge()
    st.title('⭐ Pro Features')
    if not st.session_state.get('pro_token'):
        st.info('Activate your license key on the **⚙️ Settings** page.', icon='🔒')

    expenses = st.session_state.expenses
    currency = st.selectbox('Base currency', ['USD','EUR','GBP','THB','JPY'])

    if not expenses:
        st.info('Add some expenses first.'); return

    st.header('Analytics')

    with st.expander('📈 Spending Forecast', expanded=True):
        if st.button('Run Forecast'):
            with st.spinner('Calculating…'):
                r = _api('/forecast', {'expenses':expenses,'base_currency':currency})
                if r and r.ok:
                    fc = r.json()
                    st.caption(f"Based on {fc['based_on_months']} month(s) · {fc['base_currency']} only")
                    cols = st.columns(3)
                    for i,(cat,info) in enumerate(fc['forecasts'].items()):
                        arrow = '↑' if info['trend']=='increasing' else '↓' if info['trend']=='decreasing' else '→'
                        cols[i%3].metric(cat,f"{info['next_month_forecast']:.2f}",f"{arrow} avg {info['current_avg']:.2f}")
                else: st.error('Forecast unavailable.')

    with st.expander('🚨 Anomaly Detection'):
        z = st.slider('Z-score threshold', 1.5, 4.0, 2.5, 0.1)
        if st.button('Scan for Anomalies'):
            with st.spinner('Scanning…'):
                r = _api('/detect-anomalies',{'expenses':expenses,'z_threshold':z})
                if r and r.ok:
                    flagged = r.json().get('anomalies',[])
                    if flagged:
                        for a in flagged:
                            st.warning(f"**{a.get('purchased','?')}** — {a.get('price',0):.2f} (z={a.get('z_score','?')})", icon='🚨')
                    else: st.success('No anomalies at this threshold.', icon='✅')
                else: st.error('Scan failed.')

    with st.expander('🧾 Tax Summary'):
        year = st.number_input('Tax year', min_value=2020, max_value=2035, value=2025, step=1)
        if st.button('Generate Tax Summary'):
            with st.spinner('Calculating…'):
                r = _api('/tax-summary',{'expenses':expenses,'income':st.session_state.income,'year':int(year)})
                if r and r.ok:
                    d = r.json()
                    c1,c2,c3 = st.columns(3)
                    c1.metric('Income',f"{d['total_income']:.2f}")
                    c2.metric('Expenses',f"{d['total_expenses']:.2f}")
                    c3.metric('Net',f"{d['net']:.2f}")
                    st.metric('Est. Deductible',f"{d['estimated_deductible_total']:.2f}")
                else: st.error('Tax summary failed.')

    with st.expander('💡 Financial Health Score'):
        if st.button('Calculate'):
            with st.spinner('Calculating…'):
                r = _api('/health-score',{'expenses':expenses,'income':st.session_state.income,
                         'budget':st.session_state.budget,'subscriptions':st.session_state.subscriptions,
                         'goals':st.session_state.goals})
                if r and r.ok:
                    d = r.json()
                    st.metric('Health Score', f"{d.get('score',0)}/100 ({d.get('grade','?')})")
                    for ins in d.get('insights',[]): st.info(ins, icon='💡')
                else: st.error('Unavailable.')

    st.divider(); st.header('AI Advanced Categorization')
    st.caption('Requires an active Pro or Max license.')
    if not _has('advanced_categorization'):
        st.info('Activate a Pro or Max license in ⚙️ Settings.')
    else:
        ctx = st.text_input('Focus (optional)', placeholder="e.g. 'last 3 months'")
        if st.button('Run Advanced Categorization', type='primary'):
            with st.spinner(f'Analysing {len(expenses)} expenses… (30–90 s)'):
                r = _api('/advanced-categorize',
                         {'expenses':expenses,'context':ctx or 'Advanced categorization'},
                         token=st.session_state.get('pro_token'), timeout=180)
            if r is None: st.error('Backend unreachable.')
            elif r.status_code == 401: st.error('License key rejected — re-activate in ⚙️ Settings.')
            elif not r.ok: st.error(f'Failed ({r.status_code}): {r.text}')
            else: st.session_state['adv_cat'] = r.json()

        result = st.session_state.get('adv_cat')
        if result:
            st.subheader('Summary'); st.write(result.get('summary','—'))
            if result.get('key_findings'):
                st.subheader('Key Findings')
                for f in result['key_findings']: st.markdown(f'- {f}')
            if result.get('recommendations'):
                st.subheader('Recommendations')
                for rec in result['recommendations']: st.info(rec, icon='💡')


def page_phone():
    _init(); _license_badge()
    st.title('📱 Phone Connect')
    st.caption('Control your expense tracker via Telegram or Discord — Pro & Max feature.')
    _require('bot_connect', 'Pro')

    cfg = _load_cfg()
    tab_tg, tab_dc, tab_ref = st.tabs(['Telegram','Discord','Command Reference'])

    with tab_tg:
        st.subheader('Telegram Bot')
        with st.expander('How to create a Telegram bot'):
            st.markdown('1. Open Telegram → search **@BotFather**.\n2. Send `/newbot` and follow prompts.\n3. Copy the API token.\n4. Paste below and save.\n5. Start the bot on your machine (command below).\n6. Search for your bot and send `/start`.')
        tg = st.text_input('Telegram Bot Token', value=cfg.get('telegram_token',''),
                            type='password', placeholder='YOUR_TELEGRAM_BOT_TOKEN')
        if st.button('Save Telegram Token', type='primary'):
            cfg['telegram_token'] = tg; _save_cfg(cfg); st.success('Saved.')
        if cfg.get('telegram_token'): st.success('Token configured.', icon='✅')
        st.divider()
        st.code('python backend/phone_connect.py --platform telegram', language='bash')

    with tab_dc:
        st.subheader('Discord Bot')
        with st.expander('How to create a Discord bot'):
            st.markdown('1. Go to **discord.com/developers/applications** → New Application.\n2. Bot tab → Add Bot → Reset Token → copy it.\n3. Enable **Message Content Intent**.\n4. OAuth2 → URL Generator → `bot` scope + Send Messages permission → invite the bot.\n5. Paste token below and save.\n6. Start the bot on your machine.')
        dc = st.text_input('Discord Bot Token', value=cfg.get('discord_token',''),
                           type='password', placeholder='YOUR_DISCORD_BOT_TOKEN')
        if st.button('Save Discord Token', type='primary'):
            cfg['discord_token'] = dc; _save_cfg(cfg); st.success('Saved.')
        if cfg.get('discord_token'): st.success('Token configured.', icon='✅')
        st.divider()
        st.code('python backend/phone_connect.py --platform discord', language='bash')

    with tab_ref:
        st.markdown(
            '| Command | Telegram | Discord | Description |\n'
            '|---------|----------|---------|-------------|\n'
            '| Welcome | `/start` | `!start` | Greeting |\n'
            '| Help | `/help` | `!help` | List commands |\n'
            '| Summary | `/summary` | `!summary` | Overview + last 5 expenses |\n'
            '| Balance | `/balance` | `!balance` | This month net |\n'
            '| Budget | `/budget` | `!budget` | Budget by category |\n'
            '| Add expense | `/add 12.50 Food Lunch` | `!add 12.50 Food Lunch` | Log expense |'
        )


def page_email():
    _init(); _license_badge()
    st.title('📧 Email Import')
    st.caption('Find purchase receipts in your inbox and import them — Max feature.')
    _require('email_parsing', 'Max')

    cfg = _load_cfg()
    PRESETS = {
        'Gmail':             ('imap.gmail.com',           993),
        'Outlook/Hotmail':   ('outlook.office365.com',    993),
        'Yahoo Mail':        ('imap.mail.yahoo.com',      993),
        'iCloud':            ('imap.mail.me.com',         993),
        'Custom':            ('',                          993),
    }
    preset = st.selectbox('Provider', list(PRESETS.keys()))
    ds, dp = PRESETS[preset]

    with st.form('email_cfg'):
        c1,c2 = st.columns([3,1])
        srv  = c1.text_input('IMAP Server', value=cfg.get('email_imap_server',ds) or ds)
        port = c2.number_input('Port', value=cfg.get('email_imap_port',dp) or dp, min_value=1, max_value=65535, step=1)
        addr = st.text_input('Email Address', value=cfg.get('email_address',''))
        pwd  = st.text_input('Password / App Password', value=cfg.get('email_password',''), type='password')
        c3,c4 = st.columns(2)
        days  = c3.slider('Scan last N days', 7, 180, 30)
        limit = c4.number_input('Max emails', 10, 500, 150, step=10)
        submitted = st.form_submit_button('Save & Scan', type='primary')

    with st.expander('Gmail App Password setup'):
        st.markdown('1. Google Account → Security → 2-Step Verification (must be on).\n2. Scroll to **App passwords**.\n3. Generate for Mail — use the 16-char code as the password above.')

    if submitted:
        if not srv or not addr or not pwd:
            st.error('All fields required.'); return
        cfg.update({'email_imap_server':srv,'email_imap_port':int(port),'email_address':addr,'email_password':pwd})
        _save_cfg(cfg)
        with st.spinner(f'Scanning up to {limit} emails from the last {days} days…'):
            try:
                from email_parser import fetch_expense_emails
                st.session_state['email_results'] = fetch_expense_emails(
                    srv, int(port), addr, pwd, days_back=days, max_emails=int(limit))
            except ConnectionError as exc:
                st.error(f'Connection failed: {exc}'); return
            except Exception as exc:
                st.error(f'Scan error: {exc}'); return

    results = st.session_state.get('email_results')
    if results is None:
        st.info('Configure credentials above and click **Save & Scan**.'); return

    if not results:
        st.success('No receipt-like emails found.', icon='✅')
        if st.button('Clear'): st.session_state.pop('email_results',None); st.rerun()
        return

    st.success(f'Found **{len(results)}** potential expense(s).', icon='📬')
    rows = [{'date':r['date'],'purchased':r['purchased'],'price':r['price'],
             'currency':r['currency'],'tags':r['tags'],'subject':r.get('_subject','')} for r in results]
    edited = st.data_editor(pd.DataFrame(rows), use_container_width=True, num_rows='fixed',
        column_config={'price':st.column_config.NumberColumn('Amount',format='%.2f'),
                       'tags':st.column_config.SelectboxColumn('Category',
                           options=['Food','Shopping','Travel','Subscriptions','Utilities','Healthcare','Education','Entertainment','Other'])},
        key='email_ed')

    sel = st.multiselect('Select rows to import', list(range(len(results))),
                         default=list(range(len(results))),
                         format_func=lambda i: f"{rows[i]['date']}  {rows[i]['purchased']}  {rows[i]['price']:.2f}")

    c1,c2 = st.columns([1,5])
    with c1:
        if st.button('Import Selected', type='primary', disabled=not sel):
            t = _get_tracker(); ok = 0
            for idx in sel:
                row = edited.iloc[idx]
                res = t.add_expenses(float(row['price']),str(row['purchased']),str(row['tags']),
                                     str(row['currency']).lower(),str(row['date']),
                                     results[idx].get('notes','Imported from email'))
                if res.get('success'): ok += 1
            if ok:
                st.success(f'Imported {ok} expense(s).', icon='✅')
                _sync(); st.session_state.pop('email_results',None); st.rerun()
    with c2:
        if st.button('Clear Results'): st.session_state.pop('email_results',None); st.rerun()


def page_settings():
    _init(); _license_badge()
    st.title('⚙️ Settings')

    tab_lic, tab_data, tab_prefs = st.tabs(['License','Data','Preferences'])

    # ── License ────────────────────────────────────────────────────────────────
    with tab_lic:
        st.subheader('Activate Your License')
        st.markdown('Enter the license key from your purchase email to unlock **Pro** or **Max** features.')

        tier  = st.session_state.get('pro_tier','')
        email = st.session_state.get('pro_email','')
        if tier:
            icon = '👑' if tier=='max' else '⭐'
            st.success(f"{icon} **{tier.upper()} license active** — {email}")
            st.caption('Unlocked: ' + ', '.join(st.session_state.get('pro_features',[])))
            st.divider()

        key_input = st.text_input(
            'License key',
            value=st.session_state.get('pro_token',''),
            type='password',
            placeholder='Paste the key from your purchase email…',
        )

        c1, c2 = st.columns([1, 5])
        with c1:
            if st.button('Activate', type='primary', disabled=not key_input):
                with st.spinner('Validating…'):
                    try:
                        r = requests.post(f'{CLOUD_AUTH}/validate', json={'token':key_input}, timeout=10)
                        if r.ok:
                            d = r.json()
                            st.session_state.update({
                                'pro_token':    key_input,
                                'pro_email':    d.get('email',''),
                                'pro_tier':     d.get('tier','pro'),
                                'pro_features': d.get('features',[]),
                            })
                            t = d.get('tier','pro')
                            st.success(f"{'👑' if t=='max' else '⭐'} Activated — {d.get('email','')} ({t.upper()})")
                            st.rerun()
                        elif r.status_code == 422:
                            st.error('Invalid or expired key.')
                        else:
                            st.error(f'Validation failed (HTTP {r.status_code}).')
                    except requests.exceptions.ConnectionError:
                        st.error('Could not reach the license server.')
                    except Exception as exc:
                        st.error(f'Error: {exc}')

        with c2:
            if st.session_state.get('pro_token') and st.button('Remove License'):
                for k in ('pro_token','pro_email','pro_tier','pro_features'):
                    st.session_state.pop(k,None)
                st.success('License removed.'); st.rerun()

        st.divider()
        st.subheader("What's Included")
        c_free, c_pro, c_max = st.columns(3)
        with c_free:
            st.markdown('**Free**')
            st.markdown('- Full dashboard CRUD\n- Monthly summaries\n- Recurring detection\n- Spending forecast\n- Anomaly detection\n- Tax summary\n- Health score\n- CSV/PDF export')
        with c_pro:
            st.markdown('**⭐ Pro**')
            st.markdown('- Everything in Free\n- AI Advanced Categorization\n- 📱 Phone Connect\n  (Telegram & Discord)\n- Budget forecasting AI\n- Receipt OCR')
        with c_max:
            st.markdown('**👑 Max**')
            st.markdown('- Everything in Pro\n- 📧 Email Import\n- Net Worth tracking\n- Assets & Liabilities\n- Deep financial analysis\n- Multi-project support')

    # ── Data ───────────────────────────────────────────────────────────────────
    with tab_data:
        st.subheader('Import Data')
        st.warning('Importing will **replace** all current session data.', icon='⚠️')
        up = st.file_uploader('Upload data.json', type=['json'], label_visibility='collapsed')
        if up and st.button('Load this file', type='primary'):
            try:
                _import_json(up.read()); st.success('Imported.', icon='✅'); st.rerun()
            except Exception as exc:
                st.error(f'Import failed: {exc}')

        st.divider()
        st.subheader('Export Data')
        st.download_button('Download data.json', _export_json(), 'expense_tracker_data.json', 'application/json')

        st.divider()
        st.subheader('Clear All Data')
        if st.button('Clear All Data', type='secondary'):
            st.session_state['_confirm_clear'] = True
        if st.session_state.get('_confirm_clear'):
            st.error('This cannot be undone.')
            c1,c2 = st.columns([1,5])
            if c1.button('Yes, clear', type='primary'):
                _get_tracker().write_file({'expenses':[],'income':[],'budget':[],'subscriptions':[],
                    'goals':[],'recurring_expenses':[],'recurring_income':[],'assets':[],'liabilities':[]})
                _sync(); st.session_state.pop('_confirm_clear',None)
                st.success('Cleared.'); st.rerun()
            if c2.button('Cancel'):
                st.session_state.pop('_confirm_clear',None); st.rerun()

    # ── Preferences ────────────────────────────────────────────────────────────
    with tab_prefs:
        st.subheader('Active Month')
        new_month = st.text_input('Current month (YYYY-MM)', value=st.session_state.get('current_month',''))
        if st.button('Set Month'):
            try:
                pd.to_datetime(new_month)
                st.session_state.current_month = new_month
                st.success(f'Month set to {new_month}.')
            except Exception:
                st.error('Invalid format — use YYYY-MM (e.g. 2025-06).')
        st.divider()
        st.subheader('About')
        st.markdown(
            '**Expense Tracker** — personal finance app for tracking expenses, income, '
            'budgets, goals, and subscriptions.\n\n'
            'Source: [github.com/PyMite6941/Expense-tracker](https://github.com/PyMite6941/Expense-tracker)'
        )
        st.caption('Data lives only in this browser session. Export regularly to avoid losing it.')


# ══════════════════════════════════════════════════════════════════════════════
# NAVIGATION
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title='Expense Tracker',
    page_icon='💰',
    layout='wide',
    initial_sidebar_state='expanded',
)

pg = st.navigation([
    st.Page(page_home,      title='Home',            icon='🏠', default=True),
    st.Page(page_dashboard, title='Dashboard',       icon='📊'),
    st.Page(page_monthly,   title='Monthly Summary', icon='📅'),
    st.Page(page_recurring, title='Recurring',       icon='🔄'),
    st.Page(page_pro,       title='Pro Features',    icon='⭐'),
    st.Page(page_phone,     title='Phone Connect',   icon='📱'),
    st.Page(page_email,     title='Email Import',    icon='📧'),
    st.Page(page_settings,  title='Settings',        icon='⚙️'),
])
pg.run()
