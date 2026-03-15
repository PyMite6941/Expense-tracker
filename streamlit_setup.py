# For the web ui setup
import streamlit as st
# For knowing the month and etc
from datetime import datetime

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
    if 'selected_for_deletion' not in st.session_state:
        st.session_state.selected_for_deletion = []
    if 'current_month' not in st.session_state:
        st.session_state.current_month = datetime.now().month
    if 'previous_currency' not in st.session_state:
        st.session_state.previous_currency = ''

# Refresh the data in the session state
def sync_data():
    key_to_reset = ['expenses','income','budget']
    for key in key_to_reset:
        if key in st.session_state:
            del st.session_state[key]
    init_st()

# Sum all categories in a list by the first tuple element
def sum_of_all_categories(l1:list) -> list:
    categories = []
    for item in l1:
        for i in range(len(categories)):
            if item == categories[i][0]:
                categories[i][1] += item[1]
            elif item not in categories:
                categories.append(item)
    return categories