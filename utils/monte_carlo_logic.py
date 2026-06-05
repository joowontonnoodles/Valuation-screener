"""utils/monte_carlo_logic.py - Monte Carlo simulation engine for stock valuation."""
import numpy as np


def run_monte_carlo(ar, n_sims=5000,
                    growth_stdev=2.5,
                    wacc_stdev=1.0,
                    perp_growth_mean=3.0,
                    perp_growth_stdev=0.5,
                    multiplier_stdev=0.10,
                    fcf_shock_stdev=5.0,
                    seed=42):
    """
    Returns dict with:
      - iv_samples (per-share intrinsic value distribution)
      - mc_samples (total enterprise value / market cap distribution)
      - percentiles for both
      - probabilities computed against per-share current price
      - tornado sensitivity in per-share dollars
    """
    rng = np.random.default_rng(seed)

    g_mean = float(ar.get("expected_growth_rate", 8.0))
    r_mean = float(ar.get("discount_rate", 9.0))
    mult_mean = float(ar.get("composite_multiplier", 1.0))
    fcf_base = float(ar.get("fcf_current", 0.0))
    shares = float(ar.get("shares_outstanding", 0.0))
    current_price = float(ar.get("current_price", 0.0))

    if shares <= 0 or fcf_base <= 0:
        return None

    g_samples = rng.normal(g_mean, growth_stdev, n_sims) / 100.0
    r_samples = rng.normal(r_mean, wacc_stdev, n_sims) / 100.0
    pg_samples = rng.normal(perp_growth_mean, perp_growth_stdev, n_sims) / 100.0
    mult_samples = rng.normal(mult_mean, multiplier_stdev, n_sims)
    shock_samples = rng.normal(0.0, fcf_shock_stdev, n_sims) / 100.0

    r_samples = np.clip(r_samples, 0.03, 0.25)
    pg_samples = np.clip(pg_samples, 0.005, 0.05)
    mult_samples = np.clip(mult_samples, 0.3, 2.5)
    pg_samples = np.minimum(pg_samples, r_samples - 0.005)

    enterprise_samples = np.zeros(n_sims)

    for i in range(n_sims):
        g, r, pg = g_samples[i], r_samples[i], pg_samples[i]
        mult, shock = mult_samples[i], shock_samples[i]

        fcf = fcf_base * (1.0 + shock)
        pv_fcf = 0.0
        last_fcf = fcf
        for year in range(1, 11):
            decay = 1.0 if year <= 3 else (0.85 if year <= 7 else 0.6)
            last_fcf = last_fcf * (1.0 + g * decay)
            pv_fcf += last_fcf / ((1.0 + r) ** year)

        tv = (last_fcf * (1.0 + pg)) / (r - pg)
        pv_tv = tv / ((1.0 + r) ** 10)

        enterprise_samples[i] = (pv_fcf + pv_tv) * mult

    iv_samples = enterprise_samples / shares  # per-share

    mask = np.isfinite(iv_samples) & (iv_samples > 0)
    iv_samples = iv_samples[mask]
    enterprise_samples = enterprise_samples[mask]

    if len(iv_samples) == 0:
        return None

    p10, p25, p50, p75, p90 = np.percentile(iv_samples, [10, 25, 50, 75, 90])
    mp10, mp25, mp50, mp75, mp90 = np.percentile(enterprise_samples, [10, 25, 50, 75, 90])

    prob_upside = float(np.mean(iv_samples > current_price)) * 100.0
    prob_double = float(np.mean(iv_samples > current_price * 2.0)) * 100.0
    prob_loss = float(np.mean(iv_samples < current_price * 0.8)) * 100.0

    tornado = _tornado_sensitivity(ar, shares)

    return {
        # Per-share distribution (USED for probabilities and the main histogram)
        "iv_samples": iv_samples,
        "p10": float(p10), "p25": float(p25), "p50": float(p50),
        "p75": float(p75), "p90": float(p90),
        "mean": float(np.mean(iv_samples)),
        "std": float(np.std(iv_samples)),

        # Enterprise / market-cap distribution
        "mc_samples": enterprise_samples,
        "mc_p10": float(mp10), "mc_p25": float(mp25), "mc_p50": float(mp50),
        "mc_p75": float(mp75), "mc_p90": float(mp90),
        "mc_mean": float(np.mean(enterprise_samples)),
        "mc_std": float(np.std(enterprise_samples)),

        "n_sims": int(len(iv_samples)),
        "current_price": current_price,
        "current_market_cap": current_price * shares,
        "shares_outstanding": shares,
        "auto_iv": float(ar.get("adjusted_value", 0.0)),

        "prob_upside": prob_upside,
        "prob_double": prob_double,
        "prob_loss": prob_loss,

        "tornado": tornado,
        "params": {
            "n_sims": n_sims,
            "growth_mean": g_mean, "growth_stdev": growth_stdev,
            "wacc_mean": r_mean, "wacc_stdev": wacc_stdev,
            "perp_growth_mean": perp_growth_mean,
            "perp_growth_stdev": perp_growth_stdev,
            "multiplier_mean": mult_mean,
            "multiplier_stdev": multiplier_stdev,
            "fcf_shock_stdev": fcf_shock_stdev,
            "seed": seed,
        },
    }


