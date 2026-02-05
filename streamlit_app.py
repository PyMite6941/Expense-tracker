import streamlit as st

if 'expenses' not in st.session_state:
    st.session_state.expenses = []
st.title('Web-based Expense and Income Tracking')