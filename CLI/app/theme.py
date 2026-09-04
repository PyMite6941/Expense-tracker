"""Shared visual identity for every Streamlit surface.

IMPORTANT: this is the single source of truth for styling. Both the local
multipage app (entrypoint CLI/app/main.py) and the hosted single-file app
(published/app.py) import from here, so the deployed URL looks EXACTLY like the
local one. Never style a page inline — add it here instead.

`.streamlit/config.toml` sets the base Streamlit chrome colors to match; this
module layers the custom look on top.

Everything degrades gracefully: Streamlit's internal test-ids can change between
versions, so if a selector stops matching the app still works, it just loses a
little polish.
"""
from __future__ import annotations

import streamlit as st

# ── Brand palette ────────────────────────────────────────────────────────────
INK = "#0f172a"
ACCENT = "#4f46e5"
ACCENT_SOFT = "#6366f1"
GOOD = "#10b981"
WARN = "#f59e0b"
BAD = "#ef4444"

# Every page in the app, in nav order: (script path, label, icon)
# Paths are relative to the entrypoint dir (CLI/app/).
PAGES = [
    ("Dashboard.py", "Overview", "🏠"),
    ("pages/Monthly Summary.py", "Monthly", "📅"),
    ("pages/Recurring Expenses.py", "Recurring", "🔁"),
    ("pages/Pro Features.py", "Pro", "✨"),
    ("pages/Email Import.py", "Import", "📧"),
    ("pages/Phone Connect.py", "Phone", "📱"),
    ("pages/Settings.py", "Settings", "⚙️"),
]

