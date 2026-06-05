"""pages/4_monte_carlo.py - Monte Carlo Simulation on the auto valuation."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import numpy as np
import plotly.graph_objects as go
from streamlit_extras.let_it_rain import rain

from utils.monte_carlo_logic import run_monte_carlo
from utils.ai_helper import get_ai_explanation, build_monte_carlo_prompt
from theme import (
    inject_global_css,
    inject_keyboard_sound,
    inject_audio_autoplay_helper,
    render_navbar,
    sidebar_audio_player,
    THEME,
)


def fmt_big(v):
    """Format a large dollar amount as $1.23T / $450.2B / $1.5M."""
    if v is None or not np.isfinite(v):
        return "—"
    av = abs(v)
    sign = "-" if v < 0 else ""
    if av >= 1e12: return f"{sign}${av/1e12:.2f}T"
    if av >= 1e9:  return f"{sign}${av/1e9:.2f}B"
    if av >= 1e6:  return f"{sign}${av/1e6:.2f}M"
    if av >= 1e3:  return f"{sign}${av/1e3:.2f}K"
    return f"{sign}${av:.2f}"


st.set_page_config(
    page_title="Monte Carlo | The Valuation Tool",
    page_icon=None, layout="wide", initial_sidebar_state="expanded",
)

inject_global_css()
inject_keyboard_sound()
inject_audio_autoplay_helper()

for k, v in {
    "auto_result": None, "auto_ticker": "", "screener_results": None,
    "manual_result": None, "mc_result": None, "mc_ai_explanation": None,
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

render_navbar("Monte Carlo Simulation")

st.markdown('<div class="section-header">Monte Carlo Simulation</div>', unsafe_allow_html=True)

with st.container(border=True):
    st.markdown(f"""
### What is a Monte Carlo Simulation?

A standard DCF valuation gives you **one number** based on a single estimate for
growth, discount rate, and other inputs. The reality is that **none of those inputs
is known with certainty**.

A Monte Carlo simulation runs the DCF **thousands of times**, each time drawing the
key inputs randomly from a probability distribution centered on the auto-valuation's
estimate. The output is a **distribution** of possible intrinsic values — letting you
answer questions like:

- What is the **probability** the stock is worth more than its current price?
- What's the **median** fair value, and the 10th-to-90th percentile range?
- Which input variable has the **biggest impact** on the valuation? (Tornado chart)

