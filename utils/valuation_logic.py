import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf

from utils.fx import to_usd_multipliers


def calculate_automatic_valuation(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)

        # --- Currency conversion multipliers (1.0 each for US stocks) ---
        fx = to_usd_multipliers(ticker)
        fcf_to_usd = fx.get("fcf_to_usd", 1.0) or 1.0
        price_to_usd = fx.get("price_to_usd", 1.0) or 1.0

        income_stmt = ticker.financials
        shares_outstanding = ticker.info.get("sharesOutstanding")
        if not shares_outstanding:
            return None
        cash_flow = ticker.cashflow
        fcf_history = cash_flow.loc['Free Cash Flow'] if 'Free Cash Flow' in cash_flow.index else None
        if fcf_history is None or len(fcf_history) == 0:
            return None
        info = ticker.info
        financials = ticker.financials
        balance_sheet = ticker.balance_sheet
        cashflow = ticker.cashflow

        total_revenue = income_stmt.loc["Total Revenue"].sort_index()
        Rev_Recent = total_revenue.iloc[-1]
        Rev_minus1 = total_revenue.iloc[-2]
        Rev_minus2 = total_revenue.iloc[-3]
        Rev_minus3 = total_revenue.iloc[-4] if len(total_revenue) >= 4 else total_revenue.iloc[0]
        Rev_growth_rate01 = (Rev_Recent - Rev_minus1) / Rev_minus1
        Rev_growth_rate12 = (Rev_minus1 - Rev_minus2) / Rev_minus2
        Rev_growth_rate23 = (Rev_minus2 - Rev_minus3) / Rev_minus3
        Rev_Simple_Growth = (Rev_growth_rate01 + Rev_growth_rate12 + Rev_growth_rate23) / 3
        Rev_Compounded_average = ((Rev_Recent / Rev_minus3) ** (1/3) - 1)
        Rev_growth_historical = (Rev_Simple_Growth + Rev_Compounded_average) / 2

        try:
            rev_est = ticker.get_revenue_estimate()
            g0 = rev_est.loc["0y", "growth"]
            g1 = rev_est.loc["+1y", "growth"]
            def to_float_growth(x):
                if isinstance(x, str):
                    return float(x.strip('%')) / 100
                return float(x)
            g0 = to_float_growth(g0)
            g1 = to_float_growth(g1)
            Rev_future_avg_growth = (g0 + g1) / 2
        except:
            Rev_future_avg_growth = Rev_growth_historical

        Expected_growth_rate = (Rev_future_avg_growth + Rev_growth_historical) / 2
        g = Expected_growth_rate

        try:
            treasury = yf.Ticker("^TNX")
            risk_free_rate = treasury.info['regularMarketPrice'] / 100
        except Exception:
            risk_free_rate = 0.043

        market_cap = info.get('marketCap', 0)
        if market_cap >= 2_000_000_000_000:
            beta = 1.05
        elif market_cap >= 300_000_000_000:
            beta = 1.2
        elif market_cap >= 10_000_000_000:
            beta = 1.3
        elif market_cap >= 300_000_000:
            beta = 1.35
        else:
            beta = 1.45
        equity_risk_premium = 0.035
        market_return = risk_free_rate + equity_risk_premium
        r = risk_free_rate + beta * (market_return - risk_free_rate)

        # FCF converted to USD
        FCF_N = fcf_history.iloc[0] * 1.05 * fcf_to_usd
        terminal_growth_rate = 0.03
        growth_rates = []
        for year in range(1, 11):
            if year <= 3:
                blended_g = Rev_future_avg_growth
            else:
                blend_factor = (10 - year) / 7
                blended_g = g * blend_factor + terminal_growth_rate * (1 - blend_factor)
            growth_rates.append(blended_g)

        CV1  = FCF_N * (1 + growth_rates[0])
        CV2  = CV1  * (1 + growth_rates[1])
        CV3  = CV2  * (1 + growth_rates[2])
        CV4  = CV3  * (1 + growth_rates[3])
        CV5  = CV4  * (1 + growth_rates[4])
        CV6  = CV5  * (1 + growth_rates[5])
        CV7  = CV6  * (1 + growth_rates[6])
        CV8  = CV7  * (1 + growth_rates[7])
        CV9  = CV8  * (1 + growth_rates[8])
        CV10 = CV9  * (1 + growth_rates[9])

        EBITDA_at_year_N = (info.get('ebitda', 0) or 0) * fcf_to_usd
        perpetual_g = 0.03
        exit_multiple = 10.0
        number_of_years_TV = 10

        if r > perpetual_g:
            TV_gordon = CV10 * (1 + perpetual_g) / (r - perpetual_g)
            PV_TV_gordon = TV_gordon / ((1 + r) ** number_of_years_TV)
        else:
            PV_TV_gordon = 0

        if EBITDA_at_year_N and EBITDA_at_year_N > 0:
            TV_multiple = EBITDA_at_year_N * exit_multiple
            PV_TV_multiple = TV_multiple / ((1 + r) ** number_of_years_TV)
        else:
            PV_TV_multiple = 0

        # market cap is reported in trading currency -> convert to USD
        market_cap_usd = market_cap * price_to_usd if market_cap > 0 else 0
        market_cap_buffer = market_cap_usd / 10 if market_cap_usd > 0 else 0
        PV_TV = (PV_TV_multiple + PV_TV_gordon + market_cap_buffer) / 2 if (PV_TV_multiple + PV_TV_gordon) > 0 else 0

        DCF = (CV1/(1+r) + CV2/((1+r)**2) + CV3/((1+r)**3) + CV4/((1+r)**4) +
               CV5/((1+r)**5) + CV6/((1+r)**6) + CV7/((1+r)**7) + CV8/((1+r)**8) +
               CV9/((1+r)**9) + CV10/((1+r)**10) + PV_TV)
        DCF_Per_Share = DCF / shares_outstanding

        def check_ddm_conditions(ticker_obj):
            try:
                info_ = ticker_obj.info
                divs = ticker_obj.dividends
                sector = info_.get('sector', '').lower()
                DDM_mature_sectors = ['utilities','real estate','consumer staples',
                                      'communication services','financial services','healthcare','energy']
                DDM_is_mature_sector = any(s in sector for s in DDM_mature_sectors)
                DDM_dividend_rate = info_.get('dividendRate', 0)
                DDM_has_dividend = DDM_dividend_rate > 0
                DDM_history_length = len(divs)
                DDM_has_history = DDM_history_length >= 20
                DDM_price = info_.get('currentPrice', info_.get('regularMarketPrice', 1))
                DDM_yield = (DDM_dividend_rate / DDM_price) if DDM_price > 0 else 0
                DDM_high_yield = DDM_yield >= 0.025
                DDM_payout_ratio = info_.get('payoutRatio', 0) or 0
                DDM_max_payout = 3.0 if 'real estate' in sector else 1.0
                DDM_good_payout = 0.30 <= DDM_payout_ratio <= DDM_max_payout
                DDM_has_earnings = info_.get('trailingEps', 0) > 0
                DDM_all = (DDM_has_dividend and DDM_has_history and DDM_high_yield and
                           DDM_good_payout and DDM_has_earnings and DDM_is_mature_sector)
                return DDM_all, {}
            except:
                return False, {}

        DDM_is_eligible, _ = check_ddm_conditions(ticker)
        DDM_intrinsic_value = None
        DDM_is_used = False
        if DDM_is_eligible:
            try:
                DDM_current_dividend = (info.get('dividendRate', 0) or 0) * price_to_usd
                if DDM_current_dividend > 0 and r > g:
                    DDM_next_dividend = DDM_current_dividend * (1 + g)
                    DDM_intrinsic_value = DDM_next_dividend / (r - g)
                    DDM_is_used = True
            except:
                DDM_is_used = False

        intrinsic_value = (DDM_intrinsic_value + DCF_Per_Share) / 2 if DDM_is_used else DCF_Per_Share

        ebitda_margin = (financials.loc['EBITDA'].iloc[0] / financials.loc['Total Revenue'].iloc[0]) * 100
        if ebitda_margin > 30:   mult_ebitda = 1.2
        elif ebitda_margin > 20: mult_ebitda = 1.1
        elif ebitda_margin > 10: mult_ebitda = 1.05
        elif ebitda_margin > 5:  mult_ebitda = 1.00
        else:                    mult_ebitda = 0.95

        de_ratio = balance_sheet.loc['Total Debt'].iloc[0] / balance_sheet.loc['Stockholders Equity'].iloc[0]
        if de_ratio < 0.5:   mult_de = 1.1
        elif de_ratio < 1.0: mult_de = 1.05
        elif de_ratio < 1.5: mult_de = 1.00
        elif de_ratio < 2.0: mult_de = 0.96
        else:                mult_de = 0.92

        ocf = cashflow.loc['Operating Cash Flow'].iloc[0]
        capex = abs(cashflow.loc['Capital Expenditure'].iloc[0])
        capex_ratio = ocf / capex if capex > 0 else 0
        if capex_ratio > 2.5:   mult_capex = 1.1
        elif capex_ratio > 2.0: mult_capex = 1.05
        elif capex_ratio > 1.5: mult_capex = 1.00
        elif capex_ratio > 1.0: mult_capex = 0.97
        else:                   mult_capex = 0.93

        roe = (financials.loc['Net Income'].iloc[0] / balance_sheet.loc['Stockholders Equity'].iloc[0]) * 100
        if roe > 20:   mult_roe = 1.1
        elif roe > 15: mult_roe = 1.05
        elif roe > 10: mult_roe = 1.00
        elif roe > 5:  mult_roe = 0.96
        else:          mult_roe = 0.92

        current_ratio = balance_sheet.loc['Current Assets'].iloc[0] / balance_sheet.loc['Current Liabilities'].iloc[0]
        if current_ratio > 2.0:   mult_current = 1.15
        elif current_ratio > 1.5: mult_current = 1.05
        elif current_ratio > 1.2: mult_current = 1.00
        elif current_ratio > 1.0: mult_current = 0.96
        else:                     mult_current = 0.90

        composite = (mult_ebitda + mult_de + mult_capex + mult_roe + mult_current) / 5
        adjusted_value = intrinsic_value * composite

        # current price converted to USD
        raw_price = info.get('currentPrice', info.get('regularMarketPrice', 0)) or 0
        current_price = raw_price * price_to_usd
        upside = ((adjusted_value - current_price) / current_price * 100) if current_price > 0 else 0

        return {
            'ticker': ticker_symbol, 'current_price': current_price,
            'rev_growth_historical': Rev_growth_historical * 100,
            'rev_growth_analyst': Rev_future_avg_growth * 100,
            'expected_growth_rate': g * 100,
            'risk_free_rate': risk_free_rate * 100, 'beta': beta, 'discount_rate': r * 100,
            'fcf_current': FCF_N,
            'fcf_y1': CV1, 'fcf_y2': CV2, 'fcf_y3': CV3, 'fcf_y4': CV4, 'fcf_y5': CV5,
            'fcf_y6': CV6, 'fcf_y7': CV7, 'fcf_y8': CV8, 'fcf_y9': CV9, 'fcf_y10': CV10,
            'pv_tv_gordon': PV_TV_gordon, 'pv_tv_multiple': PV_TV_multiple, 'pv_tv_final': PV_TV,
            'dcf_total': DCF, 'dcf_per_share': DCF_Per_Share,
            'ddm_per_share': DDM_intrinsic_value, 'ddm_is_used': DDM_is_used,
            'base_value': intrinsic_value,
            'ebitda_margin': ebitda_margin, 'mult_ebitda': mult_ebitda,
            'de_ratio': de_ratio, 'mult_de': mult_de,
            'capex_ratio': capex_ratio, 'mult_capex': mult_capex,
            'roe': roe, 'mult_roe': mult_roe,
            'current_ratio': current_ratio, 'mult_current': mult_current,
            'composite_multiplier': composite, 'adjusted_value': adjusted_value,
            'upside': upside, 'market_cap': market_cap,
            'shares_outstanding': shares_outstanding,
            'is_foreign': fx.get("is_foreign", False),
            'reporting_ccy': fx.get("reporting", "USD"),
            'trading_ccy': fx.get("trading", "USD"),
        }
    except Exception:
        return None


