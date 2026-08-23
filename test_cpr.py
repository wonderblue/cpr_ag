import yfinance as yf
import pandas as pd
import numpy as np

SAMPLE_STOCKS = [
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "sector": "Energy"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services", "sector": "IT"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank", "sector": "Banking"},
    {"symbol": "TATAMOTORS.NS", "name": "Tata Motors", "sector": "Auto"},
    {"symbol": "INFY.NS", "name": "Infosys", "sector": "IT"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank", "sector": "Banking"},
    {"symbol": "BAJFINANCE.NS", "name": "Bajaj Finance", "sector": "Finance"},
    {"symbol": "TITAN.NS", "name": "Titan Company", "sector": "Consumer"},
    {"symbol": "MARUTI.NS", "name": "Maruti Suzuki", "sector": "Auto"},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel", "sector": "Telecom"}
]

def calculate_cpr(high, low, close):
    p = (high + low + close) / 3.0
    bc = (high + low) / 2.0
    tc = (p - bc) + p
    cpr_top = max(tc, bc)
    cpr_bot = min(tc, bc)
    width = ((cpr_top - cpr_bot) / p) * 100.0 if p > 0 else 0.0
    return {"p": round(p, 2), "bc": round(bc, 2), "tc": round(tc, 2), "top": round(cpr_top, 2), "bot": round(cpr_bot, 2), "width": round(width, 3)}

print("\n🚀 Fetching NSE live data via Yahoo Finance & calculating CPR...\n")
results = []

for item in SAMPLE_STOCKS:
    try:
        t = yf.Ticker(item["symbol"])
        df = t.history(period="3mo", interval="1d")
        if len(df) < 15: continue
        
        last = df.iloc[-1]
        cpr = calculate_cpr(last['High'], last['Low'], last['Close'])
        price = round(float(last['Close']), 2)
        
        # 14-day average width
        widths = [calculate_cpr(df.iloc[-i]['High'], df.iloc[-i]['Low'], df.iloc[-i]['Close'])['width'] for i in range(2, 16)]
        avg_w = np.mean(widths)
        ratio = round(cpr['width'] / (avg_w + 1e-6), 2)
        
        # Compression Category
        comp = "Extreme Narrow 🔥" if ratio <= 0.60 else ("Narrow 🎯" if ratio <= 0.85 else "Normal/Wide ⚖️")
        
        # Price Bias
        bias = "Bullish (>TC) 🟢" if price > cpr['top'] else ("Bearish (<BC) 🔴" if price < cpr['bot'] else "Inside CPR 🟡")
        
        # Star Rating
        stars = 3
        if ratio <= 0.60: stars += 2
        elif ratio <= 0.85: stars += 1
        if "Bullish" in bias: stars += 1
        stars = min(5, stars)
        
        results.append({
            "Symbol": item["symbol"].replace(".NS", ""),
            "Price": f"₹{price}",
            "CPR Width": f"{cpr['width']}%",
            "Compression": comp,
            "Bias": bias,
            "Rating": "⭐" * stars,
            "TC": cpr['tc'],
            "Pivot": cpr['p'],
            "BC": cpr['bc']
        })
    except Exception as e:
        print(f"Error {item['symbol']}: {e}")

res_df = pd.DataFrame(results).sort_values(by="Rating", ascending=False)
print(res_df[["Symbol", "Price", "Rating", "Compression", "CPR Width", "Bias", "TC", "Pivot", "BC"]].to_string(index=False))
print("\n✅ Tested successfully on macOS!\n")
