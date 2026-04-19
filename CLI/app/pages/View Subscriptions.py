# For the web ui setup
import streamlit as st
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..')))

# Initialize the session states
from CLI.app.streamlit_setup import init_st,sync_data

init_st()

st.title('View Subscriptions')
search = st.text_input("Search subscriptions ...","")
# If subscription is empty
if not st.session_state.subscriptions:
    st.write("No subscriptions found. Add subscriptions to get started.")
if search and search != "":
    subscriptions = [subscription for subscription in st.session_state.subscriptions if search.lower() in subscription['name'].lower()]
else:
    subscriptions = st.session_state.subscriptions
# Show subscriptions
if subscriptions:
    for subscription_item in subscriptions:
        col1,col2 = st.columns([3,2])
        with col1:
            st.write(f"**{subscription_item['name']}**")
        with col2:
            st.write(f"**{subscription_item['price']:.2f} {subscription_item['currency'].upper()}**")
else:
    st.write(f"No subscriptions found using search term '{search}'.")
# Import / export subscriptions via .csv
st.file_uploader("Import subscriptions from .csv", type=["csv"], key="file_uploader")
if st.session_state.file_uploader:
    st.session_state.tracker.import_from_csv("subscriptions",st.session_state.file_uploader)
    sync_data()
    st.success("Data imported successfully!")
result = st.session_state.tracker.export_to_csv("subscriptions","subscriptions.csv")
if result['success']:
    st.download_button(label="Export subscriptions to .csv",data=result['data'].to_csv(index=False).encode('utf-8'),file_name="subscriptions.csv",mime="text/csv")