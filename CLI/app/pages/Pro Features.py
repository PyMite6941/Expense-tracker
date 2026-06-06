import os
import sys

import requests
import streamlit as st

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from core.core_stuff import ExpenseTracker

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "")
BACKEND_URL = os.getenv("BACKEND_URL", "")

st.set_page_config(page_title="Pro Features", page_icon="⭐")
st.title("⭐ Pro Features")

if not AUTH_SERVICE_URL or not BACKEND_URL:
    st.warning(
        "Set `AUTH_SERVICE_URL` and `BACKEND_URL` environment variables to connect to the services.",
        icon="⚠️",
    )

# ── License key input ────────────────────────────────────────────────────────

st.subheader("Activate your license")

saved_token = st.session_state.get("pro_token", "")
token_input = st.text_input(
    "License key",
    value=saved_token,
    type="password",
    placeholder="Paste the key from your purchase email…",
)

col_activate, col_clear = st.columns([1, 4])

with col_activate:
    if st.button("Activate", type="primary", disabled=not token_input):
        if not AUTH_SERVICE_URL:
            st.error("AUTH_SERVICE_URL is not configured.")
        else:
            try:
                resp = requests.post(
                    f"{AUTH_SERVICE_URL}/validate",
                    json={"token": token_input},
                    timeout=8,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state["pro_token"] = token_input
                    st.session_state["pro_email"] = data["email"]
                    st.success(f"License active — {data['email']}", icon="✅")
                    st.rerun()
                else:
                    st.error(f"Invalid or expired key. ({resp.status_code})")
            except requests.exceptions.ConnectionError:
                st.error("Could not reach the license server. Check AUTH_SERVICE_URL.")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

with col_clear:
    if st.session_state.get("pro_token") and st.button("Remove license"):
        st.session_state.pop("pro_token", None)
        st.session_state.pop("pro_email", None)
        st.rerun()

# ── Pro features (only shown when license is active) ─────────────────────────

if not st.session_state.get("pro_token"):
    st.divider()
    st.info(
        "No active license. [Purchase Pro]({}) to unlock advanced AI features.".format(
            os.getenv("PURCHASE_PAGE_URL", "#")
        )
    )
    st.stop()

st.divider()
st.subheader("Advanced Categorization")
st.caption(
    "Three CrewAI agents analyze your expenses: a Categorization Specialist assigns precise "
    "subcategories, a Pattern Analyst surfaces trends and anomalies, and a Finance Advisor "
    "generates specific budget recommendations."
)

context = st.text_input(
    "Focus (optional)",
    placeholder="e.g. 'Focus on the last 3 months' or leave blank for full analysis",
)

if st.button("Run Advanced Categorization", type="primary"):
    if not BACKEND_URL:
        st.error("BACKEND_URL is not configured.")
        st.stop()

    with st.spinner("Loading expenses…"):
        try:
            tracker = ExpenseTracker()
            expenses = tracker.view_total_expenses()
        except Exception as e:
            st.error(f"Could not load expense data: {e}")
            st.stop()

    if not expenses:
        st.warning("No expenses found. Add some expenses first.")
        st.stop()

    with st.spinner(f"Running AI analysis on {len(expenses)} expenses… this may take 30–60 seconds."):
        try:
            resp = requests.post(
                f"{BACKEND_URL}/advanced-categorize",
                json={
                    "expenses": expenses,
                    "context": context or "Advanced expense categorization with subcategories and pattern detection",
                },
                headers={"Authorization": f"Bearer {st.session_state['pro_token']}"},
                timeout=120,
            )
        except requests.exceptions.ConnectionError:
            st.error("Could not reach the backend. Check BACKEND_URL.")
            st.stop()
        except Exception as e:
            st.error(f"Request failed: {e}")
            st.stop()

    if resp.status_code == 401:
        st.error("License key rejected by backend. Your key may have expired.")
        st.stop()
    if not resp.ok:
        st.error(f"Analysis failed (HTTP {resp.status_code}): {resp.text}")
        st.stop()

    result = resp.json()
    st.session_state["last_categorization"] = result

# ── Display last result if available ─────────────────────────────────────────

result = st.session_state.get("last_categorization")
if result:
    st.divider()

    st.subheader("Summary")
    st.write(result.get("summary", "—"))

    findings = result.get("key_findings", [])
    if findings:
        st.subheader("Key Findings")
        for f in findings:
            st.markdown(f"- {f}")

    anomalies = result.get("anomalies", [])
    if anomalies:
        st.subheader("Anomalies")
        for a in anomalies:
            st.warning(a, icon="🚨")
    else:
        st.success("No anomalies detected in your spending.", icon="✅")

    recs = result.get("recommendations", [])
    if recs:
        st.subheader("Budget Recommendations")
        for r in recs:
            st.info(r, icon="💡")
