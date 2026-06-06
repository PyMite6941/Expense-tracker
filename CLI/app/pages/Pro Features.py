import os
import sys

import requests
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from CLI.core.core_stuff import ExpenseTracker
from CLI.app.streamlit_setup import init_st, BACKEND_URL, AUTH_SERVICE_URL

init_st()

_BACKEND  = st.session_state.get('backend_url',  BACKEND_URL)
_AUTH     = st.session_state.get('auth_service_url', AUTH_SERVICE_URL)

st.set_page_config(page_title='Pro Features', page_icon='⭐')
st.title('⭐ Pro Features')


# ── helpers ───────────────────────────────────────────────────────────────────

def _post(endpoint: str, payload: dict, token: str = None, timeout: int = 120):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return requests.post(f'{_BACKEND}{endpoint}', json=payload, headers=headers, timeout=timeout)


def _load_expenses():
    tracker = st.session_state.get('tracker') or ExpenseTracker()
    res = tracker.view_total_expenses()
    return res['data'] if res.get('success') else []


# ── License activation ────────────────────────────────────────────────────────

st.subheader('Activate your license')

token_input = st.text_input(
    'License key',
    value=st.session_state.get('pro_token', ''),
    type='password',
    placeholder='Paste the key from your purchase email…',
)

col_activate, col_clear = st.columns([1, 5])

with col_activate:
    if st.button('Activate', type='primary', disabled=not token_input):
        try:
            resp = requests.post(f'{_AUTH}/validate', json={'token': token_input}, timeout=8)
            if resp.ok:
                data = resp.json()
                st.session_state['pro_token'] = token_input
                st.session_state['pro_email']    = data['email']
                st.session_state['pro_tier']     = data.get('tier', 'pro')
                st.session_state['pro_features'] = data.get('features', [])
                st.success(f"License active — {data['email']} ({data.get('tier','pro').upper()})", icon='✅')
                st.rerun()
            else:
                st.error(f"Invalid or expired key. ({resp.status_code})")
        except requests.exceptions.ConnectionError:
            st.error('Could not reach the license server.')
        except Exception as e:
            st.error(f'Unexpected error: {e}')

with col_clear:
    if st.session_state.get('pro_token') and st.button('Remove license'):
        for k in ('pro_token', 'pro_email', 'pro_tier', 'pro_features'):
            st.session_state.pop(k, None)
        st.rerun()

if st.session_state.get('pro_token'):
    st.success(
        f"Active — **{st.session_state.get('pro_email', '')}** · "
        f"{st.session_state.get('pro_tier', 'pro').upper()} tier",
        icon='🔑',
    )


st.divider()


# ── Free analytics (no JWT needed — runs on deployed backend) ─────────────────

st.header('Analytics')
st.caption('These run on the backend server — no AI API key required.')

expenses = _load_expenses()
if not expenses:
    st.info('No expense data found. Add some expenses first.')
    st.stop()

currency = st.selectbox('Base currency for analysis', ['USD', 'EUR', 'GBP', 'THB', 'JPY'], index=0)

# ── Spending forecast ─────────────────────────────────────────────────────────
with st.expander('📈 Spending Forecast', expanded=True):
    if st.button('Run Forecast'):
        with st.spinner('Calculating…'):
            try:
                resp = _post('/forecast', {'expenses': expenses, 'base_currency': currency})
                if resp.ok:
                    data = resp.json()
                    st.caption(f"Based on {data['based_on_months']} month(s) of history · {data['base_currency']} only")
                    cols = st.columns(3)
                    for i, (cat, info) in enumerate(data['forecasts'].items()):
                        arrow = '↑' if info['trend'] == 'increasing' else '↓' if info['trend'] == 'decreasing' else '→'
                        cols[i % 3].metric(
                            cat,
                            f"{info['next_month_forecast']:.2f}",
                            f"{arrow} avg {info['current_avg']:.2f}",
                        )
                else:
                    st.warning(resp.json().get('detail', 'Forecast failed.'))
            except Exception as e:
                st.error(f'Could not reach backend: {e}')

