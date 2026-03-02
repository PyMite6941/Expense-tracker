# For the web ui setup
import streamlit as st

# Get the class to use
from core_stuff import ExpenseTracker

# Initialize the session states
def init_st():
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

# Refresh the data in the session state
def sync_data():
    key_to_reset = ['expenses','income','budget']
    for key in key_to_reset:
        if key in st.session_state:
            del st.session_state[key]
    init_st()