def _single_iv(fcf_base, shares, g_pct, r_pct, pg_pct, mult, shock_pct):
    """Per-share IV used for tornado sensitivity."""
    g = g_pct / 100.0
    r = max(r_pct / 100.0, 0.03)
    pg = min(pg_pct / 100.0, r - 0.005)
    fcf = fcf_base * (1.0 + shock_pct / 100.0)
    pv_fcf = 0.0
    last_fcf = fcf
    for year in range(1, 11):
        decay = 1.0 if year <= 3 else (0.85 if year <= 7 else 0.6)
        last_fcf = last_fcf * (1.0 + g * decay)
        pv_fcf += last_fcf / ((1.0 + r) ** year)
    tv = (last_fcf * (1.0 + pg)) / (r - pg)
    pv_tv = tv / ((1.0 + r) ** 10)
    return ((pv_fcf + pv_tv) * mult) / shares


def _tornado_sensitivity(ar, shares):
    fcf_base = float(ar.get("fcf_current", 0.0))
    g = float(ar.get("expected_growth_rate", 8.0))
    r = float(ar.get("discount_rate", 9.0))
    mult = float(ar.get("composite_multiplier", 1.0))

    base_iv = _single_iv(fcf_base, shares, g, r, 3.0, mult, 0.0)

    swings = [
        ("Growth Rate",        _single_iv(fcf_base, shares, g - 2.5, r, 3.0, mult, 0.0),
                                _single_iv(fcf_base, shares, g + 2.5, r, 3.0, mult, 0.0)),
        ("Discount Rate",      _single_iv(fcf_base, shares, g, r + 1.0, 3.0, mult, 0.0),
                                _single_iv(fcf_base, shares, g, r - 1.0, 3.0, mult, 0.0)),
        ("Perpetual Growth",   _single_iv(fcf_base, shares, g, r, 2.5, mult, 0.0),
                                _single_iv(fcf_base, shares, g, r, 3.5, mult, 0.0)),
        ("Quality Multiplier", _single_iv(fcf_base, shares, g, r, 3.0, mult - 0.10, 0.0),
                                _single_iv(fcf_base, shares, g, r, 3.0, mult + 0.10, 0.0)),
        ("FCF Shock (Y1)",     _single_iv(fcf_base, shares, g, r, 3.0, mult, -5.0),
                                _single_iv(fcf_base, shares, g, r, 3.0, mult, 5.0)),
    ]

    out = []
    for name, low, high in swings:
        out.append({
            "variable": name,
            "low": float(low), "high": float(high),
            "swing": float(abs(high - low)), "base": float(base_iv),
        })
    out.sort(key=lambda d: d["swing"], reverse=True)
    return out