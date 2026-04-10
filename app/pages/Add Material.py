# For the web ui setup
import streamlit as st
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..')))

# Initialize the session states
from core.streamlit_setup import init_st,sync_data

init_st()

st.title('Add Material')

# Get input on what is to be added
choice = st.selectbox('What to add?',options=['Expenses','Income','Budget','Subscription','Goal'])
if choice == 'Expenses':
    # Add expenses
    with st.expander('Recurring Expenses',expanded=False):
        if not st.session_state.recurring_expenses:
            st.write("No recurring expenses found.")
        else:
            for expense in st.session_state.recurring_expenses:
                col1,col2,col3,col4 = st.columns([3,2,2,2])
                with col1:
                    st.write(f"**{expense['purchased']}**")
                with col2:
                    st.write(f"{expense['amount']:.2f} {expense['currency']}")
                with col3:
                    st.write(f"{expense['tags']}")
                with col4:
                    if st.button(f"Readd {expense['purchased']}"):
                        results = st.session_state.tracker.add_expenses(expense['amount'],expense['purchased'],expense['tags'],expense['currency'],str(st.session_state.current_month + '-01'),'Readded from recurring expenses')
                        if results['success']:
                            st.success(results['message'])
                            sync_data()
                            st.rerun()
                        else:
                            st.error(results['message'])
                st.divider()
    with st.form('add_expenses_form'):
        col1, col2 = st.columns(2)
        with col1:
            expense_purchased = st.text_input('What was purchased?')
        with col2:
            expense_amount = st.number_input('Expense Amount',min_value=0.0,step=0.01)
        expense_category = st.selectbox('Expense Category',options=['Food','Transport','Entertainment','Utilities','Bills','Other'])
        expense_currency = st.selectbox('Expense Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
        expense_date = st.date_input('Expense Date')
        expense_notes = st.text_area('Expense Notes')
        recurring = st.checkbox('Recurring Expense')
        if st.form_submit_button('Add Expense'):
            if recurring == True:
                results = st.session_state.tracker.add_recurring_expense(expense_amount,expense_purchased,expense_category,expense_currency)
            results = st.session_state.tracker.add_expenses(expense_amount,expense_purchased,expense_category,expense_currency,str(expense_date),expense_notes)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])
elif choice == 'Income':
    # Add income
    with st.expander('Recurring Income',expanded=False):
        if not st.session_state.recurring_income:
            st.write("No recurring income found.")
        else:
            for income in st.session_state.recurring_income:
                col1,col2,col3 = st.columns([3,2,2])
                with col1:
                    st.write(f"**{income['source']}**")
                with col2:
                    st.write(f"{income['amount']:.2f} {income['currency']}")
                with col3:
                    if st.button(f"Readd {income['source']}"):
                        results = st.session_state.tracker.add_income(income['amount'],income['source'],str(st.session_state.current_month + '-01'),income['currency'],'Readded from recurring income')
                        if results['success']:
                            st.success(results['message'])
                            sync_data()
                            st.rerun()
                        else:
                            st.error(results['message'])
                st.divider()
    with st.form('add_income_form'):
        col1, col2 = st.columns(2)
        with col1:
            income = st.text_input('Income Source')
        with col2:
            income_amount = st.number_input('Income Amount',min_value=0.0,step=0.01)
        income_currency = st.selectbox('Income Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
        income_date = st.date_input('Income Date')
        income_notes = st.text_area('Income Notes')
        recurring = st.checkbox('Recurring Income')
        if st.form_submit_button('Add Income'):
            if recurring == True:
                results = st.session_state.tracker.add_recurring_income(income_amount,income,income_currency)
            results = st.session_state.tracker.add_income(income_amount,income,str(income_date),income_currency,income_notes)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])
elif choice == 'Budget':
    # Add budget
    with st.form('add_budget_form'):
        budget_amount = st.number_input('Budget Amount',min_value=0.0,step=0.01)
        budget_category = st.selectbox('Budget Category',options=['Food','Transport','Entertainment','Utilities','Bills','Other'])
        budget_currency = st.selectbox('Budget Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
        if st.form_submit_button('Add Budget'):
            results = st.session_state.tracker.create_budget(budget_category,budget_amount,budget_currency)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])
elif choice == 'Subscription':
    # Add subscription
    with st.form('add_subscription_form'):
        subscription_name = st.text_area('Subscription Name')
        subscription_price = st.number_input('Subscription Price',min_value=0.0,step=0.01)
        subscription_currency = st.selectbox('Subscription Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
        if st.form_submit_button('Add Subscription'):
            results = st.session_state.tracker.add_subscriptions(subscription_name,subscription_price,subscription_currency)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])
elif choice == 'Goal':
    # Add Goal
    with st.form('add_goal_form'):
        goal_name = st.text_area('Goal Name')
        goal_target_amount = st.number_input('Goal Target Amount',min_value=0.0,step=0.01)
        goal_currency = st.selectbox('Goal Currency',options=['USD','EUR','JPY','GBP','AUD','CAD','CHF','CNY','SEK','NZD','THB','INR','Other'])
        if st.form_submit_button('Add Goal'):
            results = st.session_state.tracker.create_goal(goal_name,goal_target_amount,goal_currency)
            if results['success']:
                st.success(results['message'])
                sync_data()
                st.rerun()
            else:
                st.error(results['message'])