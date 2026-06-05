"""app.py - Entry point. Auto-registers any page found in pages/."""
import os
import streamlit as st

st.set_page_config(
    page_title="The Valuation Tool",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_PAGES_DIR = os.path.join(_PROJECT_ROOT, "pages")


def _find(keywords):
    if not os.path.isdir(_PAGES_DIR):
        return None
    for fname in sorted(os.listdir(_PAGES_DIR)):
        if not fname.endswith(".py"):
            continue
        lower = fname.lower()
        for kw in keywords:
            if kw.lower() in lower:
                return f"pages/{fname}"
    return None


pages_list = [st.Page("home_page.py", title="Homepage", default=True)]

p = _find(["screener", "undervalued"])
if p: pages_list.append(st.Page(p, title="Undervalued Stock Screener"))

p = _find(["auto_valuation", "automated"])
if p: pages_list.append(st.Page(p, title="Automated Stock Valuation and Analysis"))

p = _find(["manual", "tweaks"])
if p: pages_list.append(st.Page(p, title="Manual Tweaks to Valuation Parameters"))

p = _find(["monte_carlo", "montecarlo", "monte"])
if p: pages_list.append(st.Page(p, title="Monte Carlo Simulation"))

pg = st.navigation(pages_list)
pg.run()