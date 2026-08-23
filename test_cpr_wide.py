import yfinance as yf
import pandas as pd
import numpy as np
import time

# Curated active Nifty 50 & high-volume liquid F&O stocks
NIFTY_UNIVERSE = [
    {"symbol": "RELIANCE.NS", "name": "Reliance", "sector": "Energy"},
    {"symbol": "TCS.NS", "name": "TCS", "sector": "IT"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank", "sector": "Banking"},
    {"symbol": "INFY.NS", "name": "Infosys", "sector": "IT"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank", "sector": "Banking"},
    {"symbol": "SBIN.NS", "name": "SBI", "sector": "Banking"},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel", "sector": "Telecom"},
    {"symbol": "ITC.NS", "name": "ITC Ltd", "sector": "FMCG"},
    {"symbol": "KOTAKBANK.NS", "name": "Kotak Bank", "sector": "Banking"},
    {"symbol": "LT.NS", "name": "Larsen & Toubro", "sector": "Infra"},
    {"symbol": "AXISBANK.NS", "name": "Axis Bank", "sector": "Banking"},
    {"symbol": "BAJFINANCE.NS", "name": "Bajaj Finance", "sector": "Finance"},
    {"symbol": "HINDUNILVR.NS", "name": "HUL", "sector": "FMCG"},
    {"symbol": "MARUTI.NS", "name": "Maruti Suzuki", "sector": "Auto"},
    {"symbol": "M&M.NS", "name": "Mahindra & Mahindra", "sector": "Auto"},
    {"symbol": "SUNPHARMA.NS", "name": "Sun Pharma", "sector": "Pharma"},
    {"symbol": "TITAN.NS", "name": "Titan", "sector": "Consumer"},
    {"symbol": "ULTRACEMCO.NS", "name": "UltraTech Cement", "sector": "Cement"},
    {"symbol": "POWERGRID.NS", "name": "Power Grid", "sector": "Power"},
    {"symbol": "NTPC.NS", "name": "NTPC", "sector": "Power"},
    {"symbol": "TATASTEEL.NS", "name": "Tata Steel", "sector": "Metals"},
    {"symbol": "JSWSTEEL.NS", "name": "JSW Steel", "sector": "Metals"},
    {"symbol": "HINDALCO.NS", "name": "Hindalco", "sector": "Metals"},
    {"symbol": "ADANIENT.NS", "name": "Adani Enterprises", "sector": "Diversified"},
    {"symbol": "ADANIPORTS.NS", "name": "Adani Ports", "sector": "Infra"},
    {"symbol": "COALINDIA.NS", "name": "Coal India", "sector": "Mining"},
    {"symbol": "ONGC.NS", "name": "ONGC", "sector": "Oil & Gas"},
    {"symbol": "BAJAJ-AUTO.NS", "name": "Bajaj Auto", "sector": "Auto"},
    {"symbol": "EICHERMOT.NS", "name": "Eicher Motors", "sector": "Auto"},
    {"symbol": "TRENT.NS", "name": "Trent Ltd", "sector": "Retail"},
    {"symbol": "DRREDDY.NS", "name": "Dr Reddy", "sector": "Pharma"},
    {"symbol": "CIPLA.NS", "name": "Cipla", "sector": "Pharma"},
    {"symbol": "APOLLOHOSP.NS", "name": "Apollo Hosp", "sector": "Healthcare"},
    {"symbol": "WIPRO.NS", "name": "Wipro", "sector": "IT"},
    {"symbol": "HCLTECH.NS", "name": "HCL Tech", "sector": "IT"},
    {"symbol": "TECHM.NS", "name": "Tech Mahindra", "sector": "IT"},
    {"symbol": "TATAPOWER.NS", "name": "Tata Power", "sector": "Power"},
    {"symbol": "VEDL.NS", "name": "Vedanta", "sector": "Metals"},
    {"symbol": "JINDALSTEL.NS", "name": "Jindal Steel", "sector": "Metals"}
]


def calculate_cpr(high, low, close):
    pivot = (high + low + close) / 3.0
    bc = (high + low) / 2.0
    tc = (pivot - bc) + pivot
    cpr_top = max(tc, bc)
    cpr_bot = min(tc, bc)
    width = ((cpr_top - cpr_bot) / pivot) * 100.0 if pivot > 0 else 0.0
    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high
    return {
        "pivot": round(pivot, 2), "bc": round(bc, 2), "tc": round(tc, 2),
        "cpr_top": round(cpr_top, 2), "cpr_bot": round(cpr_bot, 2),
        "width": round(width, 3), "r1": round(r1, 2), "s1": round(s1, 2)
    }


def run_screener():
    print("=" * 110)
    print(f" 🚀 BATCH FETCHING {len(NIFTY_UNIVERSE)} LIQUID NSE STOCKS (Nifty 50 & F&O)")
    print("=" * 110)
    
    start_time = time.time()
    symbols = [item["symbol"] for item in NIFTY_UNIVERSE]
    meta_map = {item["symbol"]: item for item in NIFTY_UNIVERSE}

    # 1 Single Batch Call for All Symbols (Fast and Avoids Rate Limits)
    raw_data = yf.download(
        tickers=symbols,
        period="6mo",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=True
    )

    results = []

    for sym in symbols:
        try:
            # Handle multi-index data format
            if sym in raw_data.columns.levels[0]:
                df = raw_data[sym].dropna()
            else:
                continue

            if len(df) < 25:
                continue

            meta = meta_map[sym]
            last = df.iloc[-1]
            price = round(float(last['Close']), 2)

            # 1. Daily CPR for upcoming session
            daily_cpr = calculate_cpr(last['High'], last['Low'], last['Close'])

            # 2. Historical 14-day average CPR width
            widths = [calculate_cpr(df.iloc[-i]['High'], df.iloc[-i]['Low'], df.iloc[-i]['Close'])['width'] 
                      for i in range(2, min(17, len(df)))]
            avg_w = np.mean(widths) if widths else 0.5
            comp_ratio = round(daily_cpr['width'] / (avg_w + 1e-6), 2)

            # 3. Weekly & Monthly Resampling
            df_w = df.resample('W-FRI').agg({'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
            last_w = df_w.iloc[-1] if len(df_w) > 0 else last
            weekly_cpr = calculate_cpr(last_w['High'], last_w['Low'], last_w['Close'])

            df_m = df.resample('ME').agg({'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
            last_m = df_m.iloc[-1] if len(df_m) > 0 else last
            monthly_cpr = calculate_cpr(last_m['High'], last_m['Low'], last_m['Close'])

            # 4. Volume (RVOL) & 20 EMA
            vol_20 = df['Volume'].iloc[-20:].mean()
            rvol = round(float(last['Volume'] / (vol_20 + 1e-6)), 2)
            ema_20 = float(df['Close'].ewm(span=20, adjust=False).mean().iloc[-1])

            # 5. Price Position & Multi-Timeframe Alignment
            daily_bull = price > daily_cpr['cpr_top']
            daily_bear = price < daily_cpr['cpr_bot']
            weekly_bull = price >= weekly_cpr['pivot']
            monthly_bull = price >= monthly_cpr['pivot']

            if daily_bull and weekly_bull and monthly_bull:
                confluence = "Triple Bullish 🔥"
            elif daily_bear and (not weekly_bull) and (not monthly_bull):
                confluence = "Triple Bearish ❄️"
            elif daily_bull and weekly_bull:
                confluence = "Daily+Weekly Bull 🟢"
            elif daily_bear and (not weekly_bull):
                confluence = "Daily+Weekly Bear 🔴"
            else:
                confluence = "Neutral / Mixed ⚖️"

            # 6. 1 to 5 Star Quality Rating
            score = 1
            if comp_ratio <= 0.60: score += 2       # Extreme Narrow
            elif comp_ratio <= 0.85: score += 1     # Narrow
            
            if "Triple Bullish" in confluence or "Triple Bearish" in confluence: score += 2
            elif "Daily+Weekly" in confluence: score += 1
            
            if rvol >= 1.2: score += 1              # Volume surge
            if price >= ema_20 and daily_bull: score += 1

            score = min(5, max(1, score))
            comp_tag = "Extreme Narrow 🔥" if comp_ratio <= 0.60 else ("Narrow 🎯" if comp_ratio <= 0.85 else "Average/Wide")

            results.append({
                "Symbol": sym.replace(".NS", ""),
                "Sector": meta["sector"],
                "Price": price,
                "Rating": "⭐" * score,
                "Score": score,
                "Compression": comp_tag,
                "Width%": daily_cpr['width'],
                "CompRatio": f"{int(comp_ratio*100)}%",
                "RVOL": f"{rvol}x",
                "Confluence": confluence,
                "TC": daily_cpr['tc'],
                "Pivot": daily_cpr['pivot'],
                "BC": daily_cpr['bc']
            })

        except Exception as e:
            continue

    elapsed = round(time.time() - start_time, 2)
    
    if not results:
        print("⚠️ No results could be generated. Check your internet connection.")
        return

    df_out = pd.DataFrame(results)
    df_out = df_out.sort_values(by=["Score", "Width%"], ascending=[False, True])

    print(f"\n✅ Successfully analyzed {len(df_out)} stocks in {elapsed} seconds!\n")

    print("=" * 110)
    print(" 🌟 4-STAR & 5-STAR HIGH CONVICTION SETUPS:")
    print("=" * 110)
    top_picks = df_out[df_out["Score"] >= 4]
    cols = ["Symbol", "Sector", "Price", "Rating", "Compression", "Width%", "CompRatio", "RVOL", "Confluence"]
    if not top_picks.empty:
        print(top_picks[cols].to_string(index=False))
    else:
        print("No 4/5 star setups today.")

    print("\n" + "=" * 110)
    print(" 🎯 ALL COMPRESSED NARROW CPR STOCKS (Breakout Watchlist):")
    print("=" * 110)
    narrow = df_out[df_out["Compression"].str.contains("Narrow")]
    if not narrow.empty:
        print(narrow[cols].to_string(index=False))
    else:
        print("No narrow compression stocks today.")

    print("\n" + "=" * 110)


if __name__ == "__main__":
    run_screener()
