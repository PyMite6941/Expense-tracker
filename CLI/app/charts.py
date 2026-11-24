"""Budget and cash-flow visuals shared by the local app (Dashboard.py) and the
single-file published app (published/app.py).

The numbers come from CLI/core/reports.py — the same functions the Monthly page
and the tests use — so a figure on a tile, a bar, and the Monthly table can't
disagree. This module only draws.

Charts are Altair (bundled with Streamlit): vector, interactive tooltips, and
they follow the viewer's light/dark theme. Bars carry colour AND a text/tooltip
value, so status never depends on colour alone.
"""
from __future__ import annotations

from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from CLI.core.reports import budget_vs_actual, cash_flow_window
from CLI.app.theme import BAD, GOOD, WARN

_STATUS_COLOR = {"ok": GOOD, "warning": WARN, "over": BAD}
_STATUS_LABEL = {"ok": "On track", "warning": "Near limit", "over": "Over budget"}
_STATUS_BADGE = {"ok": "green", "warning": "orange", "over": "red"}

BUDGET_VIEWS = ["Squares", "Graph"]
DAY_PRESETS = [7, 14, 30, 90, 180, 365]


def _view_picker(key: str) -> str:
    choice = st.segmented_control(
        "Budget view", BUDGET_VIEWS, default=BUDGET_VIEWS[0], key=key,
        label_visibility="collapsed",
    )
    # segmented_control returns None if the user clicks the active option off.
    return choice or BUDGET_VIEWS[0]


def _budget_squares(rows: list[dict]) -> None:
    per_row = 3
    for i in range(0, len(rows), per_row):
        cols = st.columns(per_row)
        for col, r in zip(cols, rows[i:i + per_row]):
            cur = (r["currency"] or "usd").upper()
            with col.container(border=True):
                st.markdown(f"**{r['category']}**")
                st.badge(_STATUS_LABEL[r["status"]], color=_STATUS_BADGE[r["status"]])
                st.metric("Spent", f"{r['spent']:,.2f} {cur}",
                          help=f"Limit {r['limit']:,.2f} {cur}")
                st.progress(min(r["pct_used"] / 100, 1.0),
                            text=f"{r['pct_used']:.0f}% of {r['limit']:,.2f}")
                if r["remaining"] >= 0:
                    st.caption(f"{r['remaining']:,.2f} {cur} left")
                else:
                    st.caption(f":red[Over by {-r['remaining']:,.2f} {cur}]")


def _budget_graph(rows: list[dict]) -> None:
    df = pd.DataFrame([{
        "Category": r["category"],
        "Limit": r["limit"],
        "Spent": r["spent"],
        "Used": f"{r['pct_used']:.0f}%",
        "Status": _STATUS_LABEL[r["status"]],
    } for r in rows])
    order = list(df["Category"])
    y = alt.Y("Category:N", sort=order, title=None)
    tooltip = ["Category", alt.Tooltip("Spent:Q", format=",.2f"),
               alt.Tooltip("Limit:Q", format=",.2f"), "Used", "Status"]

    # The limit is a pale full-length track; spend is drawn over it, so how
    # full each budget is reads at a glance and overspend visibly overshoots.
    track = alt.Chart(df).mark_bar(color="#94a3b8", opacity=0.25,
                                   cornerRadiusEnd=4).encode(
        x=alt.X("Limit:Q", title="Amount"), y=y, tooltip=tooltip)
    spent = alt.Chart(df).mark_bar(cornerRadiusEnd=4, size=18).encode(
        x="Spent:Q", y=y, tooltip=tooltip,
        color=alt.Color("Status:N", title=None,
                        scale=alt.Scale(domain=list(_STATUS_LABEL.values()),
                                        range=[GOOD, WARN, BAD]),
                        legend=alt.Legend(orient="bottom")))
    labels = alt.Chart(df).mark_text(align="left", dx=6).encode(
        x="Spent:Q", y=y, text="Used")
    st.altair_chart((track + spent + labels).properties(height=max(120, 44 * len(rows))),
                    width="stretch")


