# For the web ui setup
import streamlit as st
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..', '..')))

# Initialize the session states
from CLI.app.streamlit_setup import init_st, sync_data

init_st()

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

    budget_totals = {}
    for expense in st.session_state.expenses:
        if expense['date'][:7] == st.session_state.current_month:
            tag = expense['tags']
            budget_totals[tag] = budget_totals.get(tag, 0) + expense['price']
    for budget in st.session_state.budget:
        total_spent = budget_totals.get(budget['category'], 0)
        limit = float(budget['amount'])
        if limit < total_spent:
            st.warning(f"{budget['category']} budget has been surpassed by {total_spent - limit:.2f}.")
        elif limit == total_spent:
            st.warning(f"{budget['category']} budget has reached its limit.")

    st.divider()

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
            expense_category = st.selectbox('Expense Category', options=['Food', 'Transport', 'Entertainment', 'Utilities', 'Bills', 'Other'], key='add_exp_category')
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
                    for k in ('ocr_merchant', 'ocr_total', 'ocr_date'):
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

    st.file_uploader('Import expenses from .csv', type=['csv'], key='expenses_file_uploader')
    if st.session_state.get('expenses_file_uploader'):
        st.session_state.tracker.import_from_csv('expenses', st.session_state.expenses_file_uploader)
        sync_data()
        st.success('Data imported successfully!')
        st.rerun()
    result = st.session_state.tracker.export_to_csv('expenses', 'expenses.csv')
    if result['success']:
        st.download_button(label='Export expenses to .csv', data=result['data'].to_csv(index=False).encode('utf-8'), file_name='expenses.csv', mime='text/csv', key='exp_download')

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

    st.file_uploader('Import income from .csv', type=['csv'], key='income_file_uploader')
    if st.session_state.get('income_file_uploader'):
        st.session_state.tracker.import_from_csv('income', st.session_state.income_file_uploader)
        sync_data()
        st.success('Data imported successfully!')
        st.rerun()
    result = st.session_state.tracker.export_to_csv('income', 'income.csv')
    if result['success']:
        st.download_button(label='Export income to .csv', data=result['data'].to_csv(index=False).encode('utf-8'), file_name='income.csv', mime='text/csv', key='inc_download')

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

    st.file_uploader('Import subscriptions from .csv', type=['csv'], key='subscriptions_file_uploader')
    if st.session_state.get('subscriptions_file_uploader'):
        st.session_state.tracker.import_from_csv('subscriptions', st.session_state.subscriptions_file_uploader)
        sync_data()
        st.success('Data imported successfully!')
        st.rerun()
    result = st.session_state.tracker.export_to_csv('subscriptions', 'subscriptions.csv')
    if result['success']:
        st.download_button(label='Export subscriptions to .csv', data=result['data'].to_csv(index=False).encode('utf-8'), file_name='subscriptions.csv', mime='text/csv', key='sub_download')
