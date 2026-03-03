# For the web ui setup
import streamlit as st
# For the web ui graphs / charts
import plotly.express as px

# Initialize the session states
from streamlit_setup import init_st,sync_data

init_st()

st.title('Web-based Expense and Income Tracking')

if st.session_state.expenses:
    st.metric('Monthly Earnings',f"{st.session_state.monthly_earnings:.2f} USD")
else:
    st.write("No expenses found.")
if st.session_state.income:
    st.metric('Monthly Income',f"{st.session_state.monthly_income:.2f} USD")
else:
    st.write("No income found.")