"""pages/3_manual_valuation.py - Manual DCF override."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from streamlit_tags import st_tags
from streamlit_plotly_events import plotly_events
import plotly.graph_objects as go
from streamlit_extras.let_it_rain import rain

from utils.valuation_logic import calculate_manual_valuation
from utils.ai_helper import get_ai_explanation, build_manual_prompt
from theme import (
    inject_global_css,
    inject_keyboard_sound,
    inject_audio_autoplay_helper,
    render_navbar,
    sidebar_audio_player,
    THEME,
)

st.set_page_config(
    page_title="Manual Valuation | The Valuation Tool",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()
inject_keyboard_sound()
inject_audio_autoplay_helper()

for k, v in {
    "auto_result": None, "auto_ticker": "", "screener_results": None,
    "manual_result": None, "manual_ai_explanation": None,
    "manual_clicked_year": None,
}.items():
    st.session_state.setdefault(k, v)

with st.sidebar:
    st.markdown(
        f'<p style="font-size:1.1rem;font-weight:800;color:{THEME["primary"]};">'
        "The Valuation Tool</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    sidebar_audio_player()

render_navbar("Manual Tweaks to Valuation Parameters")

st.markdown('<div class="section-header">Manual Valuation</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-sub">Override every assumption used in the automatic model. '
    'Requires an Auto Valuation to have been run first.</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

if st.session_state.auto_result is None:
    st.warning(
        "No automatic valuation loaded. Please run the **Automatic Valuation** first - "
        "Manual mode uses its FCF as the starting point."
    )
    if st.button("Go to Auto Valuation"):
        st.switch_page("pages/2_auto_valuation.py")
    st.stop()

ar = st.session_state.auto_result
ticker_label = st.session_state.auto_ticker

# === RESULTS AT TOP ===
mr = st.session_state.manual_result
if mr:
    st.markdown('<div class="big-explain-btn">', unsafe_allow_html=True)
    if st.button(
        f"Explanation of why this valuation was calculated for {ticker_label}",
        key="explain_manual", use_container_width=True,
    ):
        with st.spinner("Generating explanation..."):
            st.session_state.manual_ai_explanation = get_ai_explanation(
                build_manual_prompt(mr, ar, ticker_label)
            )
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.manual_ai_explanation:
        with st.container(border=True):
            st.markdown(f"### AI Analysis - {ticker_label}")
            st.markdown(st.session_state.manual_ai_explanation)

    st.markdown('<div class="section-header">Manual Valuation Result</div>', unsafe_allow_html=True)
    upside_val = mr["upside"]
    upside_sign = "+" if upside_val >= 0 else ""
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1: st.metric("Current Price",          f"${mr['current_price']:.2f}")
    with mc2: st.metric("Manual Intrinsic Value", f"${mr['m_dcf']:.2f}")
    with mc3: st.metric("Upside / Downside",      f"{upside_sign}{upside_val:.1f}%",
                        delta=f"{upside_sign}{upside_val:.1f}%",
                        delta_color="normal" if upside_val >= 0 else "inverse")
    with mc4: st.metric("vs Auto Value",          f"${ar['adjusted_value']:.2f}",
                        delta=f"{mr['m_dcf'] - ar['adjusted_value']:+.2f}")

    st.markdown("")
    years = [f"Y{i}" for i in range(1, 11)]
    manual_cvs = [v / 1e9 for v in mr["cvs"]]
    auto_cvs = [ar[f"fcf_y{i}"] / 1e9 for i in range(1, 11)]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Manual", x=years, y=manual_cvs, marker_color=THEME["primary"],
                         text=[f"${v:.1f}B" for v in manual_cvs], textposition="outside",
                         textfont=dict(size=10, color=THEME["text"])))
    fig.add_trace(go.Bar(name="Auto", x=years, y=auto_cvs, marker_color=THEME["muted"],
                         text=[f"${v:.1f}B" for v in auto_cvs], textposition="outside",
                         textfont=dict(size=10, color=THEME["text"])))
    fig.update_layout(
        title=dict(text=f"Manual vs Auto - 10-Year FCF Projection ({ticker_label}) - Click any bar",
                   font=dict(color=THEME["text"], size=15)),
        barmode="group", plot_bgcolor=THEME["bg"], paper_bgcolor=THEME["card"],
        font=dict(color=THEME["text"], family="Inter"),
        xaxis=dict(gridcolor=THEME["border"]),
        yaxis=dict(gridcolor=THEME["border"], title="FCF (Billions USD)"),
        legend=dict(bgcolor=THEME["card"], bordercolor=THEME["border"]),
        margin=dict(t=50, b=30, l=40, r=40), height=380,
    )

    clicked = plotly_events(fig, click_event=True, hover_event=False, override_height=380)
    if clicked:
        ev = clicked[0]
        yr_idx = ev.get("pointIndex", 0)
        which = "Manual" if ev.get("curveNumber", 0) == 0 else "Auto"
        val = manual_cvs[yr_idx] if which == "Manual" else auto_cvs[yr_idx]
        st.info(f"Year {yr_idx+1} ({which}): **${val:.2f}B**")

    with st.expander("Full Manual Calculation Breakdown"):
        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            st.metric("Base FCF",      f"${mr['M_FCF_N']/1e9:.2f}B")
            st.metric("Discount Rate", f"{mr['discount_rate']*100:.2f}%")
        with dc2:
            st.metric("Gordon TV",   f"${mr['Gordon_TV']/1e9:.2f}B")
            st.metric("Multiple TV", f"${mr['Multiple_TV']/1e9:.2f}B")
        with dc3:
            st.metric("Combined TV",     f"${mr['TV']/1e9:.2f}B")
            st.metric("Final Multiplier", f"x{mr['multiplier']:.2f}")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# === INPUTS BELOW ===
st.success(
    f"Loaded auto valuation for **{ticker_label}** - "
    f"Base FCF: ${ar['fcf_current']/1e9:.2f}B | Auto IV: **${ar['adjusted_value']:.2f}**"
)
st.markdown("")

tab1, tab2, tab3, tab4 = st.tabs(
    ["Year-by-Year Growth", "Discount Rate", "Final Multiplier", "Watchlist Tags"]
)

with tab1:
    st.markdown("Set the free cash flow growth rate for each of the 10 projection years.")
    col_a, col_b = st.columns(2)
    growth_vals = []
    base_g = ar.get("expected_growth_rate", 8.0)
    defaults = [base_g] * 3 + [max(base_g * 0.85, 3.0)] * 4 + [max(base_g * 0.6, 3.0)] * 3
    for i in range(10):
        col = col_a if i < 5 else col_b
        with col:
            val = st.slider(f"Year {i+1} Growth %", -20.0, 50.0,
                            value=round(defaults[i], 1), step=0.5, key=f"cg_{i+1}")
            growth_vals.append(val)

with tab2:
    dc1, dc2 = st.columns(2)
    with dc1:
        risk_free_rate = st.slider("Risk-Free Rate %", 0.5, 10.0,
                                   value=round(ar.get("risk_free_rate", 4.3), 1), step=0.1)
        perpetual_growth = st.slider("Perpetual Growth Rate %", 0.5, 5.0, value=3.0, step=0.1)
    with dc2:
        beta_multiplier = st.slider("Beta Multiplier", 0.5, 3.0,
                                    value=round(ar.get("beta", 1.2), 2), step=0.05)
        implied_r = risk_free_rate / 100 + beta_multiplier * 0.035
        st.metric("Implied Discount Rate", f"{implied_r*100:.2f}%")

with tab3:
    cc1, cc2 = st.columns([2, 1])
    with cc1:
        multiplier = st.slider("Final Multiplier", 0.1, 3.0, value=1.0, step=0.05)
    with cc2:
        st.metric("Multiplier Applied", f"x{multiplier:.2f}")

with tab4:
    st.markdown("Tag this stock with categories for your personal watchlist.")
    tags = st_tags(
        label="Tags",
        text="Add a tag and press enter",
        value=["undervalued"] if mr and mr["upside"] > 20 else [],
        suggestions=["undervalued", "overvalued", "watchlist", "buy", "hold", "sell",
                     "growth", "value", "dividend", "tech", "energy", "finance", "healthcare"],
        maxtags=10, key=f"tags_{ticker_label}",
    )
    if tags:
        st.success(f"Tags saved for {ticker_label}: {', '.join(tags)}")

st.markdown("")
run_col, _ = st.columns([1, 4])
with run_col:
    run_manual = st.button("Calculate Manual Valuation", key="run_manual_btn")

if run_manual:
    with st.spinner("Running manual DCF..."):
        result, err = calculate_manual_valuation(
            ticker_label, ar,
            growth_vals[0], growth_vals[1], growth_vals[2], growth_vals[3], growth_vals[4],
            growth_vals[5], growth_vals[6], growth_vals[7], growth_vals[8], growth_vals[9],
            perpetual_growth, beta_multiplier, risk_free_rate, multiplier,
        )
    if result is None:
        st.error(f"Manual valuation failed: {err}")
    else:
        st.session_state.manual_result = result
        st.session_state.manual_ai_explanation = None
        if result["upside"] > 25:
            rain(emoji="$", font_size=22, falling_speed=7, animation_length=1)
        st.rerun()

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
nc1, nc2, nc3, _ = st.columns([1, 1, 1, 2])
with nc1:
    if st.button("Back to Auto Valuation"):
        st.switch_page("pages/2_auto_valuation.py")
with nc2:
    if st.button("Run Monte Carlo Simulation"):
        st.switch_page("pages/4_monte_carlo.py")
with nc3:
    if st.button("Back to Home"):
        st.switch_page("app.py")