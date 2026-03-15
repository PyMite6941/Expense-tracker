# For the web ui setup
import streamlit as st
# For data manipulation
import pandas as pd

# Initialize the session states
from streamlit_setup import init_st

init_st()

st.title('View Income')
search = st.text_input("Search income ...","")
if search:
    income = [income for income in st.session_state.income if search.lower() in income['category'].lower() or search.lower() in income['notes'].lower()]
else:
    income = st.session_state.income
if income:
    for income_item in income:
        col1,col2,col3,col4 = st.columns([3,2,2,2])
        with col1:
            st.write(f"**{income_item['amount']:.2f} {income_item['currency'].upper()}**")
        with col2:
            st.write(f"**{income_item['source']}**")
        with col3:
            st.write(f"{income_item['date']}")
        with col4:
            st.write(f"{income_item['notes'] if income_item['notes'] else ''}")
        st.divider()
else:
    st.write("No income found. Add income to get started.")