# For the web ui setup
import streamlit as st
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..', '..')))

# Initialize the session states
from CLI.app.streamlit_setup import init_st, sync_data, BACKEND_URL, USE_LOCAL_BACKEND
from CLI.app.theme import page_setup, section, account_banner, render_sidebar, upsell
import requests as _requests
import json as _json
from datetime import datetime as _dtm

# Must run before any other Streamlit call (set_page_config + theme + nav).
page_setup("GRID Expense Tracker", "💸")
init_st()
render_sidebar()


class _Resp:
    """The parts of a requests.Response the panels actually use.

    A real Response is not safely cacheable, so the network layer is reduced to
    (status_code, parsed body) and that is what gets memoised.
    """
    __slots__ = ('status_code', '_body')

    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._body is None:
            raise ValueError('no JSON body')
        return self._body


@st.cache_data(ttl=300, show_spinner=False, max_entries=64)
def _backend_fetch(url: str, payload_json: str, auth_fingerprint: str):
    """One cached round trip.

    Streamlit re-runs the whole script on EVERY widget interaction, and the
    Overview fires three of these on each render. Against Cloud Run that was
    measured at ~28s per cold call, so changing the month re-paid the entire
    cost and the panels sat blank each time.

    Keyed on the endpoint, the exact payload, and a FINGERPRINT of the token —
    never the token itself, which must not sit in a cache key. Failures are
    cached too, deliberately: a free user hitting a 403 should not re-wait 28
    seconds for the same 403 on every rerun.
    """
    headers = {}
    if auth_fingerprint:
        headers['Authorization'] = f'Bearer {st.session_state.get("pro_token", "")}'
    try:
        r = _requests.post(url, data=payload_json,
                           headers={**headers, 'Content-Type': 'application/json'},
                           timeout=30)
    except (_requests.exceptions.ConnectionError, _requests.exceptions.Timeout):
        return None
    try:
        body = r.json()
    except Exception:
        body = None
    return _Resp(r.status_code, body)


def _backend_post(endpoint: str, payload: dict, token: str = None):
    import hashlib as _hashlib
    url = f'{st.session_state.get("backend_url", BACKEND_URL)}{endpoint}'
    fp = _hashlib.sha256(token.encode()).hexdigest()[:16] if token else ''
    return _backend_fetch(url, _json.dumps(payload, sort_keys=True, default=str), fp)

def _gated(resp, feature_label: str):
    """Turn a backend response into (payload, notice).

    Panels used to collapse every failure into a falsy default, so a 403 from
    the Pro gate rendered as "not enough history" or a green "no anomalies
    detected" — telling a user their data was thin when really the feature was
    locked, and hiding real anomalies from anyone whose licence had lapsed.
    """
    if resp is None:
        return None, ('warning', 'Backend unreachable — check your connection.')
    if resp.status_code in (401, 403):
        # 'locked' is rendered by upsell(), so a paywalled panel offers a way to
        # buy rather than just naming the tier and stopping.
        if st.session_state.get('pro_token'):
            return None, ('locked_expired', feature_label)
        return None, ('locked', feature_label)
    if resp.status_code == 429:
        return None, ('warning', 'Rate limit reached — try again in a minute.')
    if not resp.ok:
        detail = ''
        try:
            detail = resp.json().get('detail', '')
        except Exception:
            pass
        return None, ('error', f'Request failed ({resp.status_code}). {detail}'.strip())
    try:
        return resp.json(), None
    except Exception:
        return None, ('error', 'Backend returned an unreadable response.')


def _notice(notice):
    kind, msg = notice
    if kind == 'locked':
        upsell(msg, 'Pro')
    elif kind == 'locked_expired':
        upsell(msg, 'Pro',
               detail='Your current licence does not cover it, or it has expired.')
    else:
        {'info': st.info, 'warning': st.warning, 'error': st.error}[kind](msg)


# Eight flat tabs was too many to scan. They're grouped into four, with the
# originals nested underneath — every `with tab_*:` block below still works
# because Streamlit containers render wherever they were created.
tab_overview, tab_manage, tab_records, tab_net_worth = st.tabs(
    ['Overview', 'Manage', 'Records', 'Net Worth']
)

tab_dashboard = tab_overview

with tab_manage:
    tab_add, tab_edit, tab_delete = st.tabs(['Add', 'Edit', 'Delete'])

with tab_records:
    tab_view_expenses, tab_view_income, tab_view_subscriptions = st.tabs(
        ['Expenses', 'Income', 'Subscriptions']
    )

