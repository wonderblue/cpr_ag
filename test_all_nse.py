import urllib.request
import io
import pandas as pd
import yfinance as yf
import numpy as np
import time

def get_nifty500_and_fno_symbols():
    """
    Downloads the official Nifty 500 list from NSE archives.
    This represents the top 500 companies in India spanning A to Z.
    """
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    
    print("📥 Downloading official NIFTY 500 Universe (A to Z leaders)...")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            csv_data = response.read().decode('utf-8')
            df = pd.read_csv(io.StringIO(csv_data))
            symbols = df['Symbol'].str.strip().tolist()
            print(f"✅ Successfully loaded {len(symbols)} stocks spanning full A-Z Indian market!\n")
            return symbols, df
    except Exception as e:
        print(f"Direct Nifty500 download error ({e}), fetching from backup repository...")
        # Fallback list of major liquid symbols if NSE blocks direct script user-agent
        url_backup = "https://raw.githubusercontent.com/anirban-d/indian-stock-market-dataset/master/data/nifty500.csv"
        df = pd.read_csv(url_backup)
        symbols = df['Symbol'].tolist() if 'Symbol' in df.columns else df.iloc[:, 0].tolist()
        return symbols, df


def calculate_cpr(high, low, close):
    pivot = (high + low + close) / 3.0
    bc = (high + low) / 2.0
    tc = (pivot - bc) + pivot
    cpr_top = max(tc, bc)
    cpr_bot = min(tc, bc)
    width = ((cpr_top - cpr_bot) / pivot) * 100.0 if pivot > 0 else 0.0
    return {
        "pivot": round(pivot, 2), "bc": round(bc, 2), "tc": round(tc, 2),
        "cpr_top": round(cpr_top, 2), "cpr_bot": round(cpr_bot, 2),
        "width": round(width, 3)
    }


def scan_full_market_a_to_z(sample_size=150):
    symbols, df_meta = get_nifty500_and_fno_symbols()
    
    if not symbols:
        return

    # Take an evenly spaced sample across the entire alphabet (A to Z)
    # E.g. Reliance (R), TCS (T), SBI (S), Tata Motors (T), Zomato (Z), etc.
    step = max(1, len(symbols) // sample_size)
    selected_symbols = symbols[::step][:sample_size]
    yf_symbols = [f"{s}.NS" for s in selected_symbols]

    print("=" * 110)
    print(f" 🚀 SCANNING {len(yf_symbols)} DIVERSE STOCKS SPANNING A TO Z (Sample from Nifty 500)")
    print("=" * 110)

    start_time = time.time()
    
    # Download data with clean batching
    raw_data = yf.download(
        tickers=yf_symbols,
        period="4mo",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=True
    )

    results = []

    for sym in yf_symbols:
        try:
            if sym not in raw_data.columns.levels[0]:
                continue

            df = raw_data[sym].dropna()
            if len(df) < 20:
                continue

            last = df.iloc[-1]
            price = round(float(last['Close']), 2)

            vol_20 = df['Volume'].iloc[-20:].mean()
            latest_vol = last['Volume']
            turnover_cr = (price * vol_20) / 1e7

            # Skip illiquid (< ₹1 Cr turnover)
            if turnover_cr < 1.0 or price < 15:
                continue

            # Daily CPR
            daily_cpr = calculate_cpr(last['High'], last['Low'], last['Close'])

            # 14-day average width
            widths = [calculate_cpr(df.iloc[-i]['High'], df.iloc[-i]['Low'], df.iloc[-i]['Close'])['width'] 
                      for i in range(2, min(16, len(df)))]
            avg_w = np.mean(widths) if widths else 0.5
            comp_ratio = round(daily_cpr['width'] / (avg_w + 1e-6), 2)

            # Weekly CPR
            df_w = df.resample('W-FRI').agg({'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
            last_w = df_w.iloc[-1] if len(df_w) > 0 else last
            weekly_cpr = calculate_cpr(last_w['High'], last_w['Low'], last_w['Close'])

            # Volume surge (RVOL)
            rvol = round(float(latest_vol / (vol_20 + 1e-6)), 2)

            daily_bull = price > daily_cpr['cpr_top']
            daily_bear = price < daily_cpr['cpr_bot']
            weekly_bull = price >= weekly_cpr['pivot']

            if daily_bull and weekly_bull:
                confluence = "Daily+Weekly Bull 🟢"
            elif daily_bear and (not weekly_bull):
                confluence = "Daily+Weekly Bear 🔴"
            else:
                confluence = "Neutral / Mixed ⚖️"

            # 5-Star Setup Score
            score = 1
            if comp_ratio <= 0.60: score += 2       # Extreme Narrow Compression
            elif comp_ratio <= 0.85: score += 1     # Narrow
            
            if "Bull" in confluence or "Bear" in confluence: score += 1
            if rvol >= 1.2: score += 1
            if daily_bull: score += 1

            score = min(5, max(1, score))
            comp_tag = "Extreme Narrow 🔥" if comp_ratio <= 0.60 else ("Narrow 🎯" if comp_ratio <= 0.85 else "Average/Wide")

            results.append({
                "Symbol": sym.replace(".NS", ""),
                "Price": f"₹{price}",
                "Turnover": f"₹{round(turnover_cr, 1)}Cr",
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
        except Exception:
            continue

    elapsed = round(time.time() - start_time, 2)
    df_out = pd.DataFrame(results)

    if df_out.empty:
        print("No qualifying liquid stocks found in this sample batch.")
        return

    df_out = df_out.sort_values(by=["Score", "Width%"], ascending=[False, True])

    print(f"\n==========================================================================================")
    print(f" ✅ SCAN COMPLETE: Filtered {len(df_out)} High-Volume Stocks Spanning A-Z in {elapsed}s")
    print(f"==========================================================================================")

    print("\n 🌟 TOP 5-STAR & 4-STAR HIGH CONVICTION SETUPS (From A to Z):")
    print("=" * 110)
    top_picks = df_out[df_out["Score"] >= 4]
    cols = ["Symbol", "Price", "Turnover", "Rating", "Compression", "Width%", "CompRatio", "RVOL", "Confluence"]
    if not top_picks.empty:
        print(top_picks[cols].head(20).to_string(index=False))
    else:
        print(df_out[cols].head(20).to_string(index=False))

    print("\n" + "=" * 110)
    print(" 🎯 EXTREME NARROW CPR STOCKS (High Probability Breakouts across sectors):")
    print("=" * 110)
    narrow = df_out[df_out["Compression"].str.contains("Extreme Narrow")]
    if not narrow.empty:
        print(narrow[cols].head(20).to_string(index=False))
    else:
        print("No extreme compression today.")


if __name__ == "__main__":
    scan_full_market_a_to_z(sample_size=150)
