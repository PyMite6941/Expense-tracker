# For the web ui setup
import streamlit as st

# Initialize the session states
from streamlit_setup import init_st,sync_data

init_st()

st.title('Add Budget')

# Add budget
with st.form('add_budget_form'):
    col1, col2 = st.columns(2)
    with col1:
        budget_name = st.text_input('Budget Name')
    with col2:
        budget_amount = st.number_input('Budget Amount',min_value=0.0,step=0.01)
    budget_category = st.selectbox('Budget Category',options=['Food','Transport','Entertainment','Utilities','Bills','Other'])
    budget_currency = st.selectbox('Budget Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
    budget_date = st.date_input('Budget Date')
    budget_notes = st.text_area('Budget Notes')
    if st.form_submit_button('Add Budget'):
        results = st.session_state.tracker.create_budget(budget_amount,budget_category,budget_currency)
        if results['success']:
            st.success(results['message'])
            sync_data()
            st.rerun()
        else:
            st.error(results['message'])