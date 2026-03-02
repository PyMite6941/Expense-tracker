# For the web ui setup
import streamlit as st

# Initialize the session states
from streamlit_setup import init_st,sync_data

init_st()

st.title('Add Expenses')

# Add expenses
with st.form('add_expenses_form'):
    col1, col2 = st.columns(2)
    with col1:
        expense_name = st.text_input('Expense Name')
    with col2:
        expense_amount = st.number_input('Expense Amount',min_value=0.0,step=0.01)
    expense_category = st.selectbox('Expense Category',options=['Food','Transport','Entertainment','Utilities','Bills','Other'])
    expense_currency = st.selectbox('Expense Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
    expense_date = st.date_input('Expense Date')
    expense_notes = st.text_area('Expense Notes')
    if st.form_submit_button('Add Expense'):
        results = st.session_state.tracker.add_expenses(expense_amount,expense_name,expense_category,expense_currency,str(expense_date),expense_notes)
        if results['success']:
            st.success(results['message'])
            sync_data()
        else:
            st.error(results['message'])