# For the web ui setup
import streamlit as st
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

# Initialize the session states
from core.streamlit_setup import init_st

# Initialize the streamlit variables
init_st()

# Show a good title
st.title('Web-based Expense and Income Tracking')

# Create benchmarks to show off
if st.session_state.expenses:
    filtered_expenses = [expense for expense in st.session_state.expenses if expense['date'][:7] == st.session_state.current_month]
    monthly_expenses = sum(expense['price'] for expense in filtered_expenses)
    st.metric('Monthly Expenses',f"{monthly_expenses:.2f} USD")
else:
    st.write("No expenses found.")
if st.session_state.income:
    filtered_income = [income for income in st.session_state.income if income['date'][:7] == st.session_state.current_month]
    monthly_income = sum(income['amount'] for income in filtered_income)
    st.metric('Monthly Income',f"{monthly_income:.2f} USD")
else:
    st.write("No income found.")

# Display budget alerts if any
budget_totals = {}
for expense in st.session_state.expenses:
    tag = expense['tags']
    budget_totals[tag] = budget_totals.get(tag,0) + expense['price']
for budget in st.session_state.budget:
    total_spent = budget_totals.get(budget['category'],0)
    limit = float(budget['amount'])
    if limit < total_spent:
        st.warning(f"Budget {budget['category']} has been surpassed by {total_spent-limit}")
    elif limit == total_spent:
        st.write(f"Budget {budget['category']} may be surpassed")

st.divider()