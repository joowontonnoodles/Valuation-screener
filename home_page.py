"""home_page.py - Landing page with hero, quote shuffle, and 4 nav cards."""
import streamlit as st
import random
from theme import (
    inject_global_css,
    inject_keyboard_sound,
    inject_audio_autoplay_helper,
    render_navbar,
    sidebar_audio_player,
    THEME,
)

inject_global_css()
inject_keyboard_sound()
inject_audio_autoplay_helper()

QUOTES = [
    ("Price is what you pay. Value is what you get.", "Warren Buffett"),
    ("The intelligent investor is a realist who sells to optimists and buys from pessimists.", "Benjamin Graham"),
    ("Risk comes from not knowing what you're doing.", "Warren Buffett"),
    ("In the short run, the market is a voting machine. In the long run, a weighing machine.", "Benjamin Graham"),
    ("Be fearful when others are greedy and greedy when others are fearful.", "Warren Buffett"),
    ("The stock market is a device for transferring money from the impatient to the patient.", "Warren Buffett"),
    ("The investor's chief problem - and even his worst enemy - is likely to be himself.", "Benjamin Graham"),
    ("Wide diversification is only required when investors do not understand what they are doing.", "Warren Buffett"),
]

if "quote_idx" not in st.session_state:
    st.session_state.quote_idx = random.randint(0, len(QUOTES) - 1)

with st.sidebar:
    st.markdown(
        f'<p style="font-size:1.1rem;font-weight:800;color:{THEME["primary"]};">'
        "The Valuation Tool</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    sidebar_audio_player()

render_navbar("Homepage")

st.markdown(
    f"""<div style="text-align:center;padding:2.5rem 1rem 1rem 1rem;">
    <div style="font-size:3rem;font-weight:900;color:{THEME['primary']};letter-spacing:-1px;">
    The Valuation Tool</div>
    <div style="font-size:1.1rem;color:{THEME['muted']};margin-top:0.6rem;">
    Disciplined stock valuation - DCF, DDM, screener, manual override, and Monte Carlo.</div>
    </div>""",
    unsafe_allow_html=True,
)

q, who = QUOTES[st.session_state.quote_idx]
with st.container(border=True):
    st.markdown(
        f"""<div style="padding:1rem 0.5rem;text-align:center;">
        <div style="font-size:1.1rem;font-style:italic;color:{THEME['text']};">"{q}"</div>
        <div style="font-size:0.9rem;color:{THEME['muted']};margin-top:0.4rem;">- {who}</div>
        </div>""",
        unsafe_allow_html=True,
    )
sc, _ = st.columns([1, 5])
with sc:
    if st.button("Shuffle Quote", key="shuffle_quote"):
        st.session_state.quote_idx = random.randint(0, len(QUOTES) - 1)
        st.rerun()

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-header">Choose a Tool</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
        st.markdown("### Undervalued Stock Screener")
        st.markdown(
            f"<div style='color:{THEME['muted']};'>Scan large-caps over $100B, find the 25 biggest "
            "fallers, and rank them by base / bull / bear DCF upside.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Open Screener", key="nav_screener", use_container_width=True):
            st.switch_page("pages/1_screener.py")

    with st.container(border=True):
        st.markdown("### Manual Valuation")
        st.markdown(
            f"<div style='color:{THEME['muted']};'>Override every assumption used in the auto model "
            "and stress-test your thesis. Requires an Auto Valuation first.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Open Manual Valuation", key="nav_manual", use_container_width=True):
            st.switch_page("pages/3_manual_valuation.py")

with c2:
    with st.container(border=True):
        st.markdown("### Automatic Valuation")
        st.markdown(
            f"<div style='color:{THEME['muted']};'>Type any ticker and run a full DCF + DDM hybrid "
            "valuation automatically with quality multipliers and AI explanation.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Open Auto Valuation", key="nav_auto", use_container_width=True):
            st.switch_page("pages/2_auto_valuation.py")

    with st.container(border=True):
        st.markdown("### Monte Carlo Simulation")
        st.markdown(
            f"<div style='color:{THEME['muted']};'>Run thousands of randomized DCFs to see the full "
            "distribution of fair values, probability of upside, and tornado sensitivity. "
            "Requires an Auto Valuation first.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Open Monte Carlo", key="nav_mc", use_container_width=True):
            st.switch_page("pages/4_monte_carlo.py")