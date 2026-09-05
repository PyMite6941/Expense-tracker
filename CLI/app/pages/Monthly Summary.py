# For the web ui setup
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
# For proper importing stuff
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','..')))
# Initialize the session states
from CLI.app.streamlit_setup import init_st, sync_data
from CLI.app.theme import page_setup, render_sidebar

page_setup('Monthly Summary', '📅')
init_st()

render_sidebar()
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
# Pie charts are Plotly, not matplotlib. Streamlit has no native pie, and a
# matplotlib one is a flat PNG — no hover, no tooltip, no way to isolate a
# slice. Plotly gives all three for free and follows the app's light/dark theme.
PIE_COLORS = ['#6ea8fe', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#22d3ee', '#fb923c']


def _pie(values, labels, title, currency_symbol='$'):
    """A donut with hover highlighting, tooltips and click-to-isolate slices."""
    total = float(sum(values))
    fig = go.Figure(go.Pie(
        labels=list(labels),
        values=list(values),
        hole=0.5,
        sort=True,
        direction='clockwise',
        marker=dict(colors=PIE_COLORS[:len(values)],
                    line=dict(color='rgba(0,0,0,0)', width=2)),
        # Hovering lifts the slice out of the ring — the highlight effect.
        pull=[0] * len(values),
        hovertemplate=(f'<b>%{{label}}</b><br>{currency_symbol}%{{value:,.2f}}'
                       '<br>%{percent}<extra></extra>'),
        texttemplate='%{percent}',
        textposition='inside',
        insidetextfont=dict(size=11, color='white'),
    ))
    fig.update_traces(
        # Plotly's own hover highlight: the hovered slice grows a border.
        marker_line_width=[0] * len(values),
        hoverlabel=dict(font_size=12),
    )
    fig.update_layout(
        title=dict(text=title, font=dict(size=13), x=0.5, xanchor='center'),
        showlegend=True,
        legend=dict(orientation='v', x=1.0, xanchor='left', y=0.5,
                    font=dict(size=10)),
        margin=dict(l=0, r=0, t=34, b=0),
        height=260,
        autosize=True,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        # The running total sits in the hole, so the chart says something even
        # before you hover.
        annotations=[dict(text=f'{currency_symbol}{total:,.0f}',
                          x=0.5, y=0.5, font=dict(size=15), showarrow=False)],
    )
    return fig


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

    # Table and chart side by side — the chart no longer needs a full row.
    col_table, col_chart = st.columns([3, 2])
    with col_table:
        st.dataframe(df, hide_index=True, use_container_width=True)
    with col_chart:
        st.plotly_chart(_pie(df['Amount'], df['Category'], 'Expense distribution'),
                        config={'displayModeBar': False})
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

    col_table, col_chart = st.columns([3, 2])
    with col_table:
        st.dataframe(df, hide_index=True, use_container_width=True)
    with col_chart:
        st.plotly_chart(_pie(df['Amount'], df['Source'], 'Income distribution'),
                        config={'displayModeBar': False})
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

    st.dataframe(df, hide_index=True, use_container_width=True)

    # Native charts: these were full-width matplotlib PNGs ~760px tall each,
    # which pushed the export controls off the screen. Native ones are compact,
    # interactive, and follow the light/dark theme.
    chart_df = df.set_index('Month')
    col_bars, col_line = st.columns(2)
    with col_bars:
        st.caption('Expenses vs income')
        st.bar_chart(chart_df[['Expenses', 'Income']], height=260)
    with col_line:
        st.caption('Savings trend')
        st.line_chart(chart_df[['Savings']], height=260)

# Export options
st.subheader('Export Data')
st.caption('Files are built in memory — nothing is written to disk until you save it.')
_month_label = st.session_state.get('current_month', '')
col1, col2 = st.columns(2)
with col1:
    _csv = st.session_state.tracker.export_to_csv('expenses')
    if _csv['success']:
        st.download_button('Download expenses (.csv)', data=_csv['bytes'],
                           file_name=f'expenses_{_month_label}.csv', mime='text/csv',
                           type='primary')
    else:
        st.caption(_csv['message'])
with col2:
    _pdf = st.session_state.tracker.export_to_pdf(
        'expenses', title=f'Expenses — {_month_label}' if _month_label else None)
    if _pdf['success']:
        st.download_button('Download expenses (.pdf)', data=_pdf['bytes'],
                           file_name=f'expenses_{_month_label}.pdf',
                           mime='application/pdf')
    else:
        st.caption(_pdf['message'])