This page uses your most recent **Automatic Valuation** as the baseline. Tweak the
standard deviations below to widen or narrow the uncertainty bands. Higher stdev =
less confidence in that input.
""")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

if st.session_state.auto_result is None:
    st.warning(
        "No automatic valuation loaded. Please run the **Automatic Valuation** first — "
        "the Monte Carlo simulation uses its FCF, growth, and discount rate as the baseline."
    )
    if st.button("Go to Auto Valuation"):
        st.switch_page("pages/2_Automated_Stock_Valuation_and_Analysis.py" if os.path.exists(
            os.path.join(os.path.dirname(__file__), "2_Automated_Stock_Valuation_and_Analysis.py")
        ) else "pages/2_auto_valuation.py")
    st.stop()

ar = st.session_state.auto_result
ticker_label = st.session_state.auto_ticker

st.success(
    f"Loaded auto valuation for **{ticker_label}** — "
    f"Auto IV: **${ar['adjusted_value']:.2f}** | "
    f"Growth: {ar['expected_growth_rate']:.1f}% | "
    f"WACC: {ar['discount_rate']:.2f}%"
)
st.markdown("")

st.markdown('<div class="section-header">Simulation Parameters</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Distribution Stdevs", "Run Settings"])

with tab1:
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        growth_stdev = st.slider("Growth Rate Stdev (%)", 0.5, 8.0, 2.5, 0.1)
        wacc_stdev = st.slider("WACC Stdev (%)", 0.2, 3.0, 1.0, 0.1)
    with cc2:
        perp_growth_mean = st.slider("Perpetual Growth Mean (%)", 0.5, 5.0, 3.0, 0.1)
        perp_growth_stdev = st.slider("Perpetual Growth Stdev (%)", 0.1, 2.0, 0.5, 0.1)
    with cc3:
        multiplier_stdev = st.slider("Multiplier Stdev", 0.02, 0.5, 0.10, 0.01)
        fcf_shock_stdev = st.slider("FCF Y1 Shock Stdev (%)", 1.0, 20.0, 5.0, 0.5)

with tab2:
    rc1, rc2 = st.columns(2)
    with rc1:
        n_sims = st.select_slider(
            "Number of Simulations", options=[1000, 2500, 5000, 10000, 25000], value=5000
        )
    with rc2:
        seed = st.number_input("Random Seed", value=42, step=1)

st.markdown("")
run_col, _ = st.columns([1, 4])
with run_col:
    run_mc = st.button("Run Simulation", key="run_mc_btn")

if run_mc:
    with st.spinner(f"Running {n_sims:,} simulations for {ticker_label}..."):
        result = run_monte_carlo(
            ar, n_sims=n_sims,
            growth_stdev=growth_stdev, wacc_stdev=wacc_stdev,
            perp_growth_mean=perp_growth_mean, perp_growth_stdev=perp_growth_stdev,
            multiplier_stdev=multiplier_stdev, fcf_shock_stdev=fcf_shock_stdev,
            seed=int(seed),
        )
    if result is None:
        st.error("Simulation failed — check that the auto valuation has valid FCF and shares outstanding.")
    else:
        st.session_state.mc_result = result
        st.session_state.mc_ai_explanation = None
        if result["prob_upside"] > 70:
            rain(emoji="$", font_size=22, falling_speed=7, animation_length=1)
        st.toast(f"Monte Carlo complete — {result['n_sims']:,} valid simulations")

mc = st.session_state.mc_result
if mc:
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    st.markdown('<div class="big-explain-btn">', unsafe_allow_html=True)
    if st.button(
        f"Explanation of why this valuation was calculated for {ticker_label}",
        key="explain_mc", use_container_width=True,
    ):
        with st.spinner("Generating explanation..."):
            st.session_state.mc_ai_explanation = get_ai_explanation(
                build_monte_carlo_prompt(mc, ar, ticker_label)
            )
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.mc_ai_explanation:
        with st.container(border=True):
            st.markdown(f"### AI Analysis - {ticker_label}")
            st.markdown(st.session_state.mc_ai_explanation)

    # === PER-SHARE METRICS ===
    st.markdown('<div class="section-header">Per-Share Intrinsic Value</div>', unsafe_allow_html=True)
    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    with mc1: st.metric("Current Price", f"${mc['current_price']:.2f}")
    with mc2: st.metric("P10 (Bear)",    f"${mc['p10']:.2f}")
    with mc3: st.metric("P50 (Median)",  f"${mc['p50']:.2f}")
    with mc4: st.metric("P90 (Bull)",    f"${mc['p90']:.2f}")
    with mc5: st.metric("Auto IV",       f"${mc['auto_iv']:.2f}")

    st.markdown("")
    pc1, pc2, pc3 = st.columns(3)
    with pc1: st.metric("P(IV > Current Price)", f"{mc['prob_upside']:.1f}%")
    with pc2: st.metric("P(IV > 2x Current)",    f"{mc['prob_double']:.1f}%")
    with pc3: st.metric("P(IV < 80% Current)",   f"{mc['prob_loss']:.1f}%")

    # === MARKET CAP / ENTERPRISE VALUE METRICS ===
    st.markdown("")
    st.markdown('<div class="section-header">Total Enterprise Value (Market Cap Scale)</div>',
                unsafe_allow_html=True)
    ec1, ec2, ec3, ec4, ec5 = st.columns(5)
    with ec1: st.metric("Current Mkt Cap", fmt_big(mc["current_market_cap"]))
    with ec2: st.metric("P10 (Bear)",      fmt_big(mc["mc_p10"]))
    with ec3: st.metric("P50 (Median)",    fmt_big(mc["mc_p50"]))
    with ec4: st.metric("P90 (Bull)",      fmt_big(mc["mc_p90"]))
    with ec5: st.metric("Mean",            fmt_big(mc["mc_mean"]))

    # === HISTOGRAM (per-share) ===
    st.markdown("")
    samples = mc["iv_samples"]
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Histogram(
        x=samples, nbinsx=60,
        marker=dict(color=THEME["primary"], line=dict(color=THEME["border"], width=0.5)),
        name="Simulations",
    ))
    fig_hist.add_vline(x=mc["current_price"], line_dash="solid", line_color="#E07B7B",
                       annotation_text=f"Price ${mc['current_price']:.0f}", annotation_position="top")
    fig_hist.add_vline(x=mc["p50"], line_dash="dash", line_color=THEME["text"],
                       annotation_text=f"Median ${mc['p50']:.0f}", annotation_position="top")
    fig_hist.add_vline(x=mc["p10"], line_dash="dot", line_color=THEME["muted"],
                       annotation_text="P10", annotation_position="bottom")
    fig_hist.add_vline(x=mc["p90"], line_dash="dot", line_color=THEME["muted"],
                       annotation_text="P90", annotation_position="bottom")
    fig_hist.update_layout(
        title=dict(text=f"Per-Share Intrinsic Value Distribution - {mc['n_sims']:,} sims - {ticker_label}",
                   font=dict(color=THEME["text"], size=15)),
        plot_bgcolor=THEME["card"], paper_bgcolor=THEME["card"],
        font=dict(color=THEME["text"], family="Inter"),
        xaxis=dict(title="Intrinsic Value per Share (USD)", gridcolor=THEME["border"]),
        yaxis=dict(title="Frequency", gridcolor=THEME["border"]),
        margin=dict(t=50, b=40, l=40, r=40), height=380, showlegend=False,
    )
    st.plotly_chart(fig_hist, use_container_width=True)

    # === MARKET CAP HISTOGRAM ===
    mc_samples = mc["mc_samples"]
    cur_mc = mc["current_market_cap"]
    fig_mc = go.Figure()
    fig_mc.add_trace(go.Histogram(
        x=mc_samples / 1e9, nbinsx=60,
        marker=dict(color=THEME["primary_hover"], line=dict(color=THEME["border"], width=0.5)),
    ))
    fig_mc.add_vline(x=cur_mc / 1e9, line_dash="solid", line_color="#E07B7B",
                     annotation_text=f"Current {fmt_big(cur_mc)}", annotation_position="top")
    fig_mc.add_vline(x=mc["mc_p50"] / 1e9, line_dash="dash", line_color=THEME["text"],
                     annotation_text=f"Median {fmt_big(mc['mc_p50'])}", annotation_position="top")
    fig_mc.update_layout(
        title=dict(text=f"Total Enterprise Value Distribution - {ticker_label}",
                   font=dict(color=THEME["text"], size=15)),
        plot_bgcolor=THEME["card"], paper_bgcolor=THEME["card"],
        font=dict(color=THEME["text"], family="Inter"),
        xaxis=dict(title="Enterprise Value (Billions USD)", gridcolor=THEME["border"]),
        yaxis=dict(title="Frequency", gridcolor=THEME["border"]),
        margin=dict(t=50, b=40, l=40, r=40), height=360, showlegend=False,
    )
    st.plotly_chart(fig_mc, use_container_width=True)

    # === CDF (per-share) ===
    sorted_samples = np.sort(samples)
    cdf = np.arange(1, len(sorted_samples) + 1) / len(sorted_samples) * 100
    fig_cdf = go.Figure()
    fig_cdf.add_trace(go.Scatter(
        x=sorted_samples, y=cdf, mode="lines",
        line=dict(color=THEME["primary"], width=2.5),
    ))
    fig_cdf.add_vline(x=mc["current_price"], line_dash="solid", line_color="#E07B7B",
                      annotation_text=f"Price ${mc['current_price']:.0f}")
    fig_cdf.update_layout(
        title=dict(text=f"Cumulative Probability (Per-Share) - {ticker_label}",
                   font=dict(color=THEME["text"], size=15)),
        plot_bgcolor=THEME["card"], paper_bgcolor=THEME["card"],
        font=dict(color=THEME["text"], family="Inter"),
        xaxis=dict(title="Intrinsic Value per Share (USD)", gridcolor=THEME["border"]),
        yaxis=dict(title="P(IV <= x) %", gridcolor=THEME["border"], range=[0, 100]),
        margin=dict(t=50, b=40, l=40, r=40), height=350, showlegend=False,
    )
    st.plotly_chart(fig_cdf, use_container_width=True)

    # === TORNADO ===
    st.markdown('<div class="section-header">Tornado Sensitivity</div>', unsafe_allow_html=True)
    st.markdown(
        f"<div style='color:{THEME['muted']};font-size:0.9rem;'>"
        "Shows how much per-share IV changes when each input is shifted by ±1 standard deviation, "
        "with all other inputs held at their mean. Longer bar = bigger impact."
        "</div>", unsafe_allow_html=True
    )
    torn = mc["tornado"]
    base = torn[0]["base"]
    names = [t["variable"] for t in torn][::-1]
    lows = [t["low"] - base for t in torn][::-1]
    highs = [t["high"] - base for t in torn][::-1]

    fig_torn = go.Figure()
    fig_torn.add_trace(go.Bar(
        y=names, x=lows, orientation="h", name="-1 stdev",
        marker_color="#7CD992", text=[f"${t['low']:.0f}" for t in torn][::-1],
        textposition="outside",
    ))
    fig_torn.add_trace(go.Bar(
        y=names, x=highs, orientation="h", name="+1 stdev",
        marker_color=THEME["primary"], text=[f"${t['high']:.0f}" for t in torn][::-1],
        textposition="outside",
    ))
    fig_torn.update_layout(
        title=dict(text=f"Tornado Sensitivity (base IV = ${base:.2f}/share)",
                   font=dict(color=THEME["text"], size=15)),
        barmode="overlay", plot_bgcolor=THEME["card"], paper_bgcolor=THEME["card"],
        font=dict(color=THEME["text"], family="Inter"),
        xaxis=dict(title="Change in IV vs Base ($/share)", gridcolor=THEME["border"],
                   zeroline=True, zerolinecolor=THEME["text"], zerolinewidth=1.5),
        yaxis=dict(gridcolor=THEME["border"]),
        legend=dict(bgcolor=THEME["card"], bordercolor=THEME["border"]),
        margin=dict(t=50, b=40, l=120, r=40), height=350,
    )
    st.plotly_chart(fig_torn, use_container_width=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    nc1, nc2, nc3, _ = st.columns([1, 1, 1, 2])
    auto_path = "pages/2_Automated_Stock_Valuation_and_Analysis.py" if os.path.exists(
        os.path.join(os.path.dirname(__file__), "2_Automated_Stock_Valuation_and_Analysis.py")
    ) else "pages/2_auto_valuation.py"
    manual_path = "pages/3_Manual_Tweaks_To_Valuation_Parameters.py" if os.path.exists(
        os.path.join(os.path.dirname(__file__), "3_Manual_Tweaks_To_Valuation_Parameters.py")
    ) else "pages/3_manual_valuation.py"
    with nc1:
        if st.button("Back to Auto Valuation"):
            st.switch_page(auto_path)
    with nc2:
        if st.button("Manual Valuation"):
            st.switch_page(manual_path)
    with nc3:
        if st.button("Back to Home"):
            st.switch_page("home_page.py")
else:
    st.markdown(
        f"""<div style="text-align:center;padding:3rem 2rem;">
        <div style="font-size:1.1rem;font-weight:600;color:{THEME['muted']};">
        Adjust parameters above and press Run Simulation</div>
        <div style="font-size:0.9rem;color:{THEME['faint']};margin-top:0.5rem;">
        Defaults are calibrated to {ticker_label}'s auto valuation</div></div>""",
        unsafe_allow_html=True,
    )