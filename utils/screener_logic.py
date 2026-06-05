import warnings
warnings.filterwarnings("ignore")
import time
from io import StringIO
import numpy as np
import pandas as pd
import requests
import yfinance as yf

MARKET_CAP_THRESHOLD = 100e9
RISK_FREE_RATE = 0.043
TERMINAL_GROWTH = 0.025
TOP_N_FALLERS = 25
SCRAPE_URL = "https://stockanalysis.com/list/biggest-companies/"
SCRAPE_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BULL_GROWTH_MULT = 1.30
BULL_WACC_ADJUST = -0.01
BEAR_GROWTH_MULT = 0.60
BEAR_WACC_ADJUST = +0.015


def parse_market_cap(val):
    if isinstance(val, str):
        val = val.strip()
        if val.endswith("T"): return float(val[:-1]) * 1e12
        elif val.endswith("B"): return float(val[:-1]) * 1e9
    try: return float(val)
    except: return None


def build_universe():
    try:
        resp = requests.get(SCRAPE_URL, headers=SCRAPE_HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Could not fetch universe: {e}")
    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"Symbol": "Symbol", "Company Name": "Company", "Market Cap": "Market Cap"})
    df["MarketCapNum"] = df["Market Cap"].apply(parse_market_cap)
    universe = df[df["MarketCapNum"] >= MARKET_CAP_THRESHOLD][["Symbol", "Company", "MarketCapNum"]].copy()
    universe = universe.dropna(subset=["Symbol"])
    universe = universe[universe["Symbol"].str.len() <= 5]
    return universe.reset_index(drop=True)


def download_prices(tickers):
    raw = yf.download(tickers, period="6mo", auto_adjust=True, progress=False, threads=True)
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    return closes.dropna(axis=1, how="all")


def get_top25_fallers(closes):
    records = []
    for ticker in closes.columns:
        series = closes[ticker].dropna()
        if len(series) < 22: continue
        price_now = series.iloc[-1]
        ret_1m = (price_now - series.iloc[-22]) / series.iloc[-22]
        ret_6m = (price_now - series.iloc[0]) / series.iloc[0]
        composite = (ret_1m + ret_6m) / 2
        records.append({"Ticker": ticker, "1M Return": round(ret_1m*100,2),
                        "6M Return": round(ret_6m*100,2), "Avg Fall": round(composite*100,2),
                        "Price": round(float(price_now),2)})
    return pd.DataFrame(records).sort_values("Avg Fall").head(TOP_N_FALLERS).reset_index(drop=True)


def get_financials(ticker_symbol):
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        shares = info.get("sharesOutstanding")
        beta = info.get("beta") or 1.0
        market_cap = info.get("marketCap") or 0
        cf = t.cashflow
        fcf = None
        if cf is not None and not cf.empty:
            if "Free Cash Flow" in cf.index:
                fcf = float(cf.loc["Free Cash Flow"].iloc[0])
            elif "Operating Cash Flow" in cf.index and "Capital Expenditure" in cf.index:
                fcf = float(cf.loc["Operating Cash Flow"].iloc[0]) + float(cf.loc["Capital Expenditure"].iloc[0])
        bs = t.balance_sheet
        total_debt = float(bs.loc["Total Debt"].iloc[0]) if bs is not None and "Total Debt" in bs.index else 0
        cash = float(bs.loc["Cash And Cash Equivalents"].iloc[0]) if bs is not None and "Cash And Cash Equivalents" in bs.index else 0
        growth = info.get("earningsGrowth") or info.get("revenueGrowth") or 0.08
        return {"ticker": ticker_symbol, "current_price": current_price, "shares": shares,
                "beta": beta, "market_cap": market_cap, "fcf": fcf,
                "total_debt": total_debt, "cash": cash, "growth": growth}
    except: return None


