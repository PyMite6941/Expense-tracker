# For the web ui setup
import streamlit as st
# For the web ui graphs / charts
import plotly.express as px

# Initialize the session states
from streamlit_setup import init_st,sync_data

init_st()

st.title('Web-based Expense and Income Tracking')

st.metric("Total Expenses","","$"+str(st.session_state.total_expenses))
st.metric("Total Income","","$"+str(st.session_state.total_income))

pie_fig = px.pie(st.session_state.expenses_df,title='Total Expenses')
st.plotly_chart(pie_fig)

with st.form('form'):
    st.form_submit_button('Save Data')
    sync_data()