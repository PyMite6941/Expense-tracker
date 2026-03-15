# For the web ui setup
import streamlit as st
# For data manipulation
import pandas as pd

# Initialize the session states
from streamlit_setup import init_st

init_st()

st.title('View Expenses')
search = st.text_input("Search expenses ...","")
if search:
    expenses = [expense for expense in st.session_state.expenses if search.lower() in expense['tags'].lower() or search.lower() in expense['notes'].lower()]
else:
    expenses = st.session_state.expenses
if expenses:
    for expense in expenses:
        col1,col2,col3,col4 = st.columns([3,2,2,2])
        with col1:
            st.write(f"**{expense['price']:.2f} {expense['currency'].upper()}**")
        with col2:
            st.write(f"**{expense['tags']}**")
        with col3:
            st.write(f"{expense['date']}")
        with col4:
            st.write(f"{expense['notes'] if expense['notes'] else ''}")
        st.divider()
else:
    st.write("No expenses found. Add expenses to get started.")