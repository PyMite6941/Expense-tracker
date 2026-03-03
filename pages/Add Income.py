# For the web ui setup
import streamlit as st

# Initialize the session states
from streamlit_setup import init_st,sync_data

init_st()

st.title('Add Income')

# Add income
with st.form('add_income_form'):
    col1, col2 = st.columns(2)
    with col1:
        income = st.text_input('Income Source')
    with col2:
        income_amount = st.number_input('Income Amount',min_value=0.0,step=0.01)
    income_currency = st.selectbox('Income Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
    income_date = st.date_input('Income Date')
    income_notes = st.text_area('Income Notes')
    if st.form_submit_button('Add Income'):
        results = st.session_state.tracker.add_income(income_amount,income,income_currency,str(income_date),income_notes)
        if results['success']:
            st.success(results['message'])
            sync_data()
            st.rerun()
        else:
            st.error(results['message'])