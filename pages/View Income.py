# For the web ui setup
import streamlit as st

# Initialize the session states
from streamlit_setup import init_st,sync_data

init_st()

st.title('View Income')
search = st.text_input("Search income ...","")
# If income is empty
if not st.session_state.income:
    st.write("No income found. Add income to get started.")
if search:
    income = [income for income in st.session_state.income if search.lower() in income['category'].lower() or search.lower() in income['notes'].lower()]
else:
    income = st.session_state.income
# Show income
if income:
    for income_item in income:
        col1,col2,col3,col4 = st.columns([3,2,2,2])
        with col1:
            st.write(f"**{income_item['amount']:.2f} {income_item['currency'].upper()}**")
        with col2:
            st.write(f"**{income_item['source']}**")
        with col3:
            st.write(f"{income_item['date']}")
        with col4:
            st.write(f"{income_item['notes'] if income_item['notes'] else ''}")
        st.divider()
else:
    st.write(f"No income found using search term '{search}'.")
# Import / export income via .csv
st.file_uploader("Import income from .csv", type=["csv"], key="file_uploader")
if st.session_state.file_uploader:
    sync_data(st.session_state.file_uploader)
    st.success("Data imported successfully!")
result = st.session_state.tracker.export_to_csv("income","income.csv")
if result['success']:
    st.download_button(label="Export income to .csv",data=result['data'].to_csv(index=False).encode('utf-8'),file_name="income.csv",mime="text/csv")