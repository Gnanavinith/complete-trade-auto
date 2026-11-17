"""
Script to check account balance on Delta Exchange India testnet.
Run: python -I check_balance.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from app.config import config
from app.delta_client import make_delta_client, DeltaAPIError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("check_balance")

def main():
    log.info("Connecting to Delta Exchange (%s) at %s...", config.delta.env, config.delta.base_url)
    client = make_delta_client(config.delta)

    try:
        log.info("Querying wallet balances with provided API key...")
        balances = client.get_wallet_balances()
        log.info("=== WALLET BALANCES ===")
        if not balances:
            log.info("No balances returned or account is empty.")
        for b in balances:
            log.info("  Asset: %s | Balance/Free: %s | Locked: %s",
                     b.get("asset", b.get("currency", "UNKNOWN")),
                     b.get("balance", b.get("free", 0)),
                     b.get("locked", 0))
    except DeltaAPIError as e:
        log.error("Delta API Error: %s (Status: %s)", e, e.status_code)
        log.error("Response body: %s", e.response_body)
    except Exception as e:
        log.error("Failed to fetch balance: %s", e)

if __name__ == "__main__":
    main()