# ── Dashboard ────────────────────────────────────────────────────────────────
with tab_dashboard:
    # Hosted-mode fallbacks (no account / no entitlement / DB unreachable) are
    # set by _build_tracker() but were never surfaced on any page. Show them.
    account_banner()

    # ── Month selector ───────────────────────────────────────────────────────
    # Everything below keys off current_month, which used to be pinned to today
    # with no control anywhere — last month was simply unreachable.
    _this_month = _dtm.now().strftime('%Y-%m')
    _months_with_data = {str(e['date'])[:7] for e in st.session_state.expenses if e.get('date')}
    _months_with_data |= {str(i['date'])[:7] for i in st.session_state.income if i.get('date')}
    _known_months = set(_months_with_data) | {_this_month}
    _months = sorted(_known_months, reverse=True)

    # Open on the newest month that actually HAS records. Defaulting to the
    # calendar month meant that on the 1st or 2nd every figure read 0.00 and the
    # dashboard looked broken until you noticed the picker. Only applied on the
    # first render — once you pick a month, your choice stands.
    if 'overview_month' not in st.session_state:
        st.session_state.current_month = (
            max(_months_with_data) if _months_with_data else _this_month
        )
    if st.session_state.current_month not in _months:
        st.session_state.current_month = _months[0]

    _pick_col, _ = st.columns([1, 3])
    with _pick_col:
        st.session_state.current_month = st.selectbox(
            'Month', _months, index=_months.index(st.session_state.current_month),
            key='overview_month',
        )
    _month = st.session_state.current_month

    # ── Headline KPIs ────────────────────────────────────────────────────────
    # Always rendered, even at zero, so the grid never jumps between states.
    _exp_rows = [e for e in st.session_state.expenses if str(e.get('date', ''))[:7] == _month]
    _inc_rows = [i for i in st.session_state.income if str(i.get('date', ''))[:7] == _month]
    _spent = sum(float(e.get('price', 0) or 0) for e in _exp_rows)
    _earned = sum(float(i.get('amount', 0) or 0) for i in _inc_rows)
    _net = _earned - _spent
    _srate = (_net / _earned * 100) if _earned else None

    _k = st.columns(4)
    _k[0].metric('Expenses', f"{_spent:,.2f}", help=f"{len(_exp_rows)} transaction(s) in {_month}")
    _k[1].metric('Income', f"{_earned:,.2f}", help=f"{len(_inc_rows)} entry/entries in {_month}")
    _k[2].metric('Net', f"{_net:,.2f}", delta=f"{_net:+,.2f}")
    _k[3].metric('Savings rate', f"{_srate:.0f}%" if _srate is not None else '—',
                 help='Net as a share of income. Needs income recorded for this month.')

    if not st.session_state.expenses and not st.session_state.income:
        st.info('No data yet — add an expense or some income on the **Manage** tab '
                'to light up the dashboard.', icon='👋')

    # ── Budget status ────────────────────────────────────────────────────────
    # One source of truth. This used to render twice: a hand-rolled loop and then
    # again via backend.analytics.budget_utilization, showing the same numbers.
    if st.session_state.budget:
        with st.container(border=True):
            section('Budget status', f'Spend against each category limit for {_month}.')
            _spent_by_cat = {}
            for _e in _exp_rows:
                _t = _e.get('tags', 'Other')
                _spent_by_cat[_t] = _spent_by_cat.get(_t, 0) + float(_e.get('price', 0) or 0)
            for _b in st.session_state.budget:
                _used = _spent_by_cat.get(_b['category'], 0)
                _limit = float(_b.get('amount', 0) or 0)
                _pct = (_used / _limit) if _limit > 0 else 0.0
                _cur = str(_b.get('currency', 'USD')).upper()
                _lab, _bar = st.columns([1, 3])
                with _lab:
                    st.write(f"**{_b['category']}**")
                    st.caption(f"{_used:,.2f} / {_limit:,.2f} {_cur}")
                with _bar:
                    st.progress(min(_pct, 1.0))
                    if _used > _limit:
                        st.error(f"Over by {_used - _limit:,.2f} {_cur}", icon='🚨')
                    elif _pct >= 0.9:
                        st.warning(f"{_pct * 100:.0f}% used — approaching limit", icon='⚠️')

    # ── Net-worth snapshot (Max only) ────────────────────────────────────────
    section('Net-Worth Snapshot', 'Assets minus liabilities, with cash flow and commitments.')
    _pro_features = st.session_state.get('pro_features', [])
    if 'net_worth' not in _pro_features:
        upsell('Net-worth tracking', 'Max',
               detail='It totals your assets against your liabilities and tracks the gap over time.')
    else:
        try:
            _nw_payload = {
                'expenses': st.session_state.expenses,
                'income': st.session_state.income,
                'subscriptions': st.session_state.subscriptions,
                'goals': st.session_state.goals,
                'assets': st.session_state.get('assets', []),
                'liabilities': st.session_state.get('liabilities', []),
            }
            if USE_LOCAL_BACKEND:
                from backend.analytics import net_worth_snapshot
                _nw = net_worth_snapshot(_nw_payload, convert_fn=st.session_state.tracker.convert_currency)
            else:
                with st.spinner('Calculating net worth…'):
                    _resp = _backend_post('/net-worth', _nw_payload, token=st.session_state.get('pro_token'))
                _nw = (_resp.json() if _resp.ok else {'success': False}) if _resp is not None else {'success': False}
            if _nw.get('success'):
                _cur = _nw['base_currency']
                _nw_cols = st.columns(4)
                _nw_cols[0].metric('Total Assets',     f"{_nw['total_assets']:,.2f} {_cur}")
                _nw_cols[1].metric('Total Liabilities', f"{_nw['total_liabilities']:,.2f} {_cur}")
                _nw_cols[2].metric('Net Cash Flow',     f"{_nw['net_cash_flow']:,.2f} {_cur}")
                _nw_cols[3].metric('Net Worth',         f"{_nw['estimated_net_worth']:,.2f} {_cur}")
                _nw_cols2 = st.columns(2)
                _nw_cols2[0].metric('Monthly Subscription Burden', f"{_nw['monthly_subscription_burden']:,.2f} {_cur}")
                _nw_cols2[1].metric('Goal Contributions to Date',  f"{_nw['goal_contributions_to_date']:,.2f} {_cur}")
                if _nw.get('assets_by_type'):
                    st.caption('Assets: ' + ' · '.join(f"{k} {v:,.2f}" for k, v in _nw['assets_by_type'].items()))
                if _nw.get('liabilities_by_type'):
                    st.caption('Liabilities: ' + ' · '.join(f"{k} {v:,.2f}" for k, v in _nw['liabilities_by_type'].items()))
        except Exception as _e:
            st.info(f'Net-worth snapshot unavailable: {_e}')

    # ── Savings rate ─────────────────────────────────────────────────────────
    section('Savings Rate', 'Share of income kept, by month.')
    try:
        from backend.analytics import savings_rate_history as _srh
        # Signature is (expenses, income) — these used to be passed the other way
        # round, which silently inverted every rate. 'history' is a LIST of
        # {month, income, expenses, savings_rate_pct}; this read it as a dict
        # keyed by month and asked for 'rate_pct'/'savings', so it always threw.
        _sr = _srh(st.session_state.expenses, st.session_state.income)
        _hist = _sr.get('history') or []
        if _sr.get('success') and _hist:
            _recent = _hist[-6:]
            _sr_cols = st.columns(len(_recent))
            for _sri, _srd in enumerate(_recent):
                _rate = _srd.get('savings_rate_pct')
                _saved = float(_srd.get('income', 0) or 0) - float(_srd.get('expenses', 0) or 0)
                _sr_cols[_sri].metric(
                    _srd.get('month', '—'),
                    f"{_rate:.1f}%" if _rate is not None else 'N/A',
                    delta=f"{_saved:+,.2f}",
                )
        else:
            st.info('Add income and expenses to track savings rate.')
    except Exception as _e:
        st.info(f'Savings rate unavailable: {_e}')


    # ── Spending forecast ────────────────────────────────────────────────────
    section('Spending Forecast', 'Linear trend per category, projected to next month.')
    _fc_notice = None
    try:
        if USE_LOCAL_BACKEND:
            from backend.analytics import forecast_spending
            _fc = forecast_spending(st.session_state.expenses)
        else:
            with st.spinner('Forecasting…'):
                _resp = _backend_post('/forecast', {'expenses': st.session_state.expenses, 'base_currency': 'USD'},
                                      token=st.session_state.get('pro_token'))
            _fc, _fc_notice = _gated(_resp, 'Spending forecast')
            if _fc_notice:
                _notice(_fc_notice)
            _fc = _fc or {}
        if _fc.get('success') and _fc.get('forecasts'):
            st.caption(f"Based on {_fc['based_on_months']} month(s) of history ({_fc['base_currency']} only)")
            _fc_cols = st.columns(3)
            for _fi, (_cat, _info) in enumerate(_fc['forecasts'].items()):
                _arrow = '↑' if _info['trend'] == 'increasing' else '↓' if _info['trend'] == 'decreasing' else '→'
                _fc_cols[_fi % 3].metric(f'{_cat} {_arrow}', f"{_info['next_month_forecast']:,.2f}", delta=f"avg {_info['current_avg']:,.2f}")
        elif not _fc_notice:
            st.info('Not enough expense history to generate a forecast yet.')
    except Exception as _e:
        st.info(f'Forecast unavailable: {_e}')


    # ── Anomaly detection ────────────────────────────────────────────────────
    section('Unusual Expenses', 'Transactions far from their category average.')
    _ad_notice = None
    try:
        if USE_LOCAL_BACKEND:
            from backend.analytics import detect_anomalies
            _ad = detect_anomalies(st.session_state.expenses)
        else:
            with st.spinner('Scanning for outliers…'):
                _resp = _backend_post('/detect-anomalies', {'expenses': st.session_state.expenses, 'z_threshold': 2.5},
                                      token=st.session_state.get('pro_token'))
            _ad, _ad_notice = _gated(_resp, 'Anomaly detection')
            if _ad_notice:
                _notice(_ad_notice)
            _ad = _ad or {}
        if _ad.get('anomalies'):
            st.caption(f"{_ad['count']} statistically unusual expense(s) detected:")
            for _anom in _ad['anomalies']:
                _dev_sign = '+' if _anom['deviation'] > 0 else ''
                st.warning(
                    f"**{_anom.get('purchased', '—')}** — "
                    f"{_anom['price']:.2f} {_anom.get('currency','').upper()} "
                    f"({_dev_sign}{_anom['deviation']:.2f} from {_anom['category_mean']:.2f} avg in {_anom['tags']}, "
                    f"z={_anom['z_score']})"
                )
        elif not _ad_notice:
            # Only claim "nothing unusual" when the check actually RAN.
            st.success('No unusual expenses detected.')
    except Exception as _e:
        st.info(f'Anomaly detection unavailable: {_e}')


    # ── Financial health score ───────────────────────────────────────────────
    section('Financial Health Score', 'A 0-100 composite across savings, budgets and debt.')
    try:
        from backend.analytics import financial_health_score as _fhs
        _fhs_data = {
            'expenses': st.session_state.expenses,
            'income': st.session_state.income,
            'budget': st.session_state.budget,
            'subscriptions': st.session_state.subscriptions,
            'goals': st.session_state.goals,
        }
        _hs = _fhs(_fhs_data)
        if _hs['success']:
            _hs_col1, _hs_col2 = st.columns([1, 3])
            with _hs_col1:
                _grade_colors = {'A': '🟢', 'B': '🟡', 'C': '🟠', 'D': '🔴', 'F': '🔴'}
                st.metric('Score', f"{_hs['score']} / 100")
                st.markdown(f"**Grade: {_grade_colors.get(_hs['grade'], '')} {_hs['grade']}**")
            with _hs_col2:
                # analytics.financial_health_score returns this under 'breakdown';
                # this panel used to read 'pillars' and so always threw a KeyError.
                _p = _hs.get('breakdown', {})
                _p_cols = st.columns(4)
                _p_cols[0].metric('Savings Rate', f"{_p.get('savings_rate', 0):.0f}/100")
                _p_cols[1].metric('Budget Adherence', f"{_p.get('budget_adherence', 0):.0f}/100")
                _p_cols[2].metric('Subscription Burden', f"{_p.get('subscription_burden', 0):.0f}/100")
                _p_cols[3].metric('Goal Consistency', f"{_p.get('goal_consistency', 0):.0f}/100")
    except Exception as _e:
        st.info(f'Health score unavailable: {_e}')


    # ── Subscription renewal alerts ──────────────────────────────────────────
    section('Upcoming Renewals', 'Subscriptions billing in the next 30 days.')
    try:
        from backend.analytics import upcoming_renewals as _upcoming_renewals
        _ur = _upcoming_renewals(st.session_state.subscriptions, days_ahead=30)
        # analytics.upcoming_renewals returns 'renewals', each carrying
        # 'next_renewal'. This panel read 'upcoming'/'next_billing_date'/
        # 'days_until' — none of which exist — so it always threw a KeyError.
        _renewals = _ur.get('renewals', [])
        if _renewals:
            st.caption(f"{_ur.get('count', len(_renewals))} subscription(s) renewing in the next 30 days:")
            _today = _dtm.now().date()
            for _sub in _renewals:
                _when = _sub.get('next_renewal', '')
                try:
                    _days = (_dtm.strptime(_when, '%Y-%m-%d').date() - _today).days
                    _label = ('today' if _days == 0
                              else f'in {_days} day{"s" if _days != 1 else ""}')
                except (ValueError, TypeError):
                    _label = 'soon'
                st.warning(
                    f"**{_sub.get('name', '—')}** — {float(_sub.get('price', 0) or 0):.2f} "
                    f"{str(_sub.get('currency', '')).upper()} renews {_label} ({_when})"
                )
        else:
            st.success('No renewals due in the next 30 days.')
    except Exception as _e:
        st.info(f'Renewal alerts unavailable: {_e}')


    # ── Goal progress ────────────────────────────────────────────────────────
    section('Goal Progress', 'How close each savings goal is, and when it lands.')
    try:
        from backend.analytics import goal_progress as _goal_progress
        _gp = _goal_progress(st.session_state.goals)
        # analytics.goal_progress returns 'saved_estimate' / 'progress_pct';
        # this panel read 'saved' / 'percent' and so always threw a KeyError.
        if _gp.get('goals'):
            for _g in _gp['goals']:
                _saved = float(_g.get('saved_estimate', 0) or 0)
                _target = float(_g.get('target', 0) or 0)
                _pct = float(_g.get('progress_pct', 0) or 0)
                st.markdown(
                    f"**{_g.get('name', '—')}** — {_saved:,.2f} / {_target:,.2f} "
                    f"{str(_g.get('currency', 'USD')).upper()} · ETA: {_g.get('eta', 'unknown')}"
                )
                st.progress(min(1.0, _pct / 100), text=f"{_pct:.1f}%")
        else:
            st.info('No goals found. Add a goal to track progress.')
    except Exception as _e:
        st.info(f'Goal progress unavailable: {_e}')


    # ── Natural language query ───────────────────────────────────────────────
    section('Ask About Your Finances', 'Natural-language questions answered from your data.')
    _nl_ai_ok = False
    try:
        from backend.ai import is_configured as _ai_configured_nl
        _nl_ai_ok = _ai_configured_nl()
    except Exception:
        pass
    if not _nl_ai_ok and not USE_LOCAL_BACKEND:
        st.info('Set an AI_API_KEY to enable natural language queries about your finances.')
    else:
        _nl_question = st.text_input('Ask anything about your finances …', key='nl_query_input', max_chars=500)
        if st.button('Ask', key='nl_query_btn') and _nl_question.strip():
            with st.spinner('Thinking …'):
                _nl_data = {
                    'expenses': st.session_state.expenses, 'income': st.session_state.income,
                    'budget': st.session_state.budget, 'subscriptions': st.session_state.subscriptions,
                    'goals': st.session_state.goals,
                }
                try:
                    if USE_LOCAL_BACKEND:
                        from backend.ai import answer_query as _answer_query
                        _nl_answer = _answer_query(_nl_question, _nl_data)
                    else:
                        _resp = _backend_post('/query', {'question': _nl_question, 'data': _nl_data},
                                                  token=st.session_state.get('pro_token'))
                        _nl_payload, _nl_notice = _gated(_resp, 'Natural-language queries')
                        if _nl_notice:
                            # Same treatment as the other gated panels: say it is
                            # locked, not "Error 403".
                            _nl_answer = _nl_notice[1]
                        else:
                            _nl_answer = _nl_payload.get('answer', '(empty response)')
                    st.session_state['nl_last_answer'] = _nl_answer
                except Exception as _exc:
                    st.error(f'Query failed: {_exc}')
        if st.session_state.get('nl_last_answer'):
            st.markdown(st.session_state['nl_last_answer'])


