import streamlit as st

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

st.button('View Total Expenses')
st.button('View Total Income')