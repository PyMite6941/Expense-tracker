# For the web ui setup
import streamlit as st
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..', '..')))

# Initialize the session states
from CLI.app.streamlit_setup import init_st, sync_data, BACKEND_URL, USE_LOCAL_BACKEND
import requests as _requests

init_st()


def _backend_post(endpoint: str, payload: dict):
    return _requests.post(f'{st.session_state.get("backend_url", BACKEND_URL)}{endpoint}', json=payload, timeout=30)

st.title('Web-based Expense and Income Tracking')

tab_dashboard, tab_add, tab_delete, tab_edit, tab_view_expenses, tab_view_income, tab_view_subscriptions = st.tabs([
    'Dashboard', 'Add', 'Delete', 'Edit', 'View Expenses', 'View Income', 'View Subscriptions'
])

# ── Dashboard ────────────────────────────────────────────────────────────────
with tab_dashboard:
    if st.session_state.expenses:
        filtered_expenses = [e for e in st.session_state.expenses if e['date'][:7] == st.session_state.current_month]
        monthly_expenses = sum(e['price'] for e in filtered_expenses)
        st.metric('Monthly Expenses', f"{monthly_expenses:.2f} USD")
    else:
        st.write("No expenses found.")

    if st.session_state.income:
        filtered_income = [i for i in st.session_state.income if i['date'][:7] == st.session_state.current_month]
        monthly_income = sum(i['amount'] for i in filtered_income)
        st.metric('Monthly Income', f"{monthly_income:.2f} USD")
    else:
        st.write("No income found.")

    if st.session_state.budget:
        st.subheader('Budget Status')
        budget_totals = {}
        for expense in st.session_state.expenses:
            if expense['date'][:7] == st.session_state.current_month:
                tag = expense['tags']
                budget_totals[tag] = budget_totals.get(tag, 0) + expense['price']
        for budget in st.session_state.budget:
            total_spent = budget_totals.get(budget['category'], 0)
            limit = float(budget['amount'])
            pct = min(total_spent / limit, 1.0) if limit > 0 else 0.0
            over = total_spent > limit
            col_label, col_bar = st.columns([1, 3])
            with col_label:
                st.write(f"**{budget['category']}**")
                st.caption(f"{total_spent:.2f} / {limit:.2f} {budget.get('currency','USD').upper()}")
            with col_bar:
                st.progress(pct)
                if over:
                    st.error(f"Over by {total_spent - limit:.2f} — reduce {budget['category']} spending", icon='🚨')
                elif pct >= 0.9:
                    st.warning(f"{int(pct*100)}% used — approaching limit", icon='⚠️')

    st.divider()

    # ── Net-worth snapshot ───────────────────────────────────────────────────
    st.subheader('Net-Worth Snapshot')
    try:
        if USE_LOCAL_BACKEND:
            from backend.analytics import net_worth_snapshot
            _nw = net_worth_snapshot(
                {'expenses': st.session_state.expenses, 'income': st.session_state.income,
                 'subscriptions': st.session_state.subscriptions, 'goals': st.session_state.goals},
                convert_fn=st.session_state.tracker.convert_currency,
            )
        else:
            _resp = _backend_post('/net-worth', {
                'expenses': st.session_state.expenses, 'income': st.session_state.income,
                'subscriptions': st.session_state.subscriptions, 'goals': st.session_state.goals,
            })
            _nw = _resp.json() if _resp.ok else {'success': False}
        if _nw.get('success'):
            _nw_cols = st.columns(4)
            _nw_cols[0].metric('Total Income', f"{_nw['total_income']:,.2f} {_nw['base_currency']}")
            _nw_cols[1].metric('Total Expenses', f"{_nw['total_expenses']:,.2f} {_nw['base_currency']}")
            _nw_cols[2].metric('Net Cash Flow', f"{_nw['net_cash_flow']:,.2f} {_nw['base_currency']}")
            _nw_cols[3].metric('Est. Net Worth', f"{_nw['estimated_net_worth']:,.2f} {_nw['base_currency']}")
            _nw_cols2 = st.columns(2)
            _nw_cols2[0].metric('Monthly Subscription Burden', f"{_nw['monthly_subscription_burden']:,.2f} {_nw['base_currency']}")
            _nw_cols2[1].metric('Goal Contributions to Date', f"{_nw['goal_contributions_to_date']:,.2f} {_nw['base_currency']}")
    except Exception as _e:
        st.info(f'Net-worth snapshot unavailable: {_e}')

    st.divider()

    # ── Spending forecast ────────────────────────────────────────────────────
    st.subheader('Spending Forecast')
    try:
        if USE_LOCAL_BACKEND:
            from backend.analytics import forecast_spending
            _fc = forecast_spending(st.session_state.expenses)
        else:
            _resp = _backend_post('/forecast', {'expenses': st.session_state.expenses, 'base_currency': 'USD'})
            _fc = _resp.json() if _resp.ok else {'success': False, 'forecasts': {}}
        if _fc.get('success') and _fc.get('forecasts'):
            st.caption(f"Based on {_fc['based_on_months']} month(s) of history ({_fc['base_currency']} only)")
            _fc_cols = st.columns(3)
            for _fi, (_cat, _info) in enumerate(_fc['forecasts'].items()):
                _arrow = '↑' if _info['trend'] == 'increasing' else '↓' if _info['trend'] == 'decreasing' else '→'
                _fc_cols[_fi % 3].metric(f'{_cat} {_arrow}', f"{_info['next_month_forecast']:,.2f}", delta=f"avg {_info['current_avg']:,.2f}")
        else:
            st.info('Not enough expense history to generate a forecast yet.')
    except Exception as _e:
        st.info(f'Forecast unavailable: {_e}')

    st.divider()

    # ── Anomaly detection ────────────────────────────────────────────────────
    st.subheader('Unusual Expenses')
    try:
        if USE_LOCAL_BACKEND:
            from backend.analytics import detect_anomalies
            _ad = detect_anomalies(st.session_state.expenses)
        else:
            _resp = _backend_post('/detect-anomalies', {'expenses': st.session_state.expenses, 'z_threshold': 2.5})
            _ad = _resp.json() if _resp.ok else {'anomalies': []}
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
        else:
            st.success('No unusual expenses detected.')
    except Exception as _e:
        st.info(f'Anomaly detection unavailable: {_e}')

    st.divider()

    # ── Natural language query ───────────────────────────────────────────────
    st.subheader('Ask About Your Finances')
    _nl_question = st.text_input('Ask anything about your finances …', key='nl_query_input')
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
                    _resp = _backend_post('/query', {'question': _nl_question, 'data': _nl_data})
                    _nl_answer = _resp.json().get('answer', _resp.text) if _resp.ok else f'Error {_resp.status_code}'
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
        except Exception:
            pass

        with st.expander('Recurring Expenses', expanded=False):
            if not st.session_state.recurring_expenses:
                st.write("No recurring expenses found.")
            else:
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
            expense_currency = st.selectbox('Expense Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'Other'], key='add_exp_currency')
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
            income_currency = st.selectbox('Income Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'Other'], key='add_inc_currency')
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
        with st.form('add_budget_form'):
            budget_amount = st.number_input('Budget Amount', min_value=0.0, step=0.01, key='add_bud_amount')
            budget_category = st.selectbox('Budget Category', options=['Food', 'Transport', 'Entertainment', 'Utilities', 'Bills', 'Other'], key='add_bud_category')
            budget_currency = st.selectbox('Budget Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'Other'], key='add_bud_currency')
            if st.form_submit_button('Add Budget'):
                results = st.session_state.tracker.create_budget(budget_category, budget_amount, budget_currency)
                if results['success']:
                    st.success(results['message'])
                    sync_data()
                    st.rerun()
                else:
                    st.error(results['message'])

    elif choice == 'Subscription':
        with st.form('add_subscription_form'):
            subscription_name = st.text_area('Subscription Name', key='add_sub_name')
            subscription_price = st.number_input('Subscription Price', min_value=0.0, step=0.01, key='add_sub_price')
            subscription_currency = st.selectbox('Subscription Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'Other'], key='add_sub_currency')
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
            goal_currency = st.selectbox('Goal Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'Other'], key='add_goal_currency')
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
            expense_currency = st.selectbox('Expense Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'Other'], key='edit_exp_currency')
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
            income_currency = st.selectbox('Change Income Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'Other'], key='edit_inc_currency')
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
            budget_currency = st.selectbox('Change Budget Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'Other'], key='edit_bud_currency')
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
            subscription_currency = st.selectbox('Subscription Currency', options=['USD', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 'THB', 'INR', 'Other'], key='edit_sub_currency')
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
    search = st.text_input('Search expenses ...', '', key='view_exp_search')
    if search:
        expenses = [e for e in st.session_state.expenses if search.lower() in e['tags'].lower() or search.lower() in (e['notes'] or '').lower()]
    else:
        expenses = st.session_state.expenses

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
    search = st.text_input('Search income ...', '', key='view_inc_search')
    if search:
        income_list = [i for i in st.session_state.income if search.lower() in i['source'].lower() or search.lower() in (i['notes'] or '').lower()]
    else:
        income_list = st.session_state.income

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