# ── Add ──────────────────────────────────────────────────────────────────────
with tab_add:
    st.subheader('Add Material')
    choice = st.selectbox('What to add?', options=['Expenses', 'Income', 'Budget', 'Subscription', 'Goal'], key='add_choice')

    if choice == 'Expenses':
        # Receipt OCR expander
        with st.expander('Scan a Receipt', expanded=False):
            ocr_available = bool(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))
            if not ocr_available:
                st.info('Set the GOOGLE_APPLICATION_CREDENTIALS environment variable to enable receipt scanning.')
            uploaded_receipt = st.file_uploader('Upload receipt image', type=['png', 'jpg', 'jpeg', 'webp'], key='receipt_uploader')
            if uploaded_receipt is not None:
                if ocr_available:
                    try:
                        from backend.ocr import parse_receipt
                        with st.spinner('Scanning receipt...'):
                            result = parse_receipt(uploaded_receipt.read())
                        st.session_state['ocr_merchant'] = result.get('merchant', '')
                        st.session_state['ocr_total'] = float(result.get('total', 0.0))
                        raw_date = result.get('date', '')
                        if raw_date:
                            import datetime
                            for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y'):
                                try:
                                    st.session_state['ocr_date'] = datetime.datetime.strptime(raw_date, fmt).date()
                                    break
                                except ValueError:
                                    pass
                        st.success('Receipt scanned — fields pre-filled below.')
                    except Exception as exc:
                        st.error(f'OCR failed: {exc}')
                else:
                    st.info('Set GOOGLE_APPLICATION_CREDENTIALS to scan receipts.')

        # ── AI category suggestion ───────────────────────────────────────────
        try:
            from backend.ai import is_configured as _ai_ok_add, suggest_category as _suggest_cat
            if _ai_ok_add():
                with st.expander('Suggest Category with AI', expanded=False):
                    _sug_merchant = st.text_input('Merchant name', key='ai_sug_merchant')
                    _sug_amount = st.number_input('Amount', min_value=0.0, step=0.01, key='ai_sug_amount')
                    if st.button('Suggest', key='ai_sug_btn') and _sug_merchant.strip():
                        with st.spinner('Thinking …'):
                            try:
                                _cat_result = _suggest_cat(_sug_merchant, _sug_amount)
                                st.session_state['ai_suggested_category'] = _cat_result
                            except Exception as _exc:
                                st.error(f'Suggestion failed: {_exc}')
                    if st.session_state.get('ai_suggested_category'):
                        st.info(f"Suggested category: **{st.session_state['ai_suggested_category']}**")
        except Exception as _sect_err:
            # Was `pass`: a failure here silently removed the whole
            # section instead of saying anything.
            st.caption(f'Receipt scan / AI category unavailable: {_sect_err}')

        with st.expander('Recurring Expenses', expanded=False):
            if not st.session_state.recurring_expenses:
                st.write("No recurring expenses found.")
            else:
                if st.button('Apply all recurring expenses for this month', key='apply_all_rec_exp'):
                    _aar = st.session_state.tracker.apply_all_recurring(st.session_state.current_month)
                    st.success(_aar['message'])
                    sync_data()
                    st.rerun()
                st.divider()
                for idx, expense in enumerate(st.session_state.recurring_expenses):
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                    with col1:
                        st.write(f"**{expense['purchased']}**")
                    with col2:
                        st.write(f"{expense['amount']:.2f} {expense['currency']}")
                    with col3:
                        st.write(f"{expense['tags']}")
                    with col4:
                        if st.button(f"Readd {expense['purchased']}", key=f'readd_expense_{idx}'):
                            results = st.session_state.tracker.add_expenses(
                                expense['amount'], expense['purchased'], expense['tags'],
                                expense['currency'], str(st.session_state.current_month + '-01'),
                                'Readded from recurring expenses'
                            )
                            if results['success']:
                                st.success(results['message'])
                                sync_data()
                                st.rerun()
                            else:
                                st.error(results['message'])
                    st.divider()

        import datetime as _dt
        _default_merchant = st.session_state.get('ocr_merchant', '')
        _default_amount = st.session_state.get('ocr_total', 0.0)
        _default_date = st.session_state.get('ocr_date', _dt.date.today())

        with st.form('add_expenses_form'):
            col1, col2 = st.columns(2)
            with col1:
                expense_purchased = st.text_input('What was purchased?', value=_default_merchant, key='add_exp_purchased')
            with col2:
                expense_amount = st.number_input('Expense Amount', min_value=0.0, step=0.01, value=_default_amount, key='add_exp_amount')
            _exp_cat_opts = ['Food', 'Transport', 'Entertainment', 'Utilities', 'Bills', 'Other']
            _ai_cat = st.session_state.get('ai_suggested_category', None)
            _exp_cat_idx = _exp_cat_opts.index(_ai_cat) if _ai_cat in _exp_cat_opts else 0
            expense_category = st.selectbox('Expense Category', options=_exp_cat_opts, index=_exp_cat_idx, key='add_exp_category')
            expense_currency = st.selectbox('Expense Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'BTC', 'ETH', 'USDC', 'SOL', 'Other'], key='add_exp_currency')
            expense_date = st.date_input('Expense Date', value=_default_date, key='add_exp_date')
            expense_notes = st.text_area('Expense Notes', key='add_exp_notes')
            recurring = st.checkbox('Recurring Expense', key='add_exp_recurring')
            if st.form_submit_button('Add Expense'):
                if recurring:
                    results = st.session_state.tracker.add_recurring_expense(expense_amount, expense_purchased, expense_category, expense_currency)
                else:
                    results = st.session_state.tracker.add_expenses(expense_amount, expense_purchased, expense_category, expense_currency, str(expense_date), expense_notes)
                if results['success']:
                    for k in ('ocr_merchant', 'ocr_total', 'ocr_date', 'ai_suggested_category'):
                        st.session_state.pop(k, None)
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

    elif choice == 'Income':
        with st.expander('Recurring Income', expanded=False):
            if not st.session_state.recurring_income:
                st.write("No recurring income found.")
            else:
                if st.button('Apply all recurring income for this month', key='apply_all_rec_inc'):
                    _aari = st.session_state.tracker.apply_all_recurring(st.session_state.current_month)
                    st.success(_aari['message'])
                    sync_data()
                    st.rerun()
                st.divider()
                for idx, income in enumerate(st.session_state.recurring_income):
                    col1, col2, col3 = st.columns([3, 2, 2])
                    with col1:
                        st.write(f"**{income['source']}**")
                    with col2:
                        st.write(f"{income['amount']:.2f} {income['currency']}")
                    with col3:
                        if st.button(f"Readd {income['source']}", key=f'readd_income_{idx}'):
                            results = st.session_state.tracker.add_income(
                                income['amount'], income['source'],
                                str(st.session_state.current_month + '-01'),
                                income['currency'], 'Readded from recurring income'
                            )
                            if results['success']:
                                st.success(results['message'])
                                sync_data()
                                st.rerun()
                            else:
                                st.error(results['message'])
                    st.divider()

        with st.form('add_income_form'):
            col1, col2 = st.columns(2)
            with col1:
                income_source = st.text_input('Income Source', key='add_inc_source')
            with col2:
                income_amount = st.number_input('Income Amount', min_value=0.0, step=0.01, key='add_inc_amount')
            income_currency = st.selectbox('Income Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'BTC', 'ETH', 'USDC', 'SOL', 'Other'], key='add_inc_currency')
            income_date = st.date_input('Income Date', key='add_inc_date')
            income_notes = st.text_area('Income Notes', key='add_inc_notes')
            recurring = st.checkbox('Recurring Income', key='add_inc_recurring')
            if st.form_submit_button('Add Income'):
                if recurring:
                    results = st.session_state.tracker.add_recurring_income(income_amount, income_source, income_currency)
                else:
                    results = st.session_state.tracker.add_income(income_amount, income_source, str(income_date), income_currency, income_notes)
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

    elif choice == 'Budget':
        try:
            from backend.ai import is_configured as _ai_ok_bud, recommend_budgets as _recommend_budgets
            if _ai_ok_bud():
                with st.expander('Get AI Budget Recommendations', expanded=False):
                    if st.button('Analyse my spending and suggest budgets', key='ai_bud_btn'):
                        with st.spinner('Analysing …'):
                            try:
                                _bud_rec = _recommend_budgets(st.session_state.expenses, st.session_state.budget)
                                if _bud_rec['success']:
                                    st.session_state['ai_budget_suggestions'] = _bud_rec['suggestions']
                                else:
                                    st.error(_bud_rec.get('message', 'Recommendation failed'))
                            except Exception as _exc:
                                st.error(f'Recommendation failed: {_exc}')
                    if st.session_state.get('ai_budget_suggestions'):
                        st.caption('Suggested monthly limits (click a category below to pre-fill the form):')
                        for _bcat, _bamt in st.session_state['ai_budget_suggestions'].items():
                            if st.button(f'{_bcat}: {_bamt:.2f}', key=f'ai_bud_pick_{_bcat}'):
                                st.session_state['ai_bud_prefill_cat'] = _bcat
                                st.session_state['ai_bud_prefill_amt'] = _bamt
                                st.rerun()
        except Exception as _sect_err:
            # Was `pass`: a failure here silently removed the whole
            # section instead of saying anything.
            st.caption(f'AI budget recommendations unavailable: {_sect_err}')

        _bud_cat_opts = ['Food', 'Transport', 'Entertainment', 'Utilities', 'Bills', 'Other']
        _ai_bud_cat = st.session_state.get('ai_bud_prefill_cat', None)
        _ai_bud_cat_idx = _bud_cat_opts.index(_ai_bud_cat) if _ai_bud_cat in _bud_cat_opts else 0
        _ai_bud_amt = st.session_state.get('ai_bud_prefill_amt', 0.0)

        with st.form('add_budget_form'):
            budget_amount = st.number_input('Budget Amount', min_value=0.0, step=0.01, value=_ai_bud_amt, key='add_bud_amount')
            budget_category = st.selectbox('Budget Category', options=_bud_cat_opts, index=_ai_bud_cat_idx, key='add_bud_category')
            budget_currency = st.selectbox('Budget Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'BTC', 'ETH', 'USDC', 'SOL', 'Other'], key='add_bud_currency')
            if st.form_submit_button('Add Budget'):
                results = st.session_state.tracker.create_budget(budget_category, budget_amount, budget_currency)
                if results['success']:
                    for _k in ('ai_bud_prefill_cat', 'ai_bud_prefill_amt', 'ai_budget_suggestions'):
                        st.session_state.pop(_k, None)
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

    elif choice == 'Subscription':
        with st.form('add_subscription_form'):
            subscription_name = st.text_area('Subscription Name', key='add_sub_name')
            subscription_price = st.number_input('Subscription Price', min_value=0.0, step=0.01, key='add_sub_price')
            subscription_currency = st.selectbox('Subscription Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'BTC', 'ETH', 'USDC', 'SOL', 'Other'], key='add_sub_currency')
            subscription_start_date = st.date_input('Start Date', key='add_sub_date')
            if st.form_submit_button('Add Subscription'):
                results = st.session_state.tracker.add_subscriptions(subscription_name, subscription_price, subscription_currency, str(subscription_start_date))
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

    elif choice == 'Goal':
        with st.form('add_goal_form'):
            goal_name = st.text_area('Goal Name', key='add_goal_name')
            goal_target_amount = st.number_input('Goal Target Amount', min_value=0.0, step=0.01, key='add_goal_target')
            goal_monthly_contribution = st.number_input('Monthly Contribution', min_value=0.0, step=0.01, key='add_goal_contribution')
            goal_start_date = st.date_input('Goal Start Date', key='add_goal_date')
            goal_currency = st.selectbox('Goal Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'BTC', 'ETH', 'USDC', 'SOL', 'Other'], key='add_goal_currency')
            if st.form_submit_button('Add Goal'):
                results = st.session_state.tracker.create_goal(goal_name, goal_target_amount, str(goal_start_date), goal_monthly_contribution, goal_currency)
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

# ── Delete ───────────────────────────────────────────────────────────────────
with tab_delete:
    st.subheader('Delete Material')
    choice = st.selectbox('What to Delete?', options=['Expenses', 'Income', 'Budget', 'Subscription'], key='delete_choice')

    if choice == 'Expenses':
        with st.form('delete_expenses_form'):
            expense_id = st.number_input('Expense ID', min_value=1, step=1, key='del_exp_id')
            if st.form_submit_button('Delete Expense'):
                results = st.session_state.tracker.delete_expenses(expense_id)
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

    elif choice == 'Income':
        with st.form('delete_income_form'):
            income_id = st.number_input('Income ID', min_value=1, step=1, key='del_inc_id')
            if st.form_submit_button('Delete Income'):
                results = st.session_state.tracker.delete_income(income_id)
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

    elif choice == 'Budget':
        with st.form('delete_budget_form'):
            budget_category = st.text_input('Current Budget Category', key='del_bud_category')
            if st.form_submit_button('Delete Budget'):
                results = st.session_state.tracker.delete_budget(budget_category)
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

    elif choice == 'Subscription':
        with st.form('delete_subscription_form'):
            subscription_name = st.text_area('Subscription Name', key='del_sub_name')
            if st.form_submit_button('Delete Subscription'):
                results = st.session_state.tracker.delete_subscription(subscription_name)
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

# ── Edit ─────────────────────────────────────────────────────────────────────
with tab_edit:
    st.subheader('Edit Material')
    choice = st.selectbox('What to Edit?', options=['Expenses', 'Income', 'Budget', 'Subscription'], key='edit_choice')

    if choice == 'Expenses':
        with st.form('edit_expenses_form'):
            col1, col2 = st.columns(2)
            with col1:
                expense_id = st.number_input('Expense ID', min_value=1, step=1, key='edit_exp_id')
            with col2:
                expense_name = st.text_area('Expense Name', key='edit_exp_name')
            expense_amount = st.number_input('Expense Amount', min_value=0.0, step=0.01, key='edit_exp_amount')
            expense_category = st.selectbox('Expense Category', options=['Food', 'Transport', 'Entertainment', 'Utilities', 'Bills', 'Other'], key='edit_exp_category')
            expense_currency = st.selectbox('Expense Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'BTC', 'ETH', 'USDC', 'SOL', 'Other'], key='edit_exp_currency')
            expense_date = st.date_input('Expense Date', key='edit_exp_date')
            expense_notes = st.text_area('Expense Notes', key='edit_exp_notes')
            if st.form_submit_button('Edit Expense'):
                results = st.session_state.tracker.edit_expenses(expense_id, expense_amount, expense_name, expense_category, str(expense_date), expense_currency, expense_notes)
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

    elif choice == 'Income':
        with st.form('edit_income_form'):
            col1, col2 = st.columns(2)
            with col1:
                income_id = st.number_input('Income ID', min_value=1, step=1, key='edit_inc_id')
            with col2:
                income_source = st.text_area('New Income Name', key='edit_inc_source')
            income_amount = st.number_input('Change Income Amount', min_value=0.0, step=0.01, key='edit_inc_amount')
            income_currency = st.selectbox('Change Income Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'BTC', 'ETH', 'USDC', 'SOL', 'Other'], key='edit_inc_currency')
            income_date = st.date_input('Change Income Date', key='edit_inc_date')
            income_notes = st.text_area('Update Income Notes', key='edit_inc_notes')
            if st.form_submit_button('Edit Income'):
                results = st.session_state.tracker.edit_income(income_id, income_amount, income_source, str(income_date), income_currency, income_notes)
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

    elif choice == 'Budget':
        with st.form('edit_budget_form'):
            previous_category = st.text_input('Current Budget Category', key='edit_bud_prev_category')
            budget_amount = st.number_input('New Budget Amount', min_value=0.0, step=0.01, key='edit_bud_amount')
            budget_category = st.selectbox('New Budget Category', options=['Food', 'Transport', 'Entertainment', 'Utilities', 'Bills', 'Other'], key='edit_bud_category')
            budget_currency = st.selectbox('Change Budget Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'BTC', 'ETH', 'USDC', 'SOL', 'Other'], key='edit_bud_currency')
            if st.form_submit_button('Edit Budget'):
                results = st.session_state.tracker.update_budget(previous_category, budget_category, budget_amount, budget_currency)
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

    elif choice == 'Subscription':
        with st.form('edit_subscription_form'):
            subscription_name = st.text_area('Current Subscription Name', key='edit_sub_name')
            subscription_new_name = st.text_input('New Subscription Name (leave blank to keep)', key='edit_sub_new_name')
            subscription_price = st.number_input('Subscription Price', min_value=0.0, step=0.01, key='edit_sub_price')
            subscription_currency = st.selectbox('Subscription Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'BTC', 'ETH', 'USDC', 'SOL', 'Other'], key='edit_sub_currency')
            if st.form_submit_button('Edit Subscription'):
                results = st.session_state.tracker.edit_subscription(
                    subscription_name,
                    price=subscription_price if subscription_price > 0 else None,
                    name=subscription_new_name if subscription_new_name else None,
                    currency=subscription_currency,
                )
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

# ── View Expenses ────────────────────────────────────────────────────────────
with tab_view_expenses:
    st.subheader('View Expenses')

    # ── Spending charts ──────────────────────────────────────────────────────
    # Native Streamlit charts, not matplotlib: these are vector, interactive,
    # responsive, and follow the viewer's light/dark theme. The matplotlib
    # versions rendered fixed-size white PNGs that were unreadable in dark mode
    # and leaked a figure per rerun.
    if st.session_state.expenses:
        try:
            import pandas as _pd
            from backend.analytics import (spending_by_category as _sbc,
                                           monthly_totals as _mt,
                                           monthly_comparison as _mc)

            with st.expander('Spending insights', expanded=False):
                _chart_col1, _chart_col2 = st.columns(2)

                # Category breakdown for the selected month.
                # by_category is a LIST of {category,total,count,pct} — reading
                # it as a dict with .keys() was raising on every load.
                with _chart_col1:
                    st.caption(f"By category — {st.session_state.current_month}")
                    _rows = _sbc(st.session_state.expenses,
                                 month=st.session_state.current_month).get('by_category') or []
                    if _rows:
                        _df = _pd.DataFrame(_rows).set_index('category')[['total']]
                        st.bar_chart(_df, horizontal=True, height=260)
                    else:
                        st.info('No expenses in this month.')

                # Spend per month over all history. `monthly` is also a LIST.
                with _chart_col2:
                    st.caption('Monthly trend')
                    _mrows = _mt(st.session_state.expenses).get('monthly') or []
                    if len(_mrows) >= 2:
                        _mdf = _pd.DataFrame(_mrows).set_index('month')[['total']]
                        st.line_chart(_mdf, height=260)
                    else:
                        st.info('Two months of history needed for a trend.')

                # Month-on-month comparison
                _all_months = sorted({str(e.get('date', ''))[:7]
                                      for e in st.session_state.expenses if e.get('date')})
                if len(_all_months) >= 2:
                    st.divider()
                    st.caption('Compare two months')
                    _cmp_col1, _cmp_col2 = st.columns(2)
                    _cmp_a = _cmp_col1.selectbox('Month A', _all_months,
                                                 index=len(_all_months) - 2, key='cmp_month_a')
                    _cmp_b = _cmp_col2.selectbox('Month B', _all_months,
                                                 index=len(_all_months) - 1, key='cmp_month_b')
                    if _cmp_a != _cmp_b:
                        # returns {'comparison': [{category, <month_a>, <month_b>, change, ...}]}
                        _crows = _mc(st.session_state.expenses, _cmp_a, _cmp_b).get('comparison') or []
                        if _crows:
                            _cdf = _pd.DataFrame(_crows).set_index('category')
                            _cols = [c for c in (_cmp_a, _cmp_b) if c in _cdf.columns]
                            if _cols:
                                st.bar_chart(_cdf[_cols], height=280)
                        else:
                            st.info('Nothing to compare in those months.')
                    else:
                        st.caption('Pick two different months.')
        except Exception as _chart_err:
            st.info(f'Charts unavailable: {_chart_err}')

    import datetime as _dt_exp
    _exp_filter_cols = st.columns([3, 2, 2])
    search = _exp_filter_cols[0].text_input('Search expenses ...', '', key='view_exp_search')
    _exp_date_from = _exp_filter_cols[1].date_input('From', value=None, key='view_exp_date_from')
    _exp_date_to = _exp_filter_cols[2].date_input('To', value=None, key='view_exp_date_to')

    expenses = st.session_state.expenses
    if search:
        expenses = [e for e in expenses if search.lower() in e['tags'].lower() or search.lower() in (e['notes'] or '').lower()]
    if _exp_date_from:
        expenses = [e for e in expenses if e.get('date', '') >= str(_exp_date_from)]
    if _exp_date_to:
        expenses = [e for e in expenses if e.get('date', '') <= str(_exp_date_to)]

    if expenses:
        for expense in expenses:
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                st.write(f"**{expense['price']:.2f} {expense['currency'].upper()}**")
            with col2:
                st.write(f"**{expense['tags']}**")
            with col3:
                st.write(f"{expense['date']}")
            with col4:
                st.write(f"{expense['notes'] if expense['notes'] else ''}")
            st.divider()
    elif search:
        st.write(f"No expenses found using search term '{search}'.")
    else:
        st.write("No expenses found. Add expenses to get started.")

    with st.form('import_expenses_form', clear_on_submit=True):
        uploaded_csv = st.file_uploader('Import expenses from .csv', type=['csv'], key='expenses_csv_upload')
        if st.form_submit_button('Import') and uploaded_csv:
            import pandas as _pd
            try:
                preview = _pd.read_csv(uploaded_csv)
                st.dataframe(preview.head(3))
                uploaded_csv.seek(0)
                st.session_state.tracker.import_from_csv('expenses', uploaded_csv)
                sync_data()
                st.success(f'Imported {len(preview)} rows successfully.')
                st.rerun()
            except Exception as _e:
                st.error(f'Import failed: {_e}')
    result = st.session_state.tracker.export_to_csv('expenses', 'expenses.csv')
    if result['success']:
        st.download_button(label='Export expenses to .csv', data=result['data'].to_csv(index=False).encode('utf-8'), file_name='expenses.csv', mime='text/csv', key='exp_download')
    pdf_result = st.session_state.tracker.export_to_pdf('expenses', 'expenses.pdf')
    if pdf_result['success']:
        st.download_button(label='Export expenses to .pdf', data=pdf_result['data'], file_name='expenses.pdf', mime='application/pdf', key='exp_pdf_download')

# ── View Income ──────────────────────────────────────────────────────────────
with tab_view_income:
    st.subheader('View Income')

    # Income vs expenses chart
    if st.session_state.income or st.session_state.expenses:
        try:
            import pandas as _pd_inc
            from backend.analytics import income_vs_expenses as _ive
            with st.expander('Income vs expenses', expanded=False):
                # Signature is (expenses, income) — these were passed the other
                # way round, and the result is {'monthly': [ {month, income,
                # expenses, net} ]}, not separate 'months'/'income' lists.
                _rows = _ive(st.session_state.expenses,
                             st.session_state.income).get('monthly') or []
                if _rows:
                    _df = _pd_inc.DataFrame(_rows).set_index('month')
                    st.bar_chart(_df[['income', 'expenses']], height=300)
                    _latest = _rows[-1]
                    _c1, _c2, _c3 = st.columns(3)
                    _c1.metric(f"Income ({_latest['month']})", f"{_latest['income']:,.2f}")
                    _c2.metric('Expenses', f"{_latest['expenses']:,.2f}")
                    _c3.metric('Net', f"{_latest['net']:,.2f}", delta=f"{_latest['net']:+,.0f}")
                else:
                    st.info('Not enough data for a chart yet.')
        except Exception as _e_ive:
            st.info(f'Chart unavailable: {_e_ive}')

    _inc_filter_cols = st.columns([3, 2, 2])
    search = _inc_filter_cols[0].text_input('Search income ...', '', key='view_inc_search')
    _inc_date_from = _inc_filter_cols[1].date_input('From', value=None, key='view_inc_date_from')
    _inc_date_to = _inc_filter_cols[2].date_input('To', value=None, key='view_inc_date_to')

    income_list = st.session_state.income
    if search:
        income_list = [i for i in income_list if search.lower() in i['source'].lower() or search.lower() in (i['notes'] or '').lower()]
    if _inc_date_from:
        income_list = [i for i in income_list if i.get('date', '') >= str(_inc_date_from)]
    if _inc_date_to:
        income_list = [i for i in income_list if i.get('date', '') <= str(_inc_date_to)]

    if income_list:
        for income_item in income_list:
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                st.write(f"**{income_item['amount']:.2f} {income_item['currency'].upper()}**")
            with col2:
                st.write(f"**{income_item['source']}**")
            with col3:
                st.write(f"{income_item['date']}")
            with col4:
                st.write(f"{income_item['notes'] if income_item['notes'] else ''}")
            st.divider()
    elif search:
        st.write(f"No income found using search term '{search}'.")
    else:
        st.write("No income found. Add income to get started.")

    with st.form('import_income_form', clear_on_submit=True):
        uploaded_csv = st.file_uploader('Import income from .csv', type=['csv'], key='income_csv_upload')
        if st.form_submit_button('Import') and uploaded_csv:
            import pandas as _pd
            try:
                preview = _pd.read_csv(uploaded_csv)
                st.dataframe(preview.head(3))
                uploaded_csv.seek(0)
                st.session_state.tracker.import_from_csv('income', uploaded_csv)
                sync_data()
                st.success(f'Imported {len(preview)} rows successfully.')
                st.rerun()
            except Exception as _e:
                st.error(f'Import failed: {_e}')
    result = st.session_state.tracker.export_to_csv('income', 'income.csv')
    if result['success']:
        st.download_button(label='Export income to .csv', data=result['data'].to_csv(index=False).encode('utf-8'), file_name='income.csv', mime='text/csv', key='inc_download')
    pdf_result = st.session_state.tracker.export_to_pdf('income', 'income.pdf')
    if pdf_result['success']:
        st.download_button(label='Export income to .pdf', data=pdf_result['data'], file_name='income.pdf', mime='application/pdf', key='inc_pdf_download')

# ── View Subscriptions ───────────────────────────────────────────────────────
with tab_view_subscriptions:
    st.subheader('View Subscriptions')
    search = st.text_input('Search subscriptions ...', '', key='view_sub_search')
    if search:
        subscriptions = [s for s in st.session_state.subscriptions if search.lower() in s['name'].lower()]
    else:
        subscriptions = st.session_state.subscriptions

    if subscriptions:
        for subscription_item in subscriptions:
            col1, col2 = st.columns([3, 2])
            with col1:
                st.write(f"**{subscription_item['name']}**")
            with col2:
                st.write(f"**{float(subscription_item['price']):.2f} {subscription_item['currency'].upper()}**")
    elif search:
        st.write(f"No subscriptions found using search term '{search}'.")
    else:
        st.write("No subscriptions found. Add subscriptions to get started.")

    with st.form('import_subscriptions_form', clear_on_submit=True):
        uploaded_csv = st.file_uploader('Import subscriptions from .csv', type=['csv'], key='subscriptions_csv_upload')
        if st.form_submit_button('Import') and uploaded_csv:
            import pandas as _pd
            try:
                preview = _pd.read_csv(uploaded_csv)
                st.dataframe(preview.head(3))
                uploaded_csv.seek(0)
                st.session_state.tracker.import_from_csv('subscriptions', uploaded_csv)
                sync_data()
                st.success(f'Imported {len(preview)} rows successfully.')
                st.rerun()
            except Exception as _e:
                st.error(f'Import failed: {_e}')
    result = st.session_state.tracker.export_to_csv('subscriptions', 'subscriptions.csv')
    if result['success']:
        st.download_button(label='Export subscriptions to .csv', data=result['data'].to_csv(index=False).encode('utf-8'), file_name='subscriptions.csv', mime='text/csv', key='sub_download')

# ── Assets & Liabilities (Max only) ──────────────────────────────────────────
with tab_net_worth:
    if 'net_worth' not in st.session_state.get('pro_features', []):
        upsell('Assets & liabilities', 'Max',
               detail='Record what you own and what you owe, in any currency.')
        st.stop()
    _CURRENCIES = ['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'THB', 'INR', 'BTC', 'ETH', 'USDC', 'SOL', 'Other']

    col_a, col_b = st.columns(2)

    # ── Assets ────────────────────────────────────────────────────────────────
    with col_a:
        st.subheader('Assets')
        assets = st.session_state.get('assets', [])
        if assets:
            for a in assets:
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"**{a['name']}** · {a['type']}")
                c2.write(f"{a['value']:,.2f} {a['currency'].upper()}")
                if c3.button('✕', key=f'del_asset_{a["id"]}'):
                    st.session_state.tracker.delete_asset(a['id'])
                    sync_data()
                    st.rerun()
        else:
            st.caption('No assets recorded yet.')

        with st.form('add_asset_form', clear_on_submit=True):
            st.write('Add Asset')
            a_name  = st.text_input('Name (e.g. Savings Account, Crypto)')
            a_type  = st.selectbox('Type', ['liquid', 'investment', 'real_estate', 'vehicle', 'other'])
            a_val   = st.number_input('Current Value', min_value=0.0, step=0.01)
            a_cur   = st.selectbox('Currency', _CURRENCIES, key='asset_cur')
            a_notes = st.text_input('Notes (optional)')
            if st.form_submit_button('Add Asset') and a_name and a_val > 0:
                res = st.session_state.tracker.add_asset(a_name, a_type, a_val, a_cur, a_notes)
                if res['success']:
                    st.success(res['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(res['message'])

    # ── Liabilities ───────────────────────────────────────────────────────────
    with col_b:
        st.subheader('Liabilities')
        liabilities = st.session_state.get('liabilities', [])
        if liabilities:
            for l in liabilities:
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"**{l['name']}** · {l['type']}")
                c2.write(f"{l['balance']:,.2f} {l['currency'].upper()}")
                if c3.button('✕', key=f'del_liab_{l["id"]}'):
                    st.session_state.tracker.delete_liability(l['id'])
                    sync_data()
                    st.rerun()
        else:
            st.caption('No liabilities recorded yet.')

        with st.form('add_liability_form', clear_on_submit=True):
            st.write('Add Liability')
            l_name  = st.text_input('Name (e.g. Student Loan, Mortgage)')
            l_type  = st.selectbox('Type', ['mortgage', 'student_loan', 'car_loan', 'credit_card', 'personal_loan', 'other'])
            l_bal   = st.number_input('Outstanding Balance', min_value=0.0, step=0.01)
            l_rate  = st.number_input('Interest Rate % (optional)', min_value=0.0, max_value=100.0, step=0.01)
            l_cur   = st.selectbox('Currency', _CURRENCIES, key='liab_cur')
            l_notes = st.text_input('Notes (optional)', key='liab_notes')
            if st.form_submit_button('Add Liability') and l_name and l_bal > 0:
                res = st.session_state.tracker.add_liability(l_name, l_type, l_bal, l_cur, l_rate / 100, l_notes)
                if res['success']:
                    st.success(res['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(res['message'])
