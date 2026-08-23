"""
Multi-Timeframe CPR Screener & Data Builder (Institutional Sniper Edition)
Computes Composite Quant Score (0-100), 30-day compression percentiles,
Proximity Guard, and exports high-conviction outputs.
"""

import urllib.request
import io
import json
import os
import datetime
import time
import numpy as np
import pandas as pd
import yfinance as yf

def get_liquid_nse_universe():
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    
    print("📥 Loading official Nifty 500 universe...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            df = pd.read_csv(io.StringIO(response.read().decode('utf-8')))
            stocks = []
            for _, r in df.iterrows():
                sym = str(r['Symbol']).strip()
                stocks.append({
                    "symbol": sym,
                    "yf_ticker": f"{sym}.NS",
                    "name": str(r.get('Company Name', sym)).strip(),
                    "industry": str(r.get('Industry', 'General')).strip(),
                    "segment": "Nifty 500"
                })
            print(f"✅ Loaded {len(stocks)} Nifty 500 stocks.")
            return stocks
    except Exception as e:
        print(f"⚠️ Using fallback list: {e}")
        fallback = ["RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "TATAMOTORS", "SBIN", "BHARTIARTL",
                    "ITC", "LT", "BAJFINANCE", "MARUTI", "SUNPHARMA", "TITAN", "TATASTEEL", "JSWSTEEL",
                    "M&M", "NTPC", "POWERGRID", "ADANIENT", "COALINDIA", "EICHERMOT", "TRENT", "HCLTECH",
                    "TECHM", "WIPRO", "ULTRACEMCO", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "BAJAJ-AUTO",
                    "DRREDDY", "CIPLA", "APOLLOHOSP", "TATAPOWER", "VEDL", "JINDALSTEL", "ZOMATO", "BEL"]
        return [{"symbol": s, "yf_ticker": f"{s}.NS", "name": s, "industry": "Equity", "segment": "Liquid F&O"} for s in fallback]


def calculate_cpr_levels(high: float, low: float, close: float):
    pivot = (high + low + close) / 3.0
    bc = (high + low) / 2.0
    tc = (pivot - bc) + pivot
    cpr_top = max(tc, bc)
    cpr_bot = min(tc, bc)
    width = ((cpr_top - cpr_bot) / pivot) * 100.0 if pivot > 0 else 0.0

    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)

    return {
        "pivot": round(pivot, 2), "bc": round(bc, 2), "tc": round(tc, 2),
        "cpr_top": round(cpr_top, 2), "cpr_bot": round(cpr_bot, 2),
        "width_pct": round(width, 3),
        "r1": round(r1, 2), "s1": round(s1, 2),
        "r2": round(r2, 2), "s2": round(s2, 2),
        "r3": round(r3, 2), "s3": round(s3, 2)
    }


def build_cpr_database(batch_size=100):
    stocks = get_liquid_nse_universe()
    tickers = [s["yf_ticker"] for s in stocks]
    stock_meta = {s["yf_ticker"]: s for s in stocks}

    print("📈 Fetching Nifty 50 benchmark (^NSEI)...")
    try:
        nifty_df = yf.download("^NSEI", period="6mo", interval="1d", auto_adjust=True, progress=False)
        nifty_ret_3m = float((nifty_df['Close'].iloc[-1] - nifty_df['Close'].iloc[-60]) / nifty_df['Close'].iloc[-60] * 100) if len(nifty_df) >= 60 else 0.0
    except Exception:
        nifty_ret_3m = 0.0

    print(f"🚀 Downloading 6 months OHLC for {len(tickers)} stocks in batches of {batch_size}...")
    start_time = time.time()
    results = []

    for i in range(0, len(tickers), batch_size):
        chunk = tickers[i:i + batch_size]
        print(f"  • Downloading batch {i // batch_size + 1}/{(len(tickers) + batch_size - 1) // batch_size}...")
        
        try:
            raw_data = yf.download(
                tickers=chunk,
                period="6mo",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False
            )
        except Exception as e:
            print(f"⚠️ Batch error: {e}")
            continue

        for sym in chunk:
            try:
                if sym not in raw_data.columns.levels[0]:
                    continue

                df = raw_data[sym].dropna()
                if len(df) < 30:
                    continue

                last = df.iloc[-1]
                prev = df.iloc[-2]
                price = round(float(last['Close']), 2)

                # Strict Turnover Guard (Minimum ₹5 Crore Daily Turnover)
                vol_20 = float(df['Volume'].iloc[-20:].mean())
                latest_vol = float(last['Volume'])
                turnover_cr = round((price * vol_20) / 1e7, 2)
                if turnover_cr < 5.0 or price < 20.0:
                    continue

                meta = stock_meta[sym]

                # 1. Daily CPR & 30-Day True Squeeze
                daily_cpr = calculate_cpr_levels(last['High'], last['Low'], last['Close'])
                prior_cpr = calculate_cpr_levels(prev['High'], prev['Low'], prev['Close'])

                historical_widths = [calculate_cpr_levels(df.iloc[-j]['High'], df.iloc[-j]['Low'], df.iloc[-j]['Close'])['width_pct'] 
                                     for j in range(2, min(32, len(df)))]
                avg_30_w = float(np.mean(historical_widths)) if historical_widths else 0.5
                comp_ratio = round(daily_cpr['width_pct'] / (avg_30_w + 1e-6), 2)
                
                # Percentile rank (Is today's width in the lowest 20% of last 30 days?)
                percentile_rank = round((sum(1 for w in historical_widths if w > daily_cpr['width_pct']) / (len(historical_widths) + 1e-6)) * 100, 1)

                if comp_ratio <= 0.50 or percentile_rank >= 85:
                    comp_tag = "Extreme Narrow 🔥"
                elif comp_ratio <= 0.75 or percentile_rank >= 70:
                    comp_tag = "Narrow 🎯"
                elif comp_ratio <= 1.25:
                    comp_tag = "Average ⚖️"
                else:
                    comp_tag = "Wide ↔️"

                # Pivot Relation
                if daily_cpr['cpr_bot'] > prior_cpr['cpr_top']:
                    relation = "Higher CPR 🔼"
                elif daily_cpr['cpr_top'] < prior_cpr['cpr_bot']:
                    relation = "Lower CPR 🔽"
                elif daily_cpr['cpr_top'] <= prior_cpr['cpr_top'] and daily_cpr['cpr_bot'] >= prior_cpr['cpr_bot']:
                    relation = "Inside CPR 📦"
                else:
                    relation = "Overlapping"

                # 2. Weekly & Monthly CPR
                df_w = df.resample('W-FRI').agg({'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
                last_w = df_w.iloc[-1] if len(df_w) > 0 else last
                weekly_cpr = calculate_cpr_levels(last_w['High'], last_w['Low'], last_w['Close'])

                df_m = df.resample('ME').agg({'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
                last_m = df_m.iloc[-1] if len(df_m) > 0 else last
                monthly_cpr = calculate_cpr_levels(last_m['High'], last_m['Low'], last_m['Close'])

                # 3. Indicators: RVOL, 20 EMA, 50 DMA, RS vs Nifty
                rvol = round(float(latest_vol / (vol_20 + 1e-6)), 2)
                ema_20 = round(float(df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]), 2)
                dma_50 = round(float(df['Close'].rolling(window=50, min_periods=20).mean().iloc[-1]), 2)

                stock_ret_3m = float((price - df['Close'].iloc[-min(60, len(df))]) / df['Close'].iloc[-min(60, len(df))] * 100)
                rs_score = round(stock_ret_3m - nifty_ret_3m, 2)

                # 4. Multi-Timeframe Confluence
                d_bull = price > daily_cpr['cpr_top']
                d_bear = price < daily_cpr['cpr_bot']
                w_bull = price >= weekly_cpr['pivot']
                m_bull = price >= monthly_cpr['pivot']

                if d_bull and w_bull and m_bull:
                    confluence = "Triple Bullish 🔥"
                elif d_bear and (not w_bull) and (not m_bull):
                    confluence = "Triple Bearish ❄️"
                elif d_bull and w_bull:
                    confluence = "Daily+Weekly Bull 🟢"
                elif d_bear and (not w_bull):
                    confluence = "Daily+Weekly Bear 🔴"
                else:
                    confluence = "Neutral / Mixed ⚖️"

                price_bias = "Above CPR (Bullish) 🟢" if d_bull else ("Below CPR (Bearish) 🔴" if d_bear else "Inside CPR 🟡")

                # Distance to TC (Proximity Guard)
                dist_to_tc_pct = round(abs(price - daily_cpr['tc']) / daily_cpr['tc'] * 100, 2)

                # -------------------------------------------------------------
                # 5. INSTITUTIONAL COMPOSITE QUANT SCORE (0 to 100)
                # -------------------------------------------------------------
                quant_score = 0
                reasons = []

                # Compression (Max 30 pts)
                if comp_ratio <= 0.50:
                    quant_score += 30
                    reasons.append("Extreme 30D Squeeze")
                elif comp_ratio <= 0.75:
                    quant_score += 20
                    reasons.append("Narrow CPR")

                # Multi-Timeframe Alignment (Max 25 pts)
                if confluence == "Triple Bullish 🔥":
                    quant_score += 25
                    reasons.append("Triple Bullish (D+W+M)")
                elif confluence == "Triple Bearish ❄️":
                    quant_score += 25
                    reasons.append("Triple Bearish (D+W+M)")
                elif "Daily+Weekly" in confluence:
                    quant_score += 15

                # Relative Strength Alpha (Max 20 pts)
                if rs_score >= 8.0:
                    quant_score += 20
                    reasons.append("Strong Alpha (RS > +8%)")
                elif rs_score >= 3.0:
                    quant_score += 12
                    reasons.append("Positive RS vs Nifty")

                # Volume Surge (Max 15 pts)
                if rvol >= 1.5:
                    quant_score += 15
                    reasons.append(f"Institutional Volume ({rvol}x)")
                elif rvol >= 1.1:
                    quant_score += 8

                # Trend Alignment: Price > 20 EMA > 50 DMA (Max 10 pts)
                if price > ema_20 and ema_20 > dma_50:
                    quant_score += 10
                    reasons.append("Stage 2 Trend (P > 20EMA > 50DMA)")

                # Star Rating Mapping
                if quant_score >= 80:
                    stars_count = 5
                    tier_tag = "💎 Diamond (Sniper)"
                elif quant_score >= 65:
                    stars_count = 4
                    tier_tag = "Gold (High Conviction)"
                elif quant_score >= 45:
                    stars_count = 3
                    tier_tag = "Silver (Standard)"
                else:
                    stars_count = 2
                    tier_tag = "Bronze"

                chart_candles = []
                for dt, row in df.tail(40).iterrows():
                    chart_candles.append({
                        "time": dt.strftime('%Y-%m-%d'),
                        "open": round(float(row['Open']), 2),
                        "high": round(float(row['High']), 2),
                        "low": round(float(row['Low']), 2),
                        "close": round(float(row['Close']), 2),
                        "volume": int(row['Volume'])
                    })

                results.append({
                    "symbol": meta["symbol"],
                    "name": meta["name"],
                    "industry": meta["industry"],
                    "price": price,
                    "turnover_cr": turnover_cr,
                    "quant_score": quant_score,
                    "rating": stars_count,
                    "stars": "⭐" * stars_count,
                    "tier": tier_tag,
                    "is_diamond": quant_score >= 80,
                    "compression": comp_tag,
                    "width_pct": daily_cpr['width_pct'],
                    "comp_ratio": f"{int(comp_ratio * 100)}%",
                    "dist_tc_pct": dist_to_tc_pct,
                    "rvol": rvol,
                    "rs_score": rs_score,
                    "dma_50": dma_50,
                    "ema_20": ema_20,
                    "confluence": confluence,
                    "bias": price_bias,
                    "relation": relation,
                    "reasons": ", ".join(reasons),
                    "daily": daily_cpr,
                    "weekly": weekly_cpr,
                    "monthly": monthly_cpr,
                    "candles": chart_candles
                })

            except Exception:
                continue

    elapsed = round(time.time() - start_time, 2)
    
    # Sort strictly by Quant Score (Highest first) and tightest width
    sorted_results = sorted(results, key=lambda x: (x["quant_score"], -x["width_pct"]), reverse=True)
    
    diamonds = [r for r in sorted_results if r["is_diamond"]]
    print(f"\n==========================================================================")
    print(f" ✅ PROCESSED {len(sorted_results)} STOCKS IN {elapsed}s")
    print(f" 💎 FOUND {len(diamonds)} DIAMOND SNIPER SETUPS (Composite Score >= 80/100)")
    print(f"==========================================================================")
    for d in diamonds[:10]:
        print(f"  • [{d['quant_score']}/100] {d['symbol']} ({d['name']}) | Price: ₹{d['price']} | {d['reasons']}")

    os.makedirs("data", exist_ok=True)
    payload = {
        "updated_at": datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p IST"),
        "total_scanned": len(sorted_results),
        "diamond_count": len(diamonds),
        "stocks": sorted_results
    }

    with open("data/screener_output.json", "w") as f:
        json.dump(payload, f, indent=2)

    print("📁 Saved sniper database to data/screener_output.json")


if __name__ == "__main__":
    build_cpr_database(batch_size=100)
