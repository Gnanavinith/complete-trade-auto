"""
Test script for Phase 3: Baseline Strategy + Risk Manager + Backtester.
Run: python -I test_phase3.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from app.config import config
from app.delta_client import make_delta_client
from app.backtest.backtester import Backtester

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("test_phase3")

def main():
    log.info("Starting Phase 3 verification (Baseline Strategy Backtest)...")
    client = make_delta_client(config.delta)

    btc_id = client.get_btc_product_id()
    btc_symbol = client._btc_symbol

    # Fetch 500 candles (approx 5 days of 15m data)
    df_15m = client.get_candles(symbol=btc_symbol, resolution="15m", limit=500)
    df_1h = client.get_candles(symbol=btc_symbol, resolution="1h", limit=200)

    log.info("Fetched %d 15m candles and %d 1h candles for backtest", len(df_15m), len(df_1h))

    backtester = Backtester(df_15m=df_15m, df_1h=df_1h, initial_equity=10000.0)
    results = backtester.run()

    log.info("=== BACKTEST RESULTS ===")
    log.info("  Initial Equity: $%.2f", results["initial_equity"])
    log.info("  Final Equity:   $%.2f", results["final_equity"])
    log.info("  Net PnL:        $%.2f (%.2f%%)", results["net_pnl"], results["return_pct"])
    log.info("  Total Trades:   %d", results["total_trades"])
    log.info("  Win Rate:       %.2f%%", results["win_rate_pct"])
    log.info("  Profit Factor:  %s", results["profit_factor"])
    log.info("  Max Drawdown:   %.2f%%", results["max_drawdown_pct"])

    if results["trades"]:
        log.info("Last 3 trades:")
        for t in results["trades"][-3:]:
            log.info("    %s | Side: %s | Entry: %.2f | Exit: %.2f | Reason: %s | PnL: $%.2f",
                     t["side"].upper(), t["side"], t["entry_price"], t["exit_price"], t["exit_reason"], t["net_pnl"])

    log.info("=== PHASE 3 VERIFICATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
