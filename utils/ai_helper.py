"""utils/ai_helper.py - AI explanation builder. Robust to OpenAI or OpenRouter keys."""
import os
import streamlit as st


def _get_secret(name):
    val = os.getenv(name)
    if val:
        return val
    try:
        return st.secrets.get(name, None)
    except Exception:
        return None


def _make_client():
    """Lazily build a client. Prefers OpenAI key, falls back to OpenRouter."""
    try:
        from openai import OpenAI
    except Exception:
        return None, None

    openai_key = _get_secret("OPENAI_API_KEY")
    if openai_key:
        try:
            return OpenAI(api_key=openai_key), "openai"
        except Exception:
            return None, None

    or_key = _get_secret("OPENROUTER_API_KEY")
    if or_key:
        try:
            return OpenAI(api_key=or_key, base_url="https://openrouter.ai/api/v1"), "openrouter"
        except Exception:
            return None, None

    return None, None


def get_ai_explanation(prompt, model=None, max_tokens=700):
    """Send a prompt to the LLM and return text. Returns a clear message if unconfigured."""
    client, provider = _make_client()
    if client is None:
        return ("AI explanation unavailable - no API key found. Set OPENAI_API_KEY or "
                "OPENROUTER_API_KEY in your environment or .streamlit/secrets.toml "
                "(and in the Streamlit Cloud 'Secrets' box when deployed).")

    if model is None:
        model = "gpt-4o-mini" if provider == "openai" else "meta-llama/llama-3.3-70b-instruct:free"

    try:
        kwargs = dict(
            model=model,
            messages=[
                {"role": "system",
                 "content": "You are a sharp, concise equity analyst. Use plain language. "
                            "Avoid hedging. 4-6 short paragraphs maximum."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.4,
        )
        if provider == "openrouter":
            kwargs["extra_headers"] = {
                "HTTP-Referer": "https://valuation-tool.local",
                "X-Title": "The Valuation Tool",
            }
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"AI request failed: {e}"


def build_auto_prompt(ar, ticker):
    return f"""Explain the automatic DCF + DDM valuation for {ticker}.

Current price: ${ar['current_price']:.2f}
Intrinsic value: ${ar['adjusted_value']:.2f}
Upside: {ar['upside']:.1f}%
Expected growth: {ar['expected_growth_rate']:.2f}%
Discount rate: {ar['discount_rate']:.2f}%
Beta: {ar['beta']:.2f}
Composite multiplier: x{ar['composite_multiplier']:.3f}
EBITDA margin: {ar['ebitda_margin']:.1f}%
ROE: {ar['roe']:.1f}%
Debt/Equity: {ar['de_ratio']:.2f}

Cover: 1) Why this growth rate, 2) Why this discount rate, 3) What the multiplier reflects,
4) Whether the stock looks under- or over-valued and the key risk to that thesis."""


def build_manual_prompt(mr, ar, ticker):
    return f"""Compare manual vs automatic valuation for {ticker}.

Auto IV: ${ar['adjusted_value']:.2f}
Manual IV: ${mr['m_dcf']:.2f}
Current price: ${mr['current_price']:.2f}
Manual upside: {mr['upside']:.1f}%
Manual discount rate: {mr['discount_rate']*100:.2f}%
Final multiplier: x{mr['multiplier']:.2f}

Explain what assumptions drove the difference and whether the manual case is more or less
defensible than the auto case."""


def build_screener_prompt(row):
    return f"""Quick analysis on screener pick: {row.get('Ticker')} - {row.get('Company','')}.

Price: ${row.get('Price'):.2f}
Intrinsic value: ${row.get('Intrinsic Value', 0):.2f}
Upside (base): {row.get('Upside Base'):.1f}%
Upside (bull): {row.get('Upside Bull'):.1f}%
Upside (bear): {row.get('Upside Bear'):.1f}%
Avg fall (1-6M): {row.get('Avg Fall (1-6M)'):.1f}%

In 4 short paragraphs: 1) why this stock fell, 2) is the upside real or a value trap,
3) the single biggest risk, 4) verdict."""


def build_monte_carlo_prompt(mc, ar, ticker):
    torn_top = mc["tornado"][0]["variable"] if mc.get("tornado") else "Growth Rate"
    return f"""Interpret a Monte Carlo simulation for {ticker}.

Current price: ${mc['current_price']:.2f}
Auto IV: ${mc['auto_iv']:.2f}
Simulations run: {mc['n_sims']:,}

Distribution of intrinsic values:
- P10 (bear):   ${mc['p10']:.2f}
- P25:          ${mc['p25']:.2f}
- P50 (median): ${mc['p50']:.2f}
- P75:          ${mc['p75']:.2f}
- P90 (bull):   ${mc['p90']:.2f}
- Mean:         ${mc['mean']:.2f}
- Stdev:        ${mc['std']:.2f}

Probabilities:
- P(IV > current price): {mc['prob_upside']:.1f}%
- P(IV > 2x current):    {mc['prob_double']:.1f}%
- P(IV < 80% current):   {mc['prob_loss']:.1f}%

Most sensitive variable in tornado: {torn_top}.

Explain in 4-5 short paragraphs:
1) What the distribution shape tells us about confidence in fair value.
2) Whether the probability of upside justifies a position.
3) The biggest source of valuation risk based on the tornado.
4) How wide the range is vs the auto point estimate, and what that implies."""