"""app.py - Entry point. Registers pages from theme.PAGE_PATHS (single source of truth)."""
import os
import streamlit as st

st.set_page_config(
    page_title="The Valuation Tool",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

from theme import PAGE_PATHS

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def _exists(rel_path):
    if not rel_path:
        return False
    full = os.path.join(_PROJECT_ROOT, rel_path.replace("/", os.sep))
    return os.path.isfile(full)


pages_list = [st.Page("home_page.py", title="Homepage", default=True)]

for label, rel_path in PAGE_PATHS.items():
    if label == "Homepage":
        continue
    if _exists(rel_path):
        pages_list.append(st.Page(rel_path, title=label))

pg = st.navigation(pages_list)
pg.run()