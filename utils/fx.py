"""utils/fx.py - Currency conversion for non-US tickers."""
from functools import lru_cache
import yfinance as yf

CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥",
    "HKD": "HK$", "KRW": "₩", "INR": "₹", "CAD": "C$", "AUD": "A$",
    "CHF": "CHF", "SEK": "kr", "NOK": "kr", "DKK": "kr", "SGD": "S$",
    "TWD": "NT$", "BRL": "R$", "MXN": "Mex$", "ZAR": "R",
}


@lru_cache(maxsize=64)
def get_fx_rate(from_ccy: str, to_ccy: str = "USD") -> float:
    if not from_ccy or not to_ccy:
        return 1.0
    from_ccy, to_ccy = from_ccy.upper(), to_ccy.upper()
    if from_ccy == to_ccy:
        return 1.0
    pair = f"{from_ccy}{to_ccy}=X"
    try:
        fx = yf.Ticker(pair)
        hist = fx.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        info = fx.info or {}
        rate = info.get("regularMarketPrice") or info.get("previousClose")
        return float(rate) if rate else 1.0
    except Exception:
        return 1.0


def detect_currencies(ticker_obj) -> dict:
    try:
        info = ticker_obj.info or {}
    except Exception:
        info = {}
    reporting = (info.get("financialCurrency") or "USD").upper()
    trading = (info.get("currency") or reporting).upper()
    return {
        "reporting": reporting,
        "trading": trading,
        "is_foreign": (reporting != "USD" or trading != "USD"),
    }


def to_usd_multipliers(ticker_obj) -> dict:
    ccy = detect_currencies(ticker_obj)
    fcf_mult = get_fx_rate(ccy["reporting"], "USD")
    price_mult = get_fx_rate(ccy["trading"], "USD")
    info = getattr(ticker_obj, "info", {}) or {}
    sym = (info.get("symbol", "") or "").upper()
    # London (.L) often quotes in pence; financialCurrency is GBP but price is GBp
    if info.get("currency", "").upper() == "GBP" and sym.endswith(".L"):
        price_mult = price_mult / 100.0
    return {**ccy, "fcf_to_usd": fcf_mult, "price_to_usd": price_mult}