import urllib.request
import zipfile
import io
import pandas as pd
import numpy as np
import datetime
import time

def fetch_nse_bhavcopy_with_fallback(max_lookback_days=7):
    now = datetime.datetime.now()
    current_date = now.date()
    if now.hour < 17:
        current_date -= datetime.timedelta(days=1)

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    for i in range(max_lookback_days):
        check_date = current_date - datetime.timedelta(days=i)
        if check_date.weekday() in [5, 6]: # Skip Sat/Sun
            continue

        date_str = check_date.strftime("%d%m%Y")
        url = f"https://archives.nseindia.com/products/content/sec_bhavdata_full_{date_str}.csv"
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                content = response.read().decode('utf-8')
                if "SYMBOL" in content or "SYMBOL " in content:
                    df = pd.read_csv(io.StringIO(content))
                    df.columns = [c.strip() for c in df.columns]
                    
                    # Filter Series (EQ: Regular equity, BE: Book entry)
                    if 'SERIES' in df.columns:
                        df = df[df['SERIES'].str.strip().isin(['EQ', 'BE'])]
                    
                    # Extract High, Low, Close (support all NSE header variants)
                    high_col = 'HIGH_PRICE' if 'HIGH_PRICE' in df.columns else ('HIGH' if 'HIGH' in df.columns else None)
                    low_col = 'LOW_PRICE' if 'LOW_PRICE' in df.columns else ('LOW' if 'LOW' in df.columns else None)
                    close_col = 'CLOSE_PRICE' if 'CLOSE_PRICE' in df.columns else ('CLOSE' if 'CLOSE' in df.columns else None)
                    sym_col = 'SYMBOL' if 'SYMBOL' in df.columns else df.columns[0]
                    
                    # Turnover Calculation in ₹ Crores
                    if 'TURNOVER_LACS' in df.columns:
                        df['Turnover_Cr'] = pd.to_numeric(df['TURNOVER_LACS'], errors='coerce') / 100.0
                    elif 'TOTAL_TRADED_VAL' in df.columns:
                        df['Turnover_Cr'] = pd.to_numeric(df['TOTAL_TRADED_VAL'], errors='coerce') / 1e7
                    else:
                        df['Turnover_Cr'] = 5.0 # Default if column missing
                        
                    df['High'] = pd.to_numeric(df[high_col], errors='coerce')
                    df['Low'] = pd.to_numeric(df[low_col], errors='coerce')
                    df['Close'] = pd.to_numeric(df[close_col], errors='coerce')
                    df['Symbol'] = df[sym_col].astype(str).str.strip()
                    df['EXCHANGE'] = 'NSE'
                    
                    df = df.dropna(subset=['High', 'Low', 'Close'])
                    print(f"✅ Loaded {len(df)} NSE stocks for {check_date.strftime('%A, %d-%b-%Y')}")
                    return df[['Symbol', 'High', 'Low', 'Close', 'Turnover_Cr', 'EXCHANGE']], check_date

        except Exception as err:
            continue

    print("⚠️ Could not download Bhavcopy directly from archives.nseindia.com")
    return pd.DataFrame(), None


def fetch_bse_bhavcopy(trade_date):
    if not trade_date:
        return pd.DataFrame()

    date_str = trade_date.strftime("%d%m%y")
    url = f"https://www.bseindia.com/BSEDATA/gross/{date_str}/EQ_ISINCODE_{date_str}.ZIP"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            with zipfile.ZipFile(io.BytesIO(response.read())) as z:
                csv_filename = z.namelist()[0]
                df = pd.read_csv(z.open(csv_filename))
                df.columns = [c.strip() for c in df.columns]
                df['Turnover_Cr'] = round(pd.to_numeric(df['NET_TURNOV'], errors='coerce') / 1e7, 2)
                df['EXCHANGE'] = 'BSE'
                df['High'] = pd.to_numeric(df['HIGH'], errors='coerce')
                df['Low'] = pd.to_numeric(df['LOW'], errors='coerce')
                df['Close'] = pd.to_numeric(df['CLOSE'], errors='coerce')
                df['Symbol'] = df['SC_NAME'].astype(str).str.strip()
                df = df.dropna(subset=['High', 'Low', 'Close'])
                print(f"✅ Loaded {len(df)} BSE listed stocks.")
                return df[['Symbol', 'High', 'Low', 'Close', 'Turnover_Cr', 'EXCHANGE']]
    except Exception:
        return pd.DataFrame()


