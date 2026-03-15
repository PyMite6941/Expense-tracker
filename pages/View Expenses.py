# For the web ui setup
import streamlit as st
# For data manipulation
import pandas as pd

# Initialize the session states
from streamlit_setup import init_st

init_st()

st.title('Filter All Expenses')
filter_choice = st.multiselect(
    "Select filters to apply:",
    options=[
        'Category',
        'Price Range',
        'Date',
        'Notes'
    ]
)
if 'Category' in filter_choice:
    category = st.text_input("Enter category to filter by:")
if 'Price Range' in filter_choice:
    min_price = st.number_input("Minimum price:", min_value=0.0, step=0.01)
    max_price = st.number_input("Maximum price:", min_value=0.0, step=0.01)
if 'Date' in filter_choice:
    date = st.date_input("Select a date to filter by:")
if 'Notes' in filter_choice:
    notes = st.text_input("Enter notes to filter by:")
filtered_expenses = st.container()
convert_currency = st.selectbox('Select currency to convert to (optional):',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
if convert_currency.strip():
    if st.session_state.previous_currency != convert_currency.strip():
        result = st.session_state.tracker.convert_prices_to_currency(convert_currency.strip())
        if result['success']:
            st.success(result['message'])
            st.session_state.previous_currency = convert_currency.strip()
            st.rerun()
        if not result['success']:
            st.error(result['message'])
with filtered_expenses:
    st.subheader('Filtered Expenses')
    if st.session_state.expenses:
        if 'Category' in filter_choice:
            if category:
                df = [e for e in st.session_state.expenses if e['tags'].lower() == category.lower()]
        if 'Price Range' in filter_choice:
            if max_price >= min_price:
                df = [e for e in df if min_price <= e['price'] <= max_price]
            else:
                st.error("Maximum price must be greater than or equal to minimum price.")
        if 'Date' in filter_choice:
            df = [e for e in df if e['date'] == str(date)]
        if 'Notes' in filter_choice:
            if notes:
                df = [e for e in df if notes.lower() in e['notes'].lower()]
        pd.DataFrame(df)
    else:
        st.write("No expenses found.")