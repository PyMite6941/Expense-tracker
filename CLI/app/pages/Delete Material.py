# For the web ui setup
import streamlit as st
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..')))

# Initialize the session states
from CLI.app.streamlit_setup import init_st,sync_data

init_st()

st.title('Delete Material')

# Get input on what is to be deleted
choice = st.selectbox('What to Delete?',options=['Expenses','Income','Budget','Subscription'])
if choice == 'Expenses':
    # Delete expenses
    with st.form('delete_expenses_form'):
        expense_id = st.number_input('Expense ID',min_value=1,step=1)
        if st.form_submit_button('Delete Expense'):
            results = st.session_state.tracker.delete_expenses(expense_id)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])
elif choice == 'Income':
    # Delete income
    with st.form('delete_income_form'):
        income_id = st.number_input('Income ID',min_value=1,step=1)
        if st.form_submit_button('Delete Income'):
            results = st.session_state.tracker.delete_income(income_id)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])
elif choice == 'Budget':
    # Delete budget
    with st.form('delete_budget_form'):
        budget_category = st.text_input('Current Budget Category')
        if st.form_submit_button('Delete Budget'):
            results = st.session_state.tracker.delete_budget(budget_category)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])
elif choice == 'Subscription':
    # Delete subscription
    with st.form('delete_subscription_form'):
        subscription_name = st.text_area('Subscription Name')
        if st.form_submit_button('Delete Subscription'):
            results = st.session_state.tracker.delete_subscription(subscription_name)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])