def render_budget(budgets: list[dict], expenses: list[dict], month: str,
                  key: str = "budget_view") -> None:
    """Budget status for ``month`` as tiles ("Squares") or a bar chart ("Graph")."""
    if not budgets:
        st.caption("No budgets yet — add one under **Manage → Add → Budget** "
                   "to see spend against each category limit here.")
        return
    rows = budget_vs_actual(budgets, expenses, month)
    view = _view_picker(key)
    over = [r["category"] for r in rows if r["status"] == "over"]
    if view == "Graph":
        _budget_graph(rows)
    else:
        _budget_squares(rows)
    if over:
        st.error("Over budget: " + ", ".join(over), icon="🚨")


def render_cash_flow(expenses: list[dict], income: list[dict],
                     key: str = "cashflow", today: date | None = None) -> None:
    """Money in vs money out over the last N days, as a grouped bar chart."""
    today = today or date.today()
    c_days, c_custom, c_end = st.columns([3, 1, 1])
    with c_days:
        preset = st.segmented_control(
            "Time frame (days)", DAY_PRESETS + ["Custom"], default=30,
            key=f"{key}_preset", format_func=lambda v: v if v == "Custom" else f"{v}d",
        ) or 30
    with c_custom:
        days = st.number_input("Days", min_value=1, max_value=3650, value=45, step=1,
                               key=f"{key}_custom", disabled=preset != "Custom")
    with c_end:
        end = st.date_input("Ending", value=today, key=f"{key}_end") or today
    if preset != "Custom":
        days = int(preset)

    cf = cash_flow_window(expenses, income, int(days), end=end)

    k = st.columns(4)
    k[0].metric("Money in", f"{cf['total_in']:,.2f}")
    k[1].metric("Money out", f"{cf['total_out']:,.2f}")
    k[2].metric("Net", f"{cf['net']:,.2f}", delta=f"{cf['net']:+,.2f}")
    k[3].metric("Transactions", cf["transactions"])

    if not cf["transactions"]:
        st.info(f"No income or expenses between {cf['start']} and {cf['end']}. "
                "Try a longer time frame or an earlier end date.")
        return

    long = pd.DataFrame(
        [{"Period": r["label"], "Start": r["period"], "Flow": "Money in",
          "Amount": r["money_in"], "Net": r["net"]} for r in cf["rows"]]
        + [{"Period": r["label"], "Start": r["period"], "Flow": "Money out",
            "Amount": r["money_out"], "Net": r["net"]} for r in cf["rows"]]
    )
    order = [r["label"] for r in cf["rows"]]
    chart = alt.Chart(long).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("Period:N", sort=order, title=None,
                axis=alt.Axis(labelAngle=-45 if len(order) > 10 else 0,
                              labelOverlap="greedy")),
        xOffset=alt.XOffset("Flow:N", sort=["Money in", "Money out"]),
        y=alt.Y("Amount:Q", title="Amount"),
        color=alt.Color("Flow:N", title=None,
                        scale=alt.Scale(domain=["Money in", "Money out"], range=[GOOD, BAD]),
                        legend=alt.Legend(orient="top")),
        tooltip=["Period", "Flow", alt.Tooltip("Amount:Q", format=",.2f"),
                 alt.Tooltip("Net:Q", format="+,.2f", title="Net for period")],
    ).properties(height=320)
    st.altair_chart(chart, width="stretch")

    unit = {"day": "day", "week": "7-day block", "month": "calendar month"}[cf["bucket"]]
    note = f"{cf['start']} → {cf['end']} · one bar pair per {unit}."
    if len(cf["currencies"]) > 1:
        note += (f" Mixed currencies ({', '.join(c.upper() for c in cf['currencies'])}) "
                 "are summed as entered, not converted.")
    st.caption(note)
