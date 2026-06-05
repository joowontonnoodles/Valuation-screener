"""pages/1_screener.py - Screener with NaN filter, outlier filter, dark themed table, intrinsic value."""
import sys
import os
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_extras.let_it_rain import rain

from utils.screener_logic import build_universe, download_prices, get_top25_fallers, rank_by_undervalue
from utils.ai_helper import get_ai_explanation, build_screener_prompt
from theme import (
    inject_global_css,
    inject_keyboard_sound,
    inject_audio_autoplay_helper,
    render_navbar,
    sidebar_audio_player,
    THEME,
)

# ---- Outlier rules ----
EXTREME_UPSIDE_LIMIT = 2000.0
SUSPICIOUS_UPSIDE = 200.0
EXTREME_DOWNSIDE_LIMIT = -95.0

# ---- Columns that must have valid numeric values ----
REQUIRED_NUMERIC_FIELDS = [
    "Price",
    "Upside Base",
    "Upside Bull",
    "Upside Bear",
    "Avg Fall (1-6M)",
]

st.set_page_config(
    page_title="Stock Screener | The Valuation Tool",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()
inject_keyboard_sound()
inject_audio_autoplay_helper()

for k, v in {
    "auto_result": None, "auto_ticker": "", "screener_results": None,
    "manual_result": None, "screener_ai_explanations": {},
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

render_navbar("Undervalued Stock Screener")

st.markdown('<div class="section-header">Stock Screener</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-sub">Scans every large-cap stock (>$100B), finds the 25 biggest fallers '
    'over 1M and 6M, then runs base / bull / bear DCF on each.</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

ci1, ci2, ci3 = st.columns(3)
with ci1: st.info("Runtime: ~3-5 minutes")
with ci2: st.info("Bull: Growth x1.3 | WACC -1%")
with ci3: st.info("Bear: Growth x0.6 | WACC +1.5%")
st.markdown("")

run_col, _ = st.columns([1, 4])
with run_col:
    run_clicked = st.button("Run Screener", key="run_screener")

if run_clicked:
    st.session_state.screener_results = None
    st.session_state.screener_ai_explanations = {}
    progress_bar = st.progress(0, text="Starting...")
    with st.status("Running screener pipeline...", expanded=True) as status:
        st.write("**Step 1/5** - Building universe of large-cap stocks...")
        progress_bar.progress(5, text="Building universe...")
        try:
            universe = build_universe()
            st.write(f"Found **{len(universe)}** companies with market cap > $100B")
        except Exception as e:
            st.error(f"Failed: {e}"); st.stop()

        st.write("**Step 2/5** - Downloading 6 months of price history...")
        progress_bar.progress(15, text="Downloading prices...")
        try:
            closes = download_prices(universe["Symbol"].tolist())
            st.write(f"{closes.shape[1]} tickers x {closes.shape[0]} days")
        except Exception as e:
            st.error(f"Price download failed: {e}"); st.stop()

        st.write("**Step 3/5** - Identifying 25 biggest fallers...")
        progress_bar.progress(30, text="Calculating returns...")
        fallers = get_top25_fallers(closes)
        st.write(f"Worst faller: **{fallers.iloc[0]['Ticker']}** ({fallers.iloc[0]['Avg Fall']:.1f}%)")

        st.write(f"**Steps 4+5/5** - Fetching financials and running DCF for {len(fallers)} stocks...")
        prog_placeholder = st.empty()

        def update_progress(i, total, ticker, name):
            pct = 30 + int((i / max(total, 1)) * 65)
            progress_bar.progress(pct, text=f"Analysing {ticker} ({i+1}/{total})")
            prog_placeholder.markdown(f"Processing: **{ticker}** - {name}")

        results = rank_by_undervalue(fallers, universe, progress_callback=update_progress)
        progress_bar.progress(100, text="Complete!")
        status.update(label="Screener complete", state="complete")

    st.session_state.screener_results = results
    rain(emoji="$", font_size=22, falling_speed=7, animation_length=1)
    st.toast(f"Screener complete - {len(results)} stocks ranked")


def is_bad_number(v):
    """Return True if v is None, NaN, inf, or non-numeric."""
    if v is None:
        return True
    try:
        f = float(v)
    except (TypeError, ValueError):
        return True
    if math.isnan(f) or math.isinf(f):
        return True
    return False


def get_intrinsic_value(r):
    for k in ("Intrinsic Value", "intrinsic_value", "Adjusted Value", "adjusted_value",
              "IV Base", "Base IV", "Intrinsic Base", "intrinsic_base", "base_iv", "IV"):
        v = r.get(k)
        if not is_bad_number(v):
            vf = float(v)
            if vf > 0:
                return vf
    price = r.get("Price")
    upside = r.get("Upside Base")
    if not is_bad_number(price) and not is_bad_number(upside):
        p = float(price)
        if p > 0:
            return p * (1 + float(upside) / 100.0)
    return None


def render_dark_table(rows):
    def fmt_pct(v, flag=False):
        if is_bad_number(v):
            return "<span class='neg'>—</span>"
        v = float(v)
        cls = "pos" if v > 0 else ("neg" if v < 0 else "")
        sign = "+" if v > 0 else ""
        flag_html = " ⚠️" if flag else ""
        return f"<span class='{cls}'>{sign}{v:.1f}%{flag_html}</span>"

    def fmt_money(v):
        if is_bad_number(v):
            return "—"
        return f"${float(v):,.2f}"

    def fmt_text(v):
        if v is None:
            return "—"
        s = str(v).strip()
        if s.lower() in ("nan", "none", "", "inf", "-inf"):
            return "—"
        return s

    body = []
    for r in rows:
        u = r.get("Upside Base")
        suspicious = (not is_bad_number(u) and abs(float(u)) > SUSPICIOUS_UPSIDE)
        row_bg = "background:rgba(255,193,7,0.08);" if suspicious else ""
        iv = r.get("Intrinsic Value")
        body.append(f"""
        <tr style="{row_bg}">
            <td style="color:{THEME['primary']};font-weight:700;text-align:center;">{r.get('Rank','')}</td>
            <td style="font-weight:700;">{r.get('Ticker','')}</td>
            <td>{str(r.get('Company',''))[:30]}</td>
            <td style="text-align:right;">{fmt_money(r.get('Price'))}</td>
            <td style="text-align:right;font-weight:600;">{fmt_money(iv)}</td>
            <td style="text-align:right;">{fmt_pct(r.get('Upside Base'), suspicious)}</td>
            <td style="text-align:right;">{fmt_pct(r.get('Upside Bull'))}</td>
            <td style="text-align:right;">{fmt_pct(r.get('Upside Bear'))}</td>
            <td style="text-align:right;">{fmt_pct(r.get('Avg Fall (1-6M)'))}</td>
            <td style="text-align:right;color:{THEME['muted']};">{fmt_text(r.get('Growth Rate'))}</td>
            <td style="text-align:right;color:{THEME['muted']};">{fmt_text(r.get('Discount Rate'))}</td>
        </tr>""")

    st.markdown(
        f"""
        <table class="screener-table">
            <thead>
                <tr>
                    <th style="text-align:center;">Rank</th>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th style="text-align:right;">Price</th>
                    <th style="text-align:right;">Intrinsic Value</th>
                    <th style="text-align:right;">Upside Base</th>
                    <th style="text-align:right;">Upside Bull</th>
                    <th style="text-align:right;">Upside Bear</th>
                    <th style="text-align:right;">Avg Fall (1-6M)</th>
                    <th style="text-align:right;">Growth</th>
                    <th style="text-align:right;">WACC</th>
                </tr>
            </thead>
            <tbody>{''.join(body)}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


if st.session_state.screener_results:
    raw_results = st.session_state.screener_results

    clean, dropped = [], []
    for r in raw_results:
        ticker = r.get("Ticker", "?")

        # 1. Reject rows missing or NaN in any required numeric field
        bad_fields = [f for f in REQUIRED_NUMERIC_FIELDS if is_bad_number(r.get(f))]
        if bad_fields:
            dropped.append((ticker, f"NaN in {', '.join(bad_fields)}"))
            continue

        u = float(r.get("Upside Base"))

        # 2. Outlier filter
        if u > EXTREME_UPSIDE_LIMIT:
            dropped.append((ticker, f"+{u:.0f}%"))
            continue
        if u < EXTREME_DOWNSIDE_LIMIT:
            dropped.append((ticker, f"{u:.0f}%"))
            continue

        # 3. Compute IV; drop if it can't be computed cleanly
        iv = get_intrinsic_value(r)
        if is_bad_number(iv) or iv is None or iv <= 0:
            dropped.append((ticker, "invalid intrinsic value"))
            continue
        r["Intrinsic Value"] = round(float(iv), 2)

        clean.append(r)

    for i, r in enumerate(clean, start=1):
        r["Rank"] = i

    results = clean
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="section-header">Results - {datetime.today().strftime("%d %b %Y")}</div>',
        unsafe_allow_html=True,
    )

    if dropped:
        names = ", ".join([f"{t} ({reason})" for t, reason in dropped[:6]])
        more = f" and {len(dropped)-6} more" if len(dropped) > 6 else ""
        st.error(
            f"Excluded {len(dropped)} stock(s) due to NaN values or extreme upside "
            f"(|upside| > {EXTREME_UPSIDE_LIMIT:.0f}% or downside < {EXTREME_DOWNSIDE_LIMIT:.0f}%): "
            f"{names}{more}."
        )

    st.warning(
        f"⚠️ Disclaimer: Highlighted rows have unusually high upside (>{SUSPICIOUS_UPSIDE:.0f}%). "
        "Always verify the input data and assumptions before trusting these valuations."
    )

    mc1, mc3, mc4 = st.columns(3)
    with mc1: st.metric("Stocks Analysed", len(results))
    with mc3: st.metric("Top Pick",        results[0]["Ticker"] if results else "-")
    with mc4: st.metric("Best Upside",     f"+{results[0]['Upside Base']:.1f}%" if results else "-")
    st.markdown("")

    if results:
        render_dark_table(results)

        st.markdown("")
        st.markdown(
            f"<div style='color:{THEME['muted']};font-size:0.9rem;'>Select a ticker for AI analysis:</div>",
            unsafe_allow_html=True,
        )
        tickers = [r["Ticker"] for r in results]
        sel = st.selectbox("Ticker", tickers, key="screener_select_ticker", label_visibility="collapsed")
        sel_row = next((r for r in results if r["Ticker"] == sel), None)

        if sel_row:
            ec1, ec2 = st.columns([3, 1])
            with ec1:
                st.markdown(f"### Selected: **{sel_row['Ticker']}** - {sel_row.get('Company','')}")
            with ec2:
                st.markdown('<div class="ai-mini-btn">', unsafe_allow_html=True)
                if st.button(f"AI Explain {sel_row['Ticker']}", key=f"ai_sel_{sel_row['Ticker']}"):
                    with st.spinner(f"Analysing {sel_row['Ticker']}..."):
                        st.session_state.screener_ai_explanations[sel_row["Ticker"]] = get_ai_explanation(
                            build_screener_prompt(sel_row)
                        )
                st.markdown('</div>', unsafe_allow_html=True)

            if sel_row["Ticker"] in st.session_state.screener_ai_explanations:
                with st.container(border=True):
                    st.markdown(f"#### AI Analysis - {sel_row['Ticker']}")
                    st.markdown(st.session_state.screener_ai_explanations[sel_row["Ticker"]])

        st.markdown("")
        df = pd.DataFrame(results)
        dl_col, _ = st.columns([1, 4])
        with dl_col:
            st.download_button(
                "Download CSV",
                df.to_csv(index=False),
                file_name=f"screener_{datetime.today().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
            )
    else:
        st.info("All scanned stocks were filtered out as outliers or had NaN values. Try re-running the screener.")
else:
    st.markdown(
        f"""<div style="text-align:center;padding:4rem 2rem;">
        <div style="font-size:1.1rem;font-weight:600;color:{THEME['muted']};">No results yet</div>
        <div style="font-size:0.9rem;color:{THEME['faint']};margin-top:0.5rem;">
        Press <b>Run Screener</b> to start the pipeline</div></div>""",
        unsafe_allow_html=True,
    )