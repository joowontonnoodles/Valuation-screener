"""pages/2_auto_valuation.py - Automatic DCF + DDM valuation (no streamlit_echarts)."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from st_keyup import st_keyup
from streamlit_searchbox import st_searchbox
from streamlit_extras.let_it_rain import rain
import plotly.graph_objects as go

from utils.valuation_logic import calculate_automatic_valuation
from utils.ai_helper import get_ai_explanation, build_auto_prompt
from theme import (
    inject_global_css,
    inject_keyboard_sound,
    inject_audio_autoplay_helper,
    render_navbar,
    sidebar_audio_player,
    THEME,
)

st.set_page_config(
    page_title="Auto Valuation | The Valuation Tool",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()
inject_keyboard_sound()
inject_audio_autoplay_helper()

for k, v in {
    "auto_result": None, "auto_ticker": "", "screener_results": None,
    "manual_result": None, "auto_ai_explanation": None,
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

render_navbar("Automated Stock Valuation and Analysis")

POPULAR_TICKERS = [
    "AAPL","MSFT","GOOGL","GOOG","AMZN","META","NVDA","TSLA","AVGO","ORCL",
    "BRK-B","JPM","V","MA","WMT","JNJ","XOM","CVX","LLY","UNH","PG","HD",
    "BAC","ABBV","KO","PEP","MRK","TMO","COST","ADBE","NFLX","AMD","INTC",
    "CRM","DIS","NKE","MCD","PFE","WFC","CSCO","ABNB","PYPL","SHOP","UBER",
    "PLTR","SOFI","COIN","RIVN","F","GM","BA","GE","T","VZ","TMUS","QCOM",
]


def search_tickers(query):
    if not query:
        return []
    q = query.upper()
    return [t for t in POPULAR_TICKERS if t.startswith(q)][:10]


st.markdown('<div class="section-header">Automatic Valuation</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-sub">Type any ticker - autocomplete suggestions appear as you type. '
    'The model fetches all financial data and runs a full DCF + DDM hybrid valuation automatically.</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

inp_col, btn_col, _ = st.columns([2, 1, 3])
with inp_col:
    selected_ticker = st_searchbox(
        search_tickers,
        key="ticker_searchbox",
        placeholder="Type a ticker (AAPL, MSFT, NVDA...)",
        default=st.session_state.auto_ticker if st.session_state.auto_ticker else None,
    )
    typed_ticker = st_keyup(
        "Or type freely",
        value=st.session_state.auto_ticker,
        key="ticker_keyup",
        debounce=300,
    )
with btn_col:
    st.markdown("<div style='height:1.6rem;'></div>", unsafe_allow_html=True)
    run_auto = st.button("Analyse", key="run_auto_btn", use_container_width=True)

ticker_to_use = selected_ticker or typed_ticker

if run_auto and ticker_to_use and ticker_to_use.strip():
    ticker_clean = ticker_to_use.strip().upper()
    with st.spinner(f"Running valuation for **{ticker_clean}**..."):
        result = calculate_automatic_valuation(ticker_clean)
    if result is None:
        st.error(f"Could not complete valuation for **{ticker_clean}**.")
    else:
        st.session_state.auto_result = result
        st.session_state.auto_ticker = ticker_clean
        st.session_state.auto_ai_explanation = None
        if result.get("upside", 0) > 25:
            rain(emoji="$", font_size=22, falling_speed=7, animation_length=1)
        st.toast(f"Valuation complete for {ticker_clean}")

ar = st.session_state.auto_result
if ar:
    ticker_label = st.session_state.auto_ticker
    upside_val = ar["upside"]
    upside_sign = "+" if upside_val >= 0 else ""
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    if abs(upside_val) > 200:
        st.warning(
            f"Calculated upside of {upside_sign}{upside_val:.1f}% is unusually large. "
            "Double-check inputs (price, FCF, currency conversion) before trusting this number."
        )

    if ar.get("is_foreign"):
        st.info(
            f"Foreign ticker — financials in **{ar.get('reporting_ccy','?')}**, "
            f"price in **{ar.get('trading_ccy','?')}**. All values converted to USD."
        )

    st.markdown('<div class="big-explain-btn">', unsafe_allow_html=True)
    if st.button(
        f"Explanation of why this valuation was calculated for {ticker_label}",
        key="explain_auto", use_container_width=True,
    ):
        with st.spinner("Generating explanation..."):
            st.session_state.auto_ai_explanation = get_ai_explanation(
                build_auto_prompt(ar, ticker_label)
            )
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.auto_ai_explanation:
        with st.container(border=True):
            st.markdown(f"### AI Analysis - {ticker_label}")
            st.markdown(st.session_state.auto_ai_explanation)

    st.markdown("")
    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    with mc1: st.metric("Current Price",   f"${ar['current_price']:.2f}")
    with mc2: st.metric("Intrinsic Value", f"${ar['adjusted_value']:.2f}")
    with mc3: st.metric("Upside/Downside", f"{upside_sign}{upside_val:.1f}%",
                        delta=f"{upside_sign}{upside_val:.1f}%",
                        delta_color="normal" if upside_val >= 0 else "inverse")
    with mc4: st.metric("Discount Rate",   f"{ar['discount_rate']:.2f}%")
    with mc5: st.metric("Expected Growth", f"{ar['expected_growth_rate']:.1f}%")

    # --- Plotly gauge (replaces ECharts) ---
    st.markdown("")
    gauge_value = max(min(upside_val, 100), -50)
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(gauge_value, 1),
        number={"suffix": "%", "font": {"color": THEME["text"], "size": 28}},
        title={"text": f"{ticker_label} Upside",
               "font": {"color": THEME["text"], "size": 14}},
        gauge={
            "axis": {"range": [-50, 100],
                     "tickcolor": THEME["muted"],
                     "tickfont": {"color": THEME["muted"]}},
            "bar": {"color": THEME["primary"]},
            "bgcolor": THEME["card"],
            "bordercolor": THEME["border"],
            "steps": [
                {"range": [-50, -16],  "color": "#E07B7B"},
                {"range": [-16,  25],  "color": "#CFC6CB"},
                {"range": [ 25, 100],  "color": "#7CD992"},
            ],
            "threshold": {
                "line": {"color": THEME["text"], "width": 3},
                "thickness": 0.75,
                "value": round(gauge_value, 1),
            },
        },
    ))
    fig_gauge.update_layout(
        paper_bgcolor=THEME["card"],
        font={"color": THEME["text"], "family": "Inter"},
        height=320,
        margin=dict(t=40, b=20, l=20, r=20),
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

    # --- FCF projection bar (Plotly) ---
    st.markdown("")
    years = [f"Y{i}" for i in range(1, 11)]
    fcf_b = [round(ar[f"fcf_y{i}"] / 1e9, 2) for i in range(1, 11)]
    fig_fcf = go.Figure(go.Bar(
        x=years, y=fcf_b,
        marker=dict(color=THEME["primary"], line=dict(width=0)),
        text=[f"${v}B" for v in fcf_b], textposition="outside",
        textfont=dict(size=11, color=THEME["text"]),
    ))
    fig_fcf.update_layout(
        title=dict(text=f"10-Year Projected Free Cash Flow - {ticker_label}",
                   font=dict(color=THEME["text"], size=15)),
        plot_bgcolor=THEME["card"], paper_bgcolor=THEME["card"],
        font=dict(color=THEME["text"], family="Inter"),
        xaxis=dict(gridcolor=THEME["border"]),
        yaxis=dict(gridcolor=THEME["border"], title="FCF (Billions USD)"),
        margin=dict(t=50, b=30, l=40, r=40), height=380, showlegend=False,
    )
    st.plotly_chart(fig_fcf, use_container_width=True)

    st.markdown("")
    tab1, tab2, tab3 = st.tabs(
        ["Growth and Discount Rate", "Terminal Value and DCF", "Quality Multipliers"]
    )

    with tab1:
        ca, cb, cc = st.columns(3)
        with ca:
            st.metric("Historical Revenue Growth", f"{ar['rev_growth_historical']:.2f}%")
            st.metric("Analyst Growth Estimate",   f"{ar['rev_growth_analyst']:.2f}%")
        with cb:
            st.metric("Blended Expected Growth", f"{ar['expected_growth_rate']:.2f}%")
            st.metric("Risk-Free Rate",          f"{ar['risk_free_rate']:.2f}%")
        with cc:
            st.metric("Beta",               f"{ar['beta']:.2f}")
            st.metric("CAPM Discount Rate", f"{ar['discount_rate']:.2f}%")

    with tab2:
        ca, cb, cc = st.columns(3)
        with ca:
            st.metric("Current FCF (base)",    f"${ar['fcf_current']/1e9:.2f}B")
            st.metric("DCF Total (pre-adjust)", f"${ar['dcf_total']/1e9:.2f}B")
        with cb:
            st.metric("PV Terminal (Gordon)",   f"${ar['pv_tv_gordon']/1e9:.2f}B")
            st.metric("PV Terminal (Multiple)", f"${ar['pv_tv_multiple']/1e9:.2f}B")
        with cc:
            st.metric("PV Terminal Value (Final)", f"${ar['pv_tv_final']/1e9:.2f}B")
            st.metric("DCF per Share (pre-adjust)", f"${ar['dcf_per_share']:.2f}")

    with tab3:
        ca, cb = st.columns(2)
        mult_data = [
            ("EBITDA Margin", f"{ar['ebitda_margin']:.1f}%", ar["mult_ebitda"]),
            ("Debt/Equity",   f"{ar['de_ratio']:.2f}x",      ar["mult_de"]),
            ("CapEx Ratio",   f"{ar['capex_ratio']:.2f}x",   ar["mult_capex"]),
            ("ROE",           f"{ar['roe']:.1f}%",           ar["mult_roe"]),
            ("Current Ratio", f"{ar['current_ratio']:.2f}x", ar["mult_current"]),
        ]
        for i, (label, val, mult) in enumerate(mult_data):
            col = ca if i % 2 == 0 else cb
            with col:
                color = THEME["primary"] if mult >= 1.0 else THEME["muted"]
                st.markdown(
                    f"""<div style="background:{THEME['card']};border:1px solid {THEME['border']};
                    border-radius:10px;padding:0.8rem 1rem;margin-bottom:0.6rem;">
                    <div style="font-size:0.8rem;color:{THEME['muted']};">{label}</div>
                    <div style="font-size:1rem;font-weight:600;color:{THEME['text']};">{val}</div>
                    <div style="font-size:0.85rem;font-weight:700;color:{color};">x{mult:.2f}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        st.metric("Composite Multiplier", f"x{ar['composite_multiplier']:.4f}")
        st.metric("Final Adjusted Value / Share", f"${ar['adjusted_value']:.2f}")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    nc1, nc2, nc3, _ = st.columns([1, 1, 1, 2])
    with nc1:
        if st.button("Go to Manual Valuation"):
            st.switch_page("pages/3_manual_valuation.py")
    with nc2:
        if st.button("Run Monte Carlo Simulation"):
            st.switch_page("pages/4_monte_carlo.py")
    with nc3:
        if st.button("Back to Home"):
            st.switch_page("home_page.py")
else:
    st.markdown(
        f"""<div style="text-align:center;padding:4rem 2rem;">
        <div style="font-size:1.1rem;font-weight:600;color:{THEME['muted']};">
        Search a ticker and press Analyse</div>
        <div style="font-size:0.9rem;color:{THEME['faint']};margin-top:0.5rem;">
        Try: AAPL, MSFT, NVDA, GOOGL, AMZN</div></div>""",
        unsafe_allow_html=True,
    )