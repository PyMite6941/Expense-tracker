# For the web ui setup
import streamlit as st
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','..')))
# Initialize the session states
from CLI.app.streamlit_setup import init_st,sync_data

init_st()

st.title('Edit Material')

# Get input on what is to be editted
choice = st.selectbox('What to Edit?',options=['Expenses','Income','Budget','Subscription'])
if choice == 'Expenses':
    # Edit expenses
    with st.form('edit_expenses_form'):
        col1, col2 = st.columns(2)
        with col1:
            expense_id = st.number_input('Expense ID',min_value=1,step=1)
        with col2:
            expense_name = st.text_area('Expense Name')
        expense_amount = st.number_input('Expense Amount',min_value=0.0,step=0.01)
        expense_category = st.selectbox('Expense Category',options=['Food','Transport','Entertainment','Utilities','Bills','Other'])
        expense_currency = st.selectbox('Expense Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
        expense_date = st.date_input('Expense Date')
        expense_notes = st.text_area('Expense Notes')
        if st.form_submit_button('Edit Expense'):
            results = st.session_state.tracker.edit_expenses(expense_id,expense_amount,expense_name,expense_category,str(expense_date),expense_currency,expense_notes)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])
elif choice == 'Income':
    # Edit income
    with st.form('edit_income_form'):
        col1, col2 = st.columns(2)
        with col1:
            income_id = st.number_input('Income ID',min_value=1,step=1)
        with col2:
            income = st.text_area('New Income Name')
        income_amount = st.number_input('Change Income Amount',min_value=0.0,step=0.01)
        income_currency = st.selectbox('Change Income Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
        income_date = st.date_input('Change Income Date')
        income_notes = st.text_area('Update Income Notes')
        if st.form_submit_button('Edit Income'):
            results = st.session_state.tracker.edit_income(income_id,income_amount,income,str(income_date),income_currency,income_notes)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])
elif choice == 'Budget':
    # Edit budget
    with st.form('edit_budget_form'):
        previous_category = st.text_input('Current Budget Category')
        budget_amount = st.number_input('New Budget Amount',min_value=0.0,step=0.01)
        budget_category = st.selectbox('New Budget Category',options=['Food','Transport','Entertainment','Utilities','Bills','Other'])
        budget_currency = st.selectbox('Change Budget Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
        if st.form_submit_button('Edit Budget'):
            results = st.session_state.tracker.update_budget(previous_category,budget_category,budget_amount,budget_currency)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])
elif choice == 'Subscription':
    # Edit subscription
    with st.form('edit_subscription_form'):
        subscription_name = st.text_area('Subscription Name')
        subscription_price = st.number_input('Subscription Price',min_value=0.0,step=0.01)
        subscription_currency = st.selectbox('Subscription Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
        if st.form_submit_button('Edit Subscription'):
            results = st.session_state.tracker.edit_subscription(subscription_name,price=subscription_price,currency=subscription_currency)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])