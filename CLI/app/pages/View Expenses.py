# For the web ui setup
import streamlit as st
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..')))

# Initialize the session states
from CLI.app.streamlit_setup import init_st,sync_data

init_st()

st.title('View Expenses')
search = st.text_input("Search expenses ...","")
# If expenses are empty
if not st.session_state.expenses:
    st.write("No expenses found. Add expenses to get started.")
if search and search != "":
    expenses = [expense for expense in st.session_state.expenses if search.lower() in expense['tags'].lower() or search.lower() in (expense['notes'] or '').lower()]
else:
    expenses = st.session_state.expenses
# Show expenses
if expenses:
    for expense in expenses:
        col1,col2,col3,col4 = st.columns([3,2,2,2])
        with col1:
            st.write(f"**{expense['price']:.2f} {expense['currency'].upper()}**")
        with col2:
            st.write(f"**{expense['tags']}**")
        with col3:
            st.write(f"{expense['date']}")
        with col4:
            st.write(f"{expense['notes'] if expense['notes'] else ''}")
        st.divider()
else:
    st.write(f"No expenses found using search term '{search}'.")
# Import / export expenses via .csv
st.file_uploader("Import expenses from .csv", type=["csv"], key="file_uploader")
if st.session_state.file_uploader:
    st.session_state.tracker.import_from_csv("expenses",st.session_state.file_uploader)
    sync_data()
    st.success("Data imported successfully!")
result = st.session_state.tracker.export_to_csv("expenses","expenses.csv")
if result['success']:
    st.download_button(label="Export expenses to .csv",data=result['data'].to_csv(index=False).encode('utf-8'),file_name="expenses.csv",mime="text/csv")