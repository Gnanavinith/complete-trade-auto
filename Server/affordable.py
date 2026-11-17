import requests

BASE = "https://api.india.delta.exchange"
BALANCE_INR = 51.83
USDINR = 88.0       # update to current rate
LEVERAGE = 10
SAFETY = 0.5        # use at most 50% of balance as margin

try:
    p_res = requests.get(f"{BASE}/v2/products", timeout=15).json()
    t_res = requests.get(f"{BASE}/v2/tickers", timeout=15).json()

    products = p_res.get("result", [])
    tickers = {t["symbol"]: t for t in t_res.get("result", [])}

    rows = []
    for p in products:
        if p.get("contract_type") != "perpetual_futures" or p.get("state") != "live":
            continue
        sym = p.get("symbol")
        t = tickers.get(sym)
        if not t or not t.get("mark_price"):
            continue

        try:
            cv = float(p.get("contract_value", 1.0))
            mp = float(t.get("mark_price", 0.0))
            notional_inr = cv * mp * USDINR
            margin = notional_inr / LEVERAGE
            rows.append((margin, sym, notional_inr))
        except Exception:
            continue

    for margin, sym, notional in sorted(rows):
        ok = "OK " if margin <= BALANCE_INR * SAFETY else "-- "
        print(f"{ok}{sym:15} notional Rs.{notional:10.2f}  margin@{LEVERAGE}x Rs.{margin:9.2f}")

except Exception as e:
    print("Error fetching from Delta Exchange:", e)
