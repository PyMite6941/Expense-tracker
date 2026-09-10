"""Single entrypoint + URL router for the Streamlit app.

Run with:  streamlit run CLI/app/main.py

WHY THIS EXISTS
---------------
The app used to rely on Streamlit's `pages/` directory convention: drop a file
in `pages/`, get a route. That works, but the structure is implicit — nav order
came from filenames, URLs came from filenames, and there was no single place
that said "these are the pages of this app."

`st.navigation` moves that declaration into one file WITHOUT collapsing the app
into one file. Every page keeps its own module; this just declares them, their
order, their icons and their URLs. So:

  * one place defines the app's structure (here),
  * URLs stay real — /overview, /monthly, /settings — so links, bookmarks and
    browser back/forward all keep working,
  * each page script still only executes when it is the active page, which is
    the thing a single merged file would cost us.

`position="hidden"` suppresses Streamlit's own sidebar nav: theme.py already
draws both the top navbar and the sidebar, and two navs is worse than one.
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from CLI.app.theme import inject_css  # noqa: E402

# Must be the first Streamlit call in the process.
st.set_page_config(
    page_title="Finance Kit",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css(hide_sidebar_nav=True)

# The app's structure, in nav order. `url_path` is the route, and is
# deliberately short and lowercase — it is the thing users see and share.
PAGE_SPECS = [
    ("Dashboard.py",                 "Overview",  "🏠", "overview"),
    ("pages/Accounts.py",            "Accounts",  "🏦", "accounts"),
    ("pages/Monthly Summary.py",     "Monthly",   "📅", "monthly"),
    ("pages/Recurring Expenses.py",  "Recurring", "🔁", "recurring"),
    ("pages/Pro Features.py",        "Pro",       "✨", "pro"),
    ("pages/Email Import.py",        "Import",    "📧", "import"),
    ("pages/Phone Connect.py",       "Phone",     "📱", "phone"),
    ("pages/Settings.py",            "Settings",  "⚙️", "settings"),
]

_here = os.path.dirname(os.path.abspath(__file__))
pages = [
    st.Page(os.path.join(_here, script), title=title, icon=icon,
            url_path=url, default=(i == 0))
    for i, (script, title, icon, url) in enumerate(PAGE_SPECS)
]

# theme.py's navbar/sidebar render links from these. Handing over the Page
# objects (rather than file paths) is what st.page_link needs once navigation
# is declared here instead of inferred from the pages/ directory.
st.session_state["_nav_pages"] = pages

st.navigation(pages, position="hidden").run()