# ── Anomaly detection ─────────────────────────────────────────────────────────
with st.expander('🚨 Anomaly Detection'):
    z = st.slider('Z-score threshold', 1.5, 4.0, 2.5, 0.1,
                  help='Lower = more sensitive. 2.5 catches expenses >2.5 std-devs above their category mean.')
    if st.button('Scan for Anomalies'):
        with st.spinner('Scanning…'):
            try:
                resp = _post('/detect-anomalies', {'expenses': expenses, 'z_threshold': z})
                if resp.ok:
                    data = resp.json()
                    flagged = data.get('anomalies', [])
                    if not flagged:
                        st.success('No anomalies detected at this threshold.', icon='✅')
                    else:
                        st.warning(f"{data['count']} anomalous expense(s) found.", icon='🚨')
                        for a in flagged:
                            st.markdown(
                                f"**{a.get('purchased','?')}** — "
                                f"{a.get('price',0):.2f} {a.get('currency','')}  "
                                f"*(z={a.get('z_score','?')}, "
                                f"category avg {a.get('category_mean','?'):.2f}, "
                                f"deviation +{a.get('deviation','?'):.2f})*"
                            )
                else:
                    st.error(resp.text)
            except Exception as e:
                st.error(f'Could not reach backend: {e}')

# ── Tax summary ───────────────────────────────────────────────────────────────
with st.expander('🧾 Tax Summary'):
    year = st.number_input('Year', min_value=2020, max_value=2030, value=2025, step=1)
    income = st.session_state.get('income', [])
    if st.button('Generate Tax Summary'):
        with st.spinner('Calculating…'):
            try:
                resp = _post('/tax-summary', {
                    'expenses': expenses,
                    'income': income,
                    'year': int(year),
                })
                if resp.ok:
                    d = resp.json()
                    c1, c2, c3 = st.columns(3)
                    c1.metric('Total Income',   f"{d['total_income']:.2f}")
                    c2.metric('Total Expenses', f"{d['total_expenses']:.2f}")
                    c3.metric('Net',            f"{d['net']:.2f}")
                    st.metric('Est. Deductible Total', f"{d['estimated_deductible_total']:.2f}")
                    st.caption(f"Deductible categories: {', '.join(d['deductible_categories'])}")
                    st.subheader('By Category')
                    for cat, amt in d['by_category'].items():
                        st.text(f"  {cat}: {amt:.2f}")
                else:
                    st.error(resp.text)
            except Exception as e:
                st.error(f'Could not reach backend: {e}')


# ── AI Advanced Categorization (JWT required) ─────────────────────────────────

st.divider()
st.header('AI Advanced Categorization')
st.caption('Requires an active Pro or Max license. Runs CrewAI agents server-side.')

if not st.session_state.get('pro_token'):
    st.info('Activate your license key above to unlock this section.')
    st.stop()

context = st.text_input(
    'Focus (optional)',
    placeholder="e.g. 'focus on last 3 months' — leave blank for full analysis",
)

if st.button('Run Advanced Categorization', type='primary'):
    with st.spinner(f'Running AI analysis on {len(expenses)} expenses… (30–90 seconds)'):
        try:
            resp = _post(
                '/advanced-categorize',
                {
                    'expenses': expenses,
                    'context': context or 'Advanced categorization with subcategories and pattern detection',
                },
                token=st.session_state['pro_token'],
                timeout=180,
            )
        except requests.exceptions.ConnectionError:
            st.error('Could not reach backend.')
            st.stop()
        except Exception as e:
            st.error(f'Request failed: {e}')
            st.stop()

    if resp.status_code == 401:
        st.error('License key rejected — it may have expired. Re-activate above.')
        st.stop()
    if not resp.ok:
        st.error(f'Analysis failed (HTTP {resp.status_code}): {resp.text}')
        st.stop()

    st.session_state['last_categorization'] = resp.json()

result = st.session_state.get('last_categorization')
if result:
    st.subheader('Summary')
    st.write(result.get('summary', '—'))

    findings = result.get('key_findings', [])
    if findings:
        st.subheader('Key Findings')
        for f in findings:
            st.markdown(f'- {f}')

    anomalies = result.get('anomalies', [])
    if anomalies:
        st.subheader('Anomalies')
        for a in anomalies:
            st.warning(a, icon='🚨')
    else:
        st.success('No anomalies detected.', icon='✅')

    recs = result.get('recommendations', [])
    if recs:
        st.subheader('Budget Recommendations')
        for r in recs:
            st.info(r, icon='💡')
