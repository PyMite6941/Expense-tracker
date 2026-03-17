# For the web ui setup
import streamlit as st
# For the web ui graphs / charts
import plotly.express as px

# Initialize the session states
from streamlit_setup import init_st,sum_of_all_categories

# Initialize the streamlit variables
init_st()

# Show a good title
st.title('Web-based Expense and Income Tracking')

# Create benchmarks to show off
if st.session_state.expenses:
    filtered_expenses = [expense for expense in st.session_state.expenses if expense['date'][:7] == st.session_state.current_month]
    monthly_earnings = sum(expense['price'] for expense in filtered_expenses)
    st.metric('Monthly Earnings',f"{monthly_earnings:.2f} USD")
else:
    st.write("No expenses found.")
if st.session_state.income:
    filtered_income = [income for income in st.session_state.income if income['date'][:7] == st.session_state.current_month]
    monthly_income = sum(income['amount'] for income in filtered_income)
    st.metric('Monthly Income',f"{monthly_income:.2f} USD")
else:
    st.write("No income found.")

# Display budget alerts if any
budget_categories = []
for item in st.session_state.expenses:
    if item in st.session_state.budget:
        budget_categories.append(item['category'],item['price'])
budget_categories = sum_of_all_categories(budget_categories)
for item in st.session_state.budget:
    for i in range(len(budget_categories)):
        if item['category'] == budget_categories[i][0]:
            if item['amount'] < budget_categories[i][1]:
                st.write(f'Budget {item['category']} has been surpassed by {budget_categories[i][0]-item['amount']}')
            elif item['amount'] == budget_categories[i][0]:
                st.write(f'Budget {item['category']} may be surpassed')

st.divider()