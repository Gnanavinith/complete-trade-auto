"""
Script to run the backtest over the last 30 days of BTC candles (15m and 1h) and print diagnostics.
"""
import sys
import os

# Add Server directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.config import config
from app.delta_client import make_delta_client
from app.backtest.backtester import Backtester
import json

def main():
    print("Initializing Delta Client for historical data fetch...")
    client = make_delta_client(config.delta)

    try:
        btc_id = client.get_btc_product_id()
        btc_symbol = client._btc_symbol
        print(f"Target Symbol: {btc_symbol} (Product ID: {btc_id})")

        # Fetch smaller sample (e.g. 500 candles = ~5 days) to ensure fast and reliable execution
        print("Fetching last 500 candles of 15m and 200 candles of 1h...")
        df_15m = client.get_candles(symbol=btc_symbol, resolution="15m", limit=500)
        df_1h = client.get_candles(symbol=btc_symbol, resolution="1h", limit=200)

        print(f"Fetched {len(df_15m)} 15m candles and {len(df_1h)} 1h candles.")

        if df_15m.empty:
            print("Error: Fetched empty 15m candle dataframe.")
            return

        backtester = Backtester(df_15m=df_15m, df_1h=df_1h, initial_equity=10000.0)
        results = backtester.run()

        print("\n" + "="*50)
        print("BACKTEST RESULTS (BTC)")
        print("="*50)
        print(f"Cycles Evaluated : {results['cycles_evaluated']}")
        print(f"Trades Taken     : {results['trades_taken']}")
        print(f"Total Closed     : {results['total_trades']}")
        print(f"Win Rate         : {results['win_rate_pct']}%")
        print(f"Net PnL          : ${results['net_pnl']} ({results['return_pct']}%)")
        print(f"Final Equity     : ${results['final_equity']}")
        print(f"Profit Factor    : {results['profit_factor']}")
        print(f"Max Drawdown     : {results['max_drawdown_pct']}%")
        print("\nFLAT Reasons Breakdown:")
        for reason, count in results['flat_reasons_count'].items():
            print(f"  - {reason}: {count} cycles")
        print("="*50)

    except Exception as e:
        print(f"Backtest execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
