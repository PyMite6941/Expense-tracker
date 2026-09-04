# For the web ui setup
import streamlit as st
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','..')))
# Initialize the session states
from CLI.app.streamlit_setup import init_st, sync_data
from CLI.app.theme import page_setup, section, render_sidebar

page_setup('Recurring Expenses', '🔁')
init_st()
render_sidebar()

st.title('🔁 Recurring')
st.caption('Bills that repeat. Detected ones are found in your history; manual '
           'ones you add yourself. Both can be applied to a month in one go.')

tracker = st.session_state.tracker

tab_manual, tab_detected, tab_income = st.tabs(
    ['Your recurring expenses', 'Detected in history', 'Recurring income']
)

# ── Manual recurring expenses ────────────────────────────────────────────────
# These render unconditionally. They used to be nested inside the "detection
# succeeded" branch, so anything you added by hand became invisible whenever
# history had no repeating pattern to find.
with tab_manual:
    recurring = st.session_state.recurring_expenses or []

    if recurring:
        section('Saved recurring expenses',
                f'{len(recurring)} item(s) — applied together from the Manage tab.')
        total = sum(float(r.get('amount', 0) or 0) for r in recurring)
        st.metric('Monthly total', f'{total:,.2f}')

        for idx, item in enumerate(recurring):
            with st.container(border=True):
                col_desc, col_amt, col_del = st.columns([3, 2, 1])
                with col_desc:
                    st.write(f"**{item.get('purchased', '—')}**")
                    st.caption(f"Category: {item.get('tags', 'other')}")
                with col_amt:
                    st.write(f"{float(item.get('amount', 0) or 0):,.2f} "
                             f"{str(item.get('currency', '')).upper()}")
                with col_del:
                    # Keyed on the INDEX, not the description. Keying on
                    # `purchased` crashed the whole page with a duplicate-key
                    # error the moment two recurring items shared a name.
                    if st.button('Delete', key=f'del_recurring_{idx}'):
                        st.session_state['_pending_del'] = idx
                if st.session_state.get('_pending_del') == idx:
                    st.warning(f"Delete **{item.get('purchased', '')}**?", icon='⚠️')
                    c_yes, c_no = st.columns([1, 4])
                    if c_yes.button('Yes, delete', key=f'confirm_del_{idx}',
                                    type='primary'):
                        data = tracker.open_file()['data']
                        rows = data.get('recurring_expenses') or []
                        if 0 <= idx < len(rows):
                            rows.pop(idx)
                        data['recurring_expenses'] = rows
                        tracker.write_file(data)
                        st.session_state.pop('_pending_del', None)
                        sync_data()
                        st.rerun()
                    if c_no.button('Cancel', key=f'cancel_del_{idx}'):
                        st.session_state.pop('_pending_del', None)
                        st.rerun()
    else:
        st.info('Nothing here yet. Add one below, or pull one in from the '
                '**Detected in history** tab.', icon='🔁')

    st.divider()

    # One form, defined once. It used to be duplicated in both branches of an
    # if/else with identical widget keys.
    section('Add a recurring expense')
    with st.form('add_recurring_expense', clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input('Amount', min_value=0.01, step=0.01)
            purchased = st.text_input('Description', placeholder='Electric bill')
        with col2:
            currency = st.selectbox('Currency', ['usd', 'eur', 'gbp', 'jpy', 'thb'])
            tags = st.text_input('Category', placeholder='Bills')
        if st.form_submit_button('Add recurring expense', type='primary'):
            if purchased.strip() and tags.strip():
                result = tracker.add_recurring_expense(
                    amount=amount, purchased=purchased.strip(),
                    tags=tags.strip(), currency=currency,
                )
                if result['success']:
                    st.success(f'Added {purchased.strip()}.')
                    sync_data()
                    st.rerun()
                else:
                    st.error(result['message'])
            else:
                st.error('Description and category are both required.')

# ── Detected from history ────────────────────────────────────────────────────
with tab_detected:
    section('Detected recurring expenses',
            'Found by looking for the same purchase repeating at a regular interval.')
    detected = tracker.detect_recurring_expenses()

    if detected.get('success') and detected.get('data'):
        saved = {(str(r.get('purchased', '')).lower(), float(r.get('amount', 0) or 0))
                 for r in (st.session_state.recurring_expenses or [])}
        for idx, item in enumerate(detected['data']):
            already = (str(item['purchased']).lower(), float(item['price'])) in saved
            with st.container(border=True):
                head, action = st.columns([4, 1])
                with head:
                    st.write(f"**{item['purchased']}** — {item['price']:,.2f} "
                             f"{str(item['currency']).upper()}")
                    st.caption(
                        f"{item['category']} · every ~{item['frequency_days']} days · "
                        f"seen {item['occurrences']}× · last {item['last_date']} · "
                        f"next ~{item['next_expected_date']}"
                    )
                with action:
                    if already:
                        st.caption('✓ saved')
                    elif st.button('Save', key=f'save_detected_{idx}'):
                        result = tracker.add_recurring_expense(
                            amount=item['price'], purchased=item['purchased'],
                            tags=item['category'], currency=item['currency'],
                        )
                        if result['success']:
                            st.success(f"Saved {item['purchased']}.")
                            sync_data()
                            st.rerun()
                        else:
                            st.error(result['message'])
    else:
        st.info(detected.get('message') or
                'No repeating pattern found yet. Detection needs the same purchase '
                'at least 3 times at a regular interval.', icon='🔍')

# ── Recurring income ─────────────────────────────────────────────────────────
with tab_income:
    section('Recurring income', 'Salary and anything else that lands regularly.')
    rec_income = st.session_state.recurring_income or []
    if rec_income:
        total_in = sum(float(r.get('amount', 0) or 0) for r in rec_income)
        st.metric('Monthly total', f'{total_in:,.2f}')
        for item in rec_income:
            with st.container(border=True):
                st.write(f"**{item.get('source', '—')}** — "
                         f"{float(item.get('amount', 0) or 0):,.2f} "
                         f"{str(item.get('currency', '')).upper()}")
    else:
        st.info('No recurring income saved yet.', icon='💰')

    st.divider()
    section('Add recurring income')
    with st.form('add_recurring_income', clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            inc_amount = st.number_input('Amount', min_value=0.01, step=0.01,
                                         key='rec_inc_amount')
            source = st.text_input('Source', placeholder='Salary')
        with col2:
            inc_currency = st.selectbox('Currency', ['usd', 'eur', 'gbp', 'jpy', 'thb'],
                                        key='rec_inc_currency')
        if st.form_submit_button('Add recurring income', type='primary'):
            if source.strip():
                result = tracker.add_recurring_income(
                    amount=inc_amount, source=source.strip(), currency=inc_currency)
                if result['success']:
                    st.success(f'Added {source.strip()}.')
                    sync_data()
                    st.rerun()
                else:
                    st.error(result['message'])
            else:
                st.error('Source is required.')
