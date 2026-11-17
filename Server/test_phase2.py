"""
Test script for Phase 2: Indicators + Market Regime Detector.
Run: python -I test_phase2.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from app.config import config
from app.delta_client import make_delta_client
from app.indicators import ema, atr, rsi, adx, bollinger_bands, supertrend
from app.regime import detect_regime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("test_phase2")

def main():
    log.info("Starting Phase 2 verification (Indicators & Regime Detector)...")
    client = make_delta_client(config.delta)

    btc_id = client.get_btc_product_id()
    btc_symbol = client._btc_symbol

    df = client.get_candles(symbol=btc_symbol, resolution="15m", limit=200)
    log.info("Fetched %d candles for %s", len(df), btc_symbol)

    # Test indicators
    df["ema9"] = ema(df["close"], 9)
    df["ema21"] = ema(df["close"], 21)
    df["rsi14"] = rsi(df["close"], 14)
    df["atr14"] = atr(df, 14)
    df["adx14"] = adx(df, 14)
    _, _, _, df["bb_bw"] = bollinger_bands(df["close"])
    st_line, st_dir = supertrend(df)
    df["supertrend"] = st_line
    df["supertrend_dir"] = st_dir

    log.info("Latest Indicator Values:")
    latest = df.iloc[-1]
    log.info("  Close: %.2f", latest["close"])
    log.info("  EMA(9): %.2f | EMA(21): %.2f", latest["ema9"], latest["ema21"])
    log.info("  RSI(14): %.2f", latest["rsi14"])
    log.info("  ATR(14): %.2f", latest["atr14"])
    log.info("  ADX(14): %.2f", latest["adx14"])
    log.info("  Supertrend Dir: %d (Line: %.2f)", latest["supertrend_dir"], latest["supertrend"])

    # Test Regime Detection
    regime = detect_regime(df)
    log.info("Detected Market Regime: %s", regime.value)

    log.info("=== PHASE 2 VERIFICATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
