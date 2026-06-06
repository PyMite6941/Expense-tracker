# For the web ui setup
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','..')))
# Initialize the session states
from CLI.app.streamlit_setup import init_st, sync_data

init_st()

st.title('Monthly Summary')

# Get current month and year
current_month = st.session_state.current_month
month_name = pd.to_datetime(current_month).strftime('%B %Y')

# Filter expenses and income for the current month
expenses = [expense for expense in st.session_state.expenses if expense['date'][:7] == current_month]
income = [inc for inc in st.session_state.income if inc['date'][:7] == current_month]

# Calculate totals
total_expenses = sum(expense['price'] for expense in expenses)
total_income = sum(inc['amount'] for inc in income)
net_savings = total_income - total_expenses

# Display metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric('Total Expenses', f"${total_expenses:.2f}")
with col2:
    st.metric('Total Income', f"${total_income:.2f}")
with col3:
    st.metric('Net Savings', f"${net_savings:.2f}", delta_color="inverse" if net_savings < 0 else "normal")

st.divider()

# Expense breakdown by category
expense_by_category = {}
for expense in expenses:
    category = expense['tags']
    expense_by_category[category] = expense_by_category.get(category, 0) + expense['price']

if expense_by_category:
    st.subheader('Expenses by Category')

    # Create a DataFrame for the table
    df = pd.DataFrame({
        'Category': list(expense_by_category.keys()),
        'Amount': list(expense_by_category.values())
    }).sort_values('Amount', ascending=False)

    # Display table
    st.dataframe(df, hide_index=True)

    # Create pie chart
    fig, ax = plt.subplots()
    ax.pie(df['Amount'], labels=df['Category'], autopct='%1.1f%%')
    ax.set_title('Expense Distribution')
    st.pyplot(fig)
else:
    st.write("No expenses recorded for this month.")

st.divider()

# Income breakdown by source
income_by_source = {}
for inc in income:
    source = inc['source']
    income_by_source[source] = income_by_source.get(source, 0) + inc['amount']

if income_by_source:
    st.subheader('Income by Source')

    # Create a DataFrame for the table
    df = pd.DataFrame({
        'Source': list(income_by_source.keys()),
        'Amount': list(income_by_source.values())
    }).sort_values('Amount', ascending=False)

    # Display table
    st.dataframe(df, hide_index=True)

    # Create pie chart
    fig, ax = plt.subplots()
    ax.pie(df['Amount'], labels=df['Source'], autopct='%1.1f%%')
    ax.set_title('Income Distribution')
    st.pyplot(fig)
else:
    st.write("No income recorded for this month.")

st.divider()

# Monthly comparison (if previous months exist)
all_months = sorted(list(set([expense['date'][:7] for expense in st.session_state.expenses] + [inc['date'][:7] for inc in st.session_state.income])), reverse=True)

if len(all_months) > 1:
    st.subheader('Monthly Comparison')

    # Create a DataFrame for monthly data
    monthly_data = []
    for month in all_months:
        month_expenses = sum(expense['price'] for expense in st.session_state.expenses if expense['date'][:7] == month)
        month_income = sum(inc['amount'] for inc in st.session_state.income if inc['date'][:7] == month)
        monthly_data.append({
            'Month': pd.to_datetime(month).strftime('%B %Y'),
            'Expenses': month_expenses,
            'Income': month_income,
            'Savings': month_income - month_expenses
        })

    df = pd.DataFrame(monthly_data)

    # Display table
    st.dataframe(df, hide_index=True)

    # Create bar chart
    fig, ax = plt.subplots()
    df.plot(x='Month', y=['Expenses', 'Income'], kind='bar', ax=ax)
    ax.set_title('Monthly Expenses vs Income')
    ax.set_ylabel('Amount ($)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)

    # Create savings trend chart
    fig, ax = plt.subplots()
    df.plot(x='Month', y='Savings', kind='line', marker='o', ax=ax)
    ax.set_title('Monthly Savings Trend')
    ax.set_ylabel('Savings ($)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)

# Export options
st.subheader('Export Data')
col1, col2 = st.columns(2)
with col1:
    if st.button('Export Expenses to CSV'):
        result = st.session_state.tracker.export_to_csv('expenses', 'expenses.csv')
        if result['success']:
            st.download_button(
                label="Download Expenses CSV",
                data=result['data'].to_csv(index=False).encode('utf-8'),
                file_name="expenses.csv",
                mime="text/csv"
            )
with col2:
    if st.button('Export Summary to PDF'):
        result = st.session_state.tracker.export_to_pdf('expenses', 'monthly_summary.pdf')
        if result['success']:
            with open('monthly_summary.pdf', 'rb') as f:
                st.download_button(
                    label="Download PDF Summary",
                    data=f,
                    file_name="monthly_summary.pdf",
                    mime="application/pdf"
                )