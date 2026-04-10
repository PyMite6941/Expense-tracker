# For the web ui setup
import streamlit as st
# For knowing the month and etc
from datetime import datetime

# Get the class to use
from core.core_stuff import ExpenseTracker

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
    # If subscriptions not in session state then import
    if 'subscriptions' not in st.session_state:
        results = st.session_state.tracker.view_subscriptions()
        st.session_state.subscriptions = results['data'] if results['success'] else []
    # If goals not in session state then import
    if 'goals' not in st.session_state:
        results = st.session_state.tracker.view_all_goals()
        st.session_state.goals = results['data'] if results['success'] else []
    # If recurring expenses not in session state then import
    if 'recurring_expenses' not in st.session_state:
        results = st.session_state.tracker.view_recurring_expenses()
        st.session_state.recurring_expenses = results['data'] if results['success'] else []
    # If recurring income not in session state then import
    if 'recurring_income' not in st.session_state:
        results = st.session_state.tracker.view_recurring_income()
        st.session_state.recurring_income = results['data'] if results['success'] else []
    if 'selected_for_deletion' not in st.session_state:
        st.session_state.selected_for_deletion = []
    if 'current_month' not in st.session_state:
        st.session_state.current_month = datetime.now().strftime("%Y-%m")
    if 'previous_currency' not in st.session_state:
        st.session_state.previous_currency = ''

# Refresh the data in the session state
def sync_data():
    key_to_reset = ['expenses','income','budget','subscriptions','goals','recurring_expenses','recurring_income']
    for key in key_to_reset:
        if key in st.session_state:
            del st.session_state[key]
    init_st()