def run_dcf(fcf, shares, total_debt, cash, growth_rate, wacc):
    if not fcf or fcf <= 0 or not shares or shares <= 0: return None
    fcf_proj = float(fcf)
    total_pv = 0.0
    for yr in range(1, 11):
        gr = growth_rate if yr <= 5 else growth_rate * 0.5
        fcf_proj *= (1 + gr)
        total_pv += fcf_proj / (1 + wacc) ** yr
    terminal_value = fcf_proj * (1 + TERMINAL_GROWTH) / (wacc - TERMINAL_GROWTH)
    pv_terminal = terminal_value / (1 + wacc) ** 10
    equity_value = (total_pv + pv_terminal) - total_debt + cash
    return round(equity_value / shares, 2)


def DCF_calculation(financials):
    if financials is None: return None, "Financials fetch failed"
    fcf = financials.get("fcf")
    shares = financials.get("shares")
    current_price = financials.get("current_price")
    beta = financials.get("beta") or 1.0
    market_cap = financials.get("market_cap") or 0
    total_debt = financials.get("total_debt") or 0
    cash = financials.get("cash") or 0
    growth = financials.get("growth") or 0.08
    if fcf is None or (isinstance(fcf, float) and np.isnan(fcf)) or fcf <= 0:
        return None, "Missing/negative FCF"
    if not shares or shares <= 0: return None, "Shares missing"
    if not current_price or current_price <= 0: return None, "Price missing"
    base_growth = min(max(float(growth), 0.02), 0.25)
    risk_premium = 0.045 if market_cap > 500e9 else 0.055
    base_wacc = max(RISK_FREE_RATE + beta * risk_premium, 0.06)
    bull_growth = min(base_growth * BULL_GROWTH_MULT, 0.30)
    bull_wacc = max(base_wacc + BULL_WACC_ADJUST, 0.05)
    bear_growth = max(base_growth * BEAR_GROWTH_MULT, 0.01)
    bear_wacc = base_wacc + BEAR_WACC_ADJUST
    iv_base = run_dcf(fcf, shares, total_debt, cash, base_growth, base_wacc)
    iv_bull = run_dcf(fcf, shares, total_debt, cash, bull_growth, bull_wacc)
    iv_bear = run_dcf(fcf, shares, total_debt, cash, bear_growth, bear_wacc)
    if iv_base is None: return None, "DCF returned None"
    def upside(iv):
        return round(((iv - current_price) / current_price) * 100, 1) if iv else None
    return {"current_price": round(current_price,2), "iv_base": iv_base, "upside_base": upside(iv_base),
            "iv_bull": iv_bull, "upside_bull": upside(iv_bull), "iv_bear": iv_bear,
            "upside_bear": upside(iv_bear), "wacc_pct": round(base_wacc*100,2),
            "growth_pct": round(base_growth*100,1)}, None


def rank_by_undervalue(fallers_df, universe_df, progress_callback=None):
    results = []
    company_map = dict(zip(universe_df["Symbol"], universe_df["Company"]))
    total = len(fallers_df)
    for i, row in fallers_df.iterrows():
        ticker = row["Ticker"]
        name = company_map.get(ticker, ticker)
        if progress_callback: progress_callback(i, total, ticker, name)
        financials = get_financials(ticker)
        dcf, err = DCF_calculation(financials)
        if dcf is None:
            time.sleep(0.2)
            continue
        results.append({"Rank": 0, "Ticker": ticker, "Company": name, "Price": dcf["current_price"],
                         "Base Case IV": dcf["iv_base"], "Bull Case IV": dcf["iv_bull"],
                         "Bear Case IV": dcf["iv_bear"], "Upside Base": dcf["upside_base"],
                         "Upside Bull": dcf["upside_bull"], "Upside Bear": dcf["upside_bear"],
                         "Avg Fall (1-6M)": row["Avg Fall"], "Growth Rate": dcf["growth_pct"],
                         "Discount Rate": dcf["wacc_pct"]})
        time.sleep(0.3)
    results.sort(key=lambda x: x["Upside Base"], reverse=True)
    for i, r in enumerate(results): r["Rank"] = i + 1
    return results