def calculate_manual_valuation(ticker_symbol, auto_result,
                                cf1_growth, cf2_growth, cf3_growth, cf4_growth, cf5_growth,
                                cf6_growth, cf7_growth, cf8_growth, cf9_growth, cf10_growth,
                                perpetual_growth, beta_multiplier, risk_free_rate, multiplier):
    try:
        stock = yf.Ticker(ticker_symbol)
        shares_outstanding = stock.info.get("sharesOutstanding")
        if not shares_outstanding:
            return None, "Could not retrieve shares outstanding."
        info = stock.info
        ar = auto_result

        fx = to_usd_multipliers(stock)
        fcf_to_usd = fx.get("fcf_to_usd", 1.0) or 1.0
        price_to_usd = fx.get("price_to_usd", 1.0) or 1.0

        pg  = perpetual_growth / 100
        bm  = beta_multiplier
        rsg = risk_free_rate / 100
        m   = multiplier
        cg  = [v / 100 for v in [cf1_growth, cf2_growth, cf3_growth, cf4_growth, cf5_growth,
                                   cf6_growth, cf7_growth, cf8_growth, cf9_growth, cf10_growth]]

        # ar['fcf_current'] is already in USD from the auto valuation
        M_FCF_N = ar['fcf_current']
        cvs = [M_FCF_N]
        for gr in cg:
            cvs.append(cvs[-1] * (1 + gr))
        cvs = cvs[1:]

        equity_risk_premium = 0.035
        market_return = rsg + equity_risk_premium
        r = rsg + bm * (market_return - rsg)

        EBITDA_at_year_N = (info.get('ebitda', 0) or 0) * fcf_to_usd
        exit_multiple = 10.0

        PV_TV_gordon = cvs[-1] * (1 + pg) / (r - pg) / ((1 + r) ** 10) if r > pg else 0
        PV_TV_multiple = (EBITDA_at_year_N * exit_multiple / ((1 + r) ** 10)) if EBITDA_at_year_N and EBITDA_at_year_N > 0 else 0
        market_cap = (info.get('marketCap', 0) or 0) * price_to_usd
        market_cap_buffer = market_cap / 10 if market_cap > 0 else 0
        PV_TV = (PV_TV_multiple + PV_TV_gordon + market_cap_buffer) / 2 if (PV_TV_multiple + PV_TV_gordon) > 0 else 0

        manual_dcf = sum(cvs[i] / ((1 + r) ** (i + 1)) for i in range(10)) + PV_TV
        m_dcf_pershare = (manual_dcf * m) / shares_outstanding
        raw_price = info.get('currentPrice', info.get('regularMarketPrice', 0)) or 0
        current_price = raw_price * price_to_usd
        upside = ((m_dcf_pershare - current_price) / current_price * 100) if current_price > 0 else 0

        return {
            'm_dcf': m_dcf_pershare, 'current_price': current_price, 'upside': upside,
            'cg': cg, 'multiplier': m, 'risk_free_rate': rsg, 'beta': bm,
            'M_FCF_N': M_FCF_N, 'cvs': cvs,
            'discount_rate': r, 'Gordon_TV': PV_TV_gordon,
            'Multiple_TV': PV_TV_multiple, 'TV': PV_TV,
            'shares_outstanding': shares_outstanding,
        }, None
    except Exception as e:
        return None, str(e)