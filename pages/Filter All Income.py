# For the web ui setup
import streamlit as st
# For data manipulation
import pandas as pd

# Initialize the session states
from streamlit_setup import init_st

init_st()

st.title('Filter All Income')
filter_choice = st.multiselect(
    "Select filters to apply:",
    options=[
        'Category',
        'Amount Range',
        'Date',
        'Notes'
    ]
)
filtered_income = st.container()
with filtered_income:
    st.subheader('Filtered Income')
    if st.session_state.income:
        df = pd.DataFrame(st.session_state.income)
        if 'Category' in filter_choice:
            category = st.text_input("Enter category to filter by:")
            if category:
                df = df[df['category'].str.contains(category, case=False, na=False)]
        if 'Amount Range' in filter_choice:
            min_amount = st.number_input("Minimum amount:", min_value=0.0, step=0.01)
            max_amount = st.number_input("Maximum amount:", min_value=0.0, step=0.01)
            if max_amount >= min_amount:
                df = df[(df['amount'] >= min_amount) & (df['amount'] <= max_amount)]
        if 'Date' in filter_choice:
            date = st.date_input("Select a date to filter by:")
            df = df[df['date'] == str(date)]
        if 'Notes' in filter_choice:
            notes = st.text_input("Enter notes to filter by:")
            if notes:
                df = df[df['notes'].str.contains(notes, case=False, na=False)]
        st.dataframe(df)
    else:
        st.write("No income found.")