_CSS = """
<style>
/* ── Type + rhythm ────────────────────────────────────────────────────── */
html, body, [class*="css"] {
  font-feature-settings: "tnum" 1, "cv02" 1;
}
.block-container {
  padding-top: 1.6rem !important;
  padding-bottom: 3rem !important;
  max-width: 1180px;
}
h1 { font-size: 1.65rem !important; font-weight: 700 !important; letter-spacing: -0.02em; }
h2 { font-size: 1.2rem  !important; font-weight: 650 !important; letter-spacing: -0.01em; }
h3 { font-size: 1.02rem !important; font-weight: 600 !important; }

/* ── Brand header ─────────────────────────────────────────────────────── */
.grid-header {
  display: flex; align-items: center; gap: .7rem;
  padding: .1rem 0 .5rem 0;
}
.grid-header .mark {
  width: 30px; height: 30px; border-radius: 9px; flex: 0 0 auto;
  background: linear-gradient(135deg, #4f46e5, #06b6d4);
  box-shadow: 0 2px 10px rgba(79,70,229,.35);
}
.grid-header .name { font-weight: 700; font-size: 1.06rem; letter-spacing: -.02em; }
.grid-header .badge {
  margin-left: auto; font-size: .68rem; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase; padding: .22rem .55rem; border-radius: 999px;
  border: 1px solid rgba(128,128,128,.32); opacity: .85;
}
.grid-header .badge.hosted  { border-color: rgba(79,70,229,.55); color: #6366f1; }
.grid-header .badge.local   { border-color: rgba(16,185,129,.5);  color: #10b981; }
.grid-header .badge.session { border-color: rgba(245,158,11,.6);  color: #f59e0b; }

/* ── Nav bar ──────────────────────────────────────────────────────────── */
.grid-nav-wrap { border-bottom: 1px solid rgba(128,128,128,.20); margin-bottom: 1.1rem; }
div[data-testid="stHorizontalBlock"]:has(> div a[data-testid="stPageLink-NavLink"]) { gap: .1rem; }
a[data-testid="stPageLink-NavLink"] {
  border-radius: 8px 8px 0 0; padding: .42rem .7rem !important;
  font-size: .875rem !important; font-weight: 550 !important;
  opacity: .72; transition: all .13s ease; border-bottom: 2px solid transparent;
}
a[data-testid="stPageLink-NavLink"]:hover {
  opacity: 1; background: rgba(128,128,128,.09); border-bottom-color: rgba(99,102,241,.45);
}

/* ── Metrics as cards ─────────────────────────────────────────────────── */
div[data-testid="stMetric"] {
  background: rgba(128,128,128,.055);
  border: 1px solid rgba(128,128,128,.18);
  border-radius: 12px; padding: .85rem 1rem;
}
div[data-testid="stMetric"] label { opacity: .72; font-size: .78rem !important; font-weight: 600 !important; }
div[data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 700 !important; letter-spacing: -.02em; }

/* ── Cards (st.container(border=True)) ────────────────────────────────── */
/* Matches the metric-card treatment so a panel and the metrics inside it read
   as one object. Metrics nested in a card drop their own border to avoid a
   box-in-a-box. */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(128,128,128,.04);
  border: 1px solid rgba(128,128,128,.18) !important;
  border-radius: 14px;
  padding: 1rem 1.15rem !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stMetric"] {
  background: transparent; border: 0; padding: .2rem 0;
}
div[data-testid="stVerticalBlockBorderWrapper"] .grid-section { margin-top: 0; }

/* ── Tabs ─────────────────────────────────────────────────────────────── */
button[data-baseweb="tab"] { font-weight: 560 !important; font-size: .9rem !important; }
div[data-baseweb="tab-border"] { background: rgba(128,128,128,.2); }

/* ── Controls ─────────────────────────────────────────────────────────── */
div[data-testid="stButton"] > button {
  border-radius: 9px; font-weight: 580; transition: transform .08s ease, box-shadow .15s ease;
}
div[data-testid="stButton"] > button:hover { transform: translateY(-1px); }
div[data-testid="stButton"] > button[kind="primary"] { box-shadow: 0 3px 12px rgba(79,70,229,.32); }
div[data-testid="stDownloadButton"] > button { border-radius: 9px; font-weight: 580; }

/* ── Panels ───────────────────────────────────────────────────────────── */
div[data-testid="stExpander"] details {
  border: 1px solid rgba(128,128,128,.2); border-radius: 11px; overflow: hidden;
}
div[data-testid="stForm"] {
  border: 1px solid rgba(128,128,128,.2); border-radius: 12px; padding: 1rem 1.1rem;
}
div[data-testid="stProgress"] > div > div > div { border-radius: 999px; }
hr { margin: 1.1rem 0 !important; opacity: .35; }

/* ── Sidebar ──────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] { border-right: 1px solid rgba(128,128,128,.18); }
section[data-testid="stSidebar"] .block-container { padding-top: 1.1rem; }
/* Compact metrics in the rail — the card treatment is too heavy at this width */
section[data-testid="stSidebar"] div[data-testid="stMetric"] {
  background: transparent; border: 0; padding: .1rem 0;
}
section[data-testid="stSidebar"] div[data-testid="stMetricValue"] { font-size: 1.05rem !important; }
section[data-testid="stSidebar"] div[data-testid="stMetric"] label { font-size: .7rem !important; }
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
  border-radius: 8px; padding: .3rem .5rem !important; border-bottom: 0;
}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
  background: rgba(128,128,128,.1);
}
section[data-testid="stSidebar"] hr { margin: .7rem 0 !important; }
.grid-side-brand { display: flex; align-items: center; gap: .55rem; margin-bottom: .6rem; }
.grid-side-brand .mark {
  width: 24px; height: 24px; border-radius: 7px; flex: 0 0 auto;
  background: linear-gradient(135deg, #4f46e5, #06b6d4);
  box-shadow: 0 2px 8px rgba(79,70,229,.35);
}
.grid-side-brand .name { font-weight: 700; letter-spacing: -.02em; }

/* ── Section heading ──────────────────────────────────────────────────── */
.grid-section { margin: .3rem 0 .9rem 0; }
.grid-section .t { font-weight: 650; font-size: 1.02rem; letter-spacing: -.01em; }
.grid-section .s { opacity: .62; font-size: .84rem; margin-top: .12rem; }

/* ── Misc ─────────────────────────────────────────────────────────────── */
#MainMenu, footer { visibility: hidden; }
</style>
"""


# Hides Streamlit's own page list. ONLY applied when we render our own top nav.
# published/app.py uses st.navigation(), which lives in the sidebar — hiding it
# there would remove that app's only means of navigation.
# Streamlit's own sidebar stylesheet wins the cascade against a plain
# attribute selector, so this needs !important — without it the auto page list
# renders underneath our own nav and you get the links twice.
_HIDE_SIDEBAR_NAV = """
<style>
[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stSidebarHeader"] { padding-bottom: 0 !important; }
</style>
"""


def inject_css(hide_sidebar_nav: bool = False) -> None:
    """Apply the visual identity. Use this directly when a surface manages its
    own page config / navigation (e.g. the published single-file app)."""
    st.markdown(_CSS, unsafe_allow_html=True)
    if hide_sidebar_nav:
        st.markdown(_HIDE_SIDEBAR_NAV, unsafe_allow_html=True)


def page_setup(title: str = "GRID Expense Tracker", icon: str = "💸",
               layout: str = "wide", nav: bool = True) -> None:
    """Call FIRST on every page. Sets config, injects the theme, draws the nav.

    Safe to call more than once — set_page_config raises if repeated, which we
    swallow so importing modules can't break a page.

    The sidebar is drawn separately by `render_sidebar()`, which pages call
    AFTER `init_st()` — it reports live totals, and session_state has not been
    populated yet at the point this runs.
    """
    try:
        st.set_page_config(
            page_title=title, page_icon=icon, layout=layout,
            initial_sidebar_state="expanded",
        )
    except Exception:
        pass  # already configured by an earlier call on this run
    inject_css(hide_sidebar_nav=nav)
    render_header()
    if nav:
        render_nav()


def render_sidebar(active: str = None) -> None:
    """The persistent sidebar: where you are, what you're looking at, and the
    numbers that matter, on every page.

    Call AFTER init_st(). Reads only from session_state, so it never triggers a
    load of its own and stays correct whichever storage backend is in play.

    Deliberately NOT a copy of the top nav. A sidebar that only repeats the
    navbar earns none of the width it takes — this carries the state you would
    otherwise have to change page to check.
    """
    from datetime import datetime

    with st.sidebar:
        st.markdown(
            '<div class="grid-side-brand"><div class="mark"></div>'
            '<div class="name">GRID</div></div>',
            unsafe_allow_html=True,
        )

        # ── Where the data lives ────────────────────────────────────────────
        hosted = bool(st.session_state.get("org_id"))
        if hosted:
            st.caption(f"☁️ Hosted · org #{st.session_state['org_id']}"
                       + (f" · {st.session_state['role']}" if st.session_state.get("role") else ""))
        else:
            st.caption("💾 Local · this machine")

        tier = st.session_state.get("pro_tier")
        if tier:
            st.caption(f"🔑 {tier.upper()} licence")
        else:
            st.caption("🔑 Free plan")

        st.divider()

        # ── This month at a glance ──────────────────────────────────────────
        month = st.session_state.get("current_month") or datetime.now().strftime("%Y-%m")
        expenses = st.session_state.get("expenses") or []
        income = st.session_state.get("income") or []
        spent = sum(float(e.get("price", 0) or 0)
                    for e in expenses if str(e.get("date", ""))[:7] == month)
        earned = sum(float(i.get("amount", 0) or 0)
                     for i in income if str(i.get("date", ""))[:7] == month)

        st.markdown(f"**{month}**")
        c1, c2 = st.columns(2)
        c1.metric("In", f"{earned:,.0f}")
        c2.metric("Out", f"{spent:,.0f}")
        st.metric("Net", f"{earned - spent:,.2f}",
                  delta=f"{earned - spent:+,.0f}")

        # ── What needs attention ────────────────────────────────────────────
        alerts = []
        budgets = st.session_state.get("budget") or []
        if budgets:
            by_cat = {}
            for e in expenses:
                if str(e.get("date", ""))[:7] == month:
                    tag = e.get("tags", "Other")
                    by_cat[tag] = by_cat.get(tag, 0) + float(e.get("price", 0) or 0)
            over = [b["category"] for b in budgets
                    if by_cat.get(b["category"], 0) > float(b.get("amount", 0) or 0) > 0]
            if over:
                alerts.append(f"🚨 Over budget: {', '.join(over)}")
        if not expenses and not income:
            alerts.append("👋 No data yet — add some on Manage")
        for a in alerts:
            st.caption(a)

        st.divider()

        # ── Navigation ──────────────────────────────────────────────────────
        for target, label, icon in _nav_targets():
            try:
                st.page_link(target, label=label, icon=icon)
            except Exception:
                pass

        st.divider()
        st.caption(f"v{_version()}")


def _version() -> str:
    """App version, or a blank if core isn't importable from this surface."""
    try:
        from CLI.core.core_stuff import __version__
        return str(__version__).lstrip("v")
    except Exception:
        return ""


def render_header(mode: str = None) -> None:
    """Brand bar + a badge showing where this session's data actually lives.

    Keys off the configured mode, NOT session_state['org_id'] — the header
    renders before init_st() populates org_id, so relying on it would label a
    hosted session "Local" on every first paint.

    `mode` forces the badge. Pass "session" for surfaces whose storage is
    ephemeral (the published demo app writes to a tempfile), so users are not
    told "Local" — which implies a file that persists — when nothing is kept.
    """
    if mode == "session":
        label, cls = "Demo · not saved", "session"
    else:
        hosted = bool(st.session_state.get("org_id"))
        if not hosted:
            try:
                from CLI.app.config import HOSTED_MODE
                hosted = HOSTED_MODE
            except Exception:
                pass
        label, cls = ("Hosted", "hosted") if hosted else ("Local", "local")
    st.markdown(
        f'<div class="grid-header"><div class="mark"></div>'
        f'<div class="name">GRID Expense Tracker</div>'
        f'<div class="badge {cls}">{label}</div></div>',
        unsafe_allow_html=True,
    )


def _nav_targets():
    """What the nav should link to, as (target, label, icon) triples.

    When main.py declares the app with st.navigation it stashes the StreamlitPage
    objects, and st.page_link wants those rather than file paths. Falling back to
    PAGES keeps the older `streamlit run Dashboard.py` entrypoint working, and
    keeps the published single-file app (which has neither) from crashing.
    """
    pages = st.session_state.get("_nav_pages")
    if pages:
        return [(p, p.title, p.icon) for p in pages]
    return list(PAGES)


def render_nav() -> None:
    """Horizontal nav bar. Uses st.page_link so it does real navigation."""
    targets = _nav_targets()
    st.markdown('<div class="grid-nav-wrap">', unsafe_allow_html=True)
    cols = st.columns(len(targets))
    for col, (target, label, icon) in zip(cols, targets):
        with col:
            try:
                st.page_link(target, label=label, icon=icon)
            except Exception:
                # Page missing (e.g. the published single-file app) — skip it
                # rather than crashing the whole surface.
                pass
    st.markdown("</div>", unsafe_allow_html=True)


def account_banner() -> None:
    """Surface hosted-mode problems consistently on every page.

    _build_tracker() deliberately never stops the app; it sets these flags and
    falls back to local storage. This turns them into a visible, actionable
    prompt instead of silent confusion about where the data went.
    """
    if st.session_state.get("needs_account"):
        st.warning(
            "You're on the public site but no account is saved, so you're "
            "seeing **local** data. Save an account in Settings to load your "
            "organization's workspace.",
            icon="🔐",
        )
    elif st.session_state.get("needs_entitlement"):
        st.warning(
            "This account has no active hosted subscription — showing **local** "
            "data. Your entitlement is linked to the email you buy with.",
            icon="🔑",
        )
        _b1, _b2, _ = st.columns([1, 1, 3])
        with _b1:
            st.link_button("Get hosted access →", _store_url(), type="primary")
        with _b2:
            try:
                st.page_link("pages/Settings.py", label="Settings", icon="⚙️")
            except Exception:
                pass
    if st.session_state.get("storage_error"):
        st.error(f"Could not reach the hosted database: "
                 f"{st.session_state['storage_error']}", icon="⚠️")


def upsell(feature: str, tier: str = "Pro", *, blocking: bool = False,
           detail: str = "") -> None:
    """The one way this app tells someone a feature is paid.

    Every gate says the same three things: what is locked, which tier unlocks
    it, and — the part that was missing almost everywhere — a link to actually
    buy it, plus a route to activate a key you already own.

    Before this, six of the eight gates named a tier and then dead-ended: "this
    is a Max feature" with nowhere to go. A paywall with no checkout is just a
    closed door.

    `blocking=True` is for gates that stop the page rendering entirely, so the
    upsell carries the full pitch rather than a one-liner.
    """
    tier_label = tier.strip().title()
    body = f"**{feature}** is a **{tier_label}** feature."
    if detail:
        body += f" {detail}"

    box = st.container(border=True) if blocking else st.container()
    with box:
        st.warning(body, icon="🔒") if blocking else st.info(body, icon="🔒")
        cols = st.columns([1, 1, 3])
        with cols[0]:
            st.link_button(f"Get {tier_label} →", _license_url(), type="primary")
        with cols[1]:
            try:
                st.page_link(_pro_page(), label="I have a key", icon="🔑")
            except Exception:
                st.caption("Activate on the Pro page.")


def _license_url() -> str:
    """Purchase URL, resolved late so a surface without config still renders."""
    try:
        from CLI.app.config import LICENSE_STORE_URL
        return LICENSE_STORE_URL
    except Exception:
        return "https://grid-store.pages.dev/codes"


def _store_url() -> str:
    try:
        from CLI.app.config import STORE_URL
        return STORE_URL
    except Exception:
        return "https://grid-store.pages.dev"


def _pro_page():
    """The Pro Features page, as whatever st.page_link accepts here."""
    pages = st.session_state.get("_nav_pages")
    if pages:
        for p in pages:
            if p.title == "Pro":
                return p
    return "pages/Pro Features.py"


def section(title: str, subtitle: str = "") -> None:
    """Consistent section heading."""
    sub = f'<div class="s">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="grid-section"><div class="t">{title}</div>{sub}</div>',
        unsafe_allow_html=True,
    )
