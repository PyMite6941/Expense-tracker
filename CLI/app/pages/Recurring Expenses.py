# For the web ui setup
import streamlit as st
import pandas as pd
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','..')))
# Initialize the session states
from CLI.app.streamlit_setup import init_st, sync_data

init_st()

st.title('Recurring Expenses')

# Detect recurring expenses
recurring_result = st.session_state.tracker.detect_recurring_expenses()

if recurring_result['success'] and recurring_result['data']:
    recurring_expenses = recurring_result['data']

    # Display recurring expenses
    st.subheader('Detected Recurring Expenses')

    for expense in recurring_expenses:
        with st.expander(f"{expense['purchased']} - {expense['price']} {expense['currency'].upper()}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Category:** {expense['category']}")
                st.write(f"**Frequency:** Every {expense['frequency_days']} days")
                st.write(f"**Occurrences:** {expense['occurrences']}")
            with col2:
                st.write(f"**Last Occurrence:** {expense['last_date']}")
                st.write(f"**Next Expected:** {expense['next_expected_date']}")

            # Option to add to recurring expenses
            if st.button(f"Add to Recurring Expenses", key=f"add_{expense['purchased']}_{expense['price']}"):
                result = st.session_state.tracker.add_recurring_expense(
                    amount=expense['price'],
                    purchased=expense['purchased'],
                    tags=expense['category'],
                    currency=expense['currency']
                )
                if result['success']:
                    st.success(f"Added {expense['purchased']} to recurring expenses")
                    sync_data()
                else:
                    st.error(f"Failed to add recurring expense: {result['message']}")
        st.divider()

    # View manually added recurring expenses
    st.subheader('Manually Added Recurring Expenses')
    if st.session_state.recurring_expenses:
        for expense in st.session_state.recurring_expenses:
            with st.expander(f"{expense['purchased']} - {expense['amount']} {expense['currency'].upper()}"):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.write(f"**Category:** {expense['tags']}")
                with col2:
                    if st.button("Edit", key=f"edit_{expense['purchased']}"):
                        st.session_state.editing_recurring = expense
                        st.rerun()
                with col3:
                    if st.button("Delete", key=f"delete_{expense['purchased']}"):
                        # Note: This is a simplified approach - in a real app, you'd need a proper ID system
                        st.session_state.recurring_expenses.remove(expense)
                        data = st.session_state.tracker.open_file()['data']
                        data['recurring_expenses'] = st.session_state.recurring_expenses
                        st.session_state.tracker.write_file(data)
                        st.success(f"Deleted {expense['purchased']}")
                        sync_data()
                        st.rerun()
            st.divider()
    else:
        st.write("No manually added recurring expenses.")

    # Add new recurring expense manually
    st.subheader('Add Recurring Expense Manually')
    with st.form("add_recurring_expense"):
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("Amount", min_value=0.01, step=0.01, key="amount")
            purchased = st.text_input("Description", key="purchased")
        with col2:
            currency = st.selectbox("Currency", ["usd", "eur", "gbp", "jpy"], key="currency")
            tags = st.text_input("Category", key="tags")

        if st.form_submit_button("Add Recurring Expense"):
            if purchased and tags:
                result = st.session_state.tracker.add_recurring_expense(
                    amount=amount,
                    purchased=purchased,
                    tags=tags,
                    currency=currency
                )
                if result['success']:
                    st.success("Recurring expense added successfully!")
                    sync_data()
                else:
                    st.error(f"Failed to add recurring expense: {result['message']}")
            else:
                st.error("Please fill in all fields")

else:
    st.write("No recurring expenses detected.")

    # Option to add recurring expenses manually
    st.subheader('Add Recurring Expense Manually')
    with st.form("add_recurring_expense"):
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("Amount", min_value=0.01, step=0.01, key="amount")
            purchased = st.text_input("Description", key="purchased")
        with col2:
            currency = st.selectbox("Currency", ["usd", "eur", "gbp", "jpy"], key="currency")
            tags = st.text_input("Category", key="tags")

        if st.form_submit_button("Add Recurring Expense"):
            if purchased and tags:
                result = st.session_state.tracker.add_recurring_expense(
                    amount=amount,
                    purchased=purchased,
                    tags=tags,
                    currency=currency
                )
                if result['success']:
                    st.success("Recurring expense added successfully!")
                    sync_data()
                else:
                    st.error(f"Failed to add recurring expense: {result['message']}")
            else:
                st.error("Please fill in all fields")