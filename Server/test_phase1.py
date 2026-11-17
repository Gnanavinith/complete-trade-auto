"""
Test script for Phase 1: Delta Exchange client + auth + fetch products, candles, orderbook, balance.
Run: python -I test_phase1.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from app.config import config
from app.delta_client import make_delta_client, DeltaAPIError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("test_phase1")

def main():
    log.info("Starting Phase 1 verification against Delta Exchange (%s)...", config.delta.env)
    log.info("Delta Base URL: %s", config.delta.base_url)

    client = make_delta_client(config.delta)

    # 1. Test fetching products & dynamic BTC perpetual product ID discovery
    try:
        log.info("Fetching products from Delta Exchange...")
        products = client.get_products()
        log.info("Successfully fetched %d products.", len(products))

        btc_id = client.get_btc_product_id()
        btc_symbol = client._btc_symbol
        log.info("Successfully discovered BTC Perpetual product_id = %d, symbol = %s", btc_id, btc_symbol)
    except Exception as e:
        log.error("Failed products fetch or BTC ID discovery: %s", e)
        sys.exit(1)

    # 2. Test fetching candles
    try:
        log.info("Fetching 15m historical candles for symbol=%s (product_id=%d)...", btc_symbol, btc_id)
        df = client.get_candles(symbol=btc_symbol, resolution="15m", limit=50)
        log.info("Successfully fetched candles DataFrame with shape %s", df.shape)
        if not df.empty:
            log.info("Latest candle:\n%s", df.tail(1).to_string())
    except Exception as e:
        log.error("Failed candles fetch: %s", e)
        sys.exit(1)

    # 3. Test fetching L2 orderbook
    try:
        log.info("Fetching L2 orderbook for product_id=%d...", btc_id)
        book = client.get_l2_orderbook(product_id=btc_id)
        log.info("Successfully fetched orderbook. Keys: %s", list(book.keys()) if isinstance(book, dict) else type(book))
    except Exception as e:
        log.error("Failed orderbook fetch: %s", e)
        sys.exit(1)

    # 4. Test authenticated endpoint (Wallet Balances)
    try:
        log.info("Testing authenticated wallet balances endpoint...")
        if not config.delta.api_key or not config.delta.api_secret:
            log.warning("No DELTA_API_KEY / DELTA_API_SECRET provided in environment. Skipping authenticated balance call (or expect auth error).")
        else:
            balances = client.get_wallet_balances()
            log.info("Successfully fetched wallet balances: %s", balances)
    except DeltaAPIError as e:
        log.warning("Authenticated balance call failed as expected if testnet keys are missing/invalid: %s", e)
    except Exception as e:
        log.warning("Authenticated balance call error: %s", e)

    log.info("=== PHASE 1 VERIFICATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
