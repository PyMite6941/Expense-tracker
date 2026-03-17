# For the web ui setup
import streamlit as st
# For the web ui graphs / charts
import plotly.express as px
# For data manipulation
import pandas as pd

# Initialize the session states
from streamlit_setup import init_st

init_st()

st.title('View All Data in Graphs')

# Show expenses
st.subheader('Expenses')
if st.session_state.expenses:
    st.session_state.expenses_df = pd.DataFrame(st.session_state.expenses)
    st.line_chart(st.session_state.expenses_df,x='date',y='price')
st.write('')
# Show income
st.subheader('Income')
if st.session_state.income:
    st.session_state.income_df = pd.DataFrame(st.session_state.income)
    st.line_chart(st.session_state.income_df,x='date',y='amount')
st.write('')
# Show budget
st.subheader('Budget')
if st.session_state.budget:
    st.session_state.budget_df = pd.DataFrame(st.session_state.budget)
    fig = px.pie(st.session_state.budget_df,names='category',values='amount',title='Budget Distribution')
    st.plotly_chart(fig)