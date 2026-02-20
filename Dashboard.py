# For the web ui setup
import streamlit as st
# For the web ui graphs / charts
import plotly.express as px

# Get the class to use
from core_stuff import ExpenseTracker

# If class obj not in session state then import
if 'tracker' not in st.session_state:
    st.session_state.tracker = ExpenseTracker()
# If expenses not in session state then import
if 'expenses' not in st.session_state:
    results = st.session_state.tracker.view_total_expenses()
    st.session_state.expenses = results['data'] if results['success'] else []
# If income not in session state then import
if 'income' not in st.session_state:
    results = st.session_state.tracker.view_income()
    st.session_state.income = results['data'] if results['success'] else []
# If budgets not in session state then import
if 'budget' not in st.session_state:
    results = st.session_state.tracker.view_all_budget()
    st.session_state.budget = results['data'] if results['success'] else []

st.title('Web-based Expense and Income Tracking')

st.metric("Total Expenses","100","$1452")
st.metric("Total Income","200","$2314")

pie_fig = px.pie(st.session_state.expenses,title='Total Expenses')
pie_fig.show()

with st.form('form'):
    st.form_submit_button('Save Data')