def calculate_cpr(df):
    """Vectorized calculation of CPR, CPR width, and S/R levels."""
    df['Pivot'] = round((df['High'] + df['Low'] + df['Close']) / 3.0, 2)
    df['BC'] = round((df['High'] + df['Low']) / 2.0, 2)
    df['TC'] = round((df['Pivot'] - df['BC']) + df['Pivot'], 2)
    df['CPR_Top'] = df[['TC', 'BC']].max(axis=1)
    df['CPR_Bot'] = df[['TC', 'BC']].min(axis=1)
    df['Width%'] = round(((df['CPR_Top'] - df['CPR_Bot']) / df['Pivot']) * 100, 3)
    
    # S/R Levels
    df['R1'] = round((2 * df['Pivot']) - df['Low'], 2)
    df['S1'] = round((2 * df['Pivot']) - df['High'], 2)
    df['R2'] = round(df['Pivot'] + (df['High'] - df['Low']), 2)
    df['S2'] = round(df['Pivot'] - (df['High'] - df['Low']), 2)

    # Classification
    cond = [df['Width%'] <= 0.20, df['Width%'] <= 0.40, df['Width%'] <= 0.80]
    choice = ['Extreme Narrow 🔥', 'Narrow 🎯', 'Average ⚖️']
    df['CPR_Type'] = np.select(cond, choice, default='Wide')

    pos = [df['Close'] > df['CPR_Top'], df['Close'] < df['CPR_Bot']]
    pos_c = ['Above CPR (Bullish) 🟢', 'Below CPR (Bearish) 🔴']
    df['Price_Bias'] = np.select(pos, pos_c, default='Inside CPR 🟡')

    return df


def run_full_scan():
    print("=" * 110)
    print(" 🚀 AUTOMATED FULL-MARKET CPR SCREENER (ALL NSE + BSE EQUITIES)")
    print("=" * 110)
    
    start_t = time.time()
    df_nse, trade_date = fetch_nse_bhavcopy_with_fallback()
    df_bse = fetch_bse_bhavcopy(trade_date)
    
    df_all = pd.concat([df_nse, df_bse], ignore_index=True)
    
    if df_all.empty:
        print("⚠️ Direct exchange server busy. Please retry.")
        return

    print(f"⚡ Total combined stocks: {len(df_all)}")
    
    # Fast vectorized CPR calculation
    df_cpr = calculate_cpr(df_all)

    # Liquidity filter: Minimum ₹2 Cr turnover to filter illiquid traps
    df_liquid = df_cpr[df_cpr['Turnover_Cr'] >= 2.0].copy()
    df_sorted = df_liquid.sort_values(by=['Width%'], ascending=True)

    elapsed = round(time.time() - start_t, 2)
    
    print(f"\n==========================================================================================")
    print(f" ✅ PROCESSED {len(df_liquid)} ACTIVE LIQUID STOCKS IN {elapsed}s (Data Date: {trade_date.strftime('%d-%b-%Y')})")
    print(f"==========================================================================================")

    print("\n 🌟 TOP 25 NARROWEST CPR STOCKS (Highest Breakout Potential for Next Session):")
    print("=" * 110)
    cols = ['Symbol', 'EXCHANGE', 'Close', 'Turnover_Cr', 'CPR_Type', 'Width%', 'Price_Bias', 'TC', 'Pivot', 'BC', 'R1', 'S1']
    print(df_sorted[cols].head(25).to_string(index=False))

    print("\n" + "=" * 110)
    print(" 🟢 TOP BULLISH BREAKOUT CANDIDATES (Above CPR + Tight Compression):")
    print("=" * 110)
    bullish = df_sorted[(df_sorted['Price_Bias'].str.contains("Bullish")) & (df_sorted['Width%'] <= 0.30)]
    if not bullish.empty:
        print(bullish[cols].head(20).to_string(index=False))


if __name__ == "__main__":
    run_full_scan()
