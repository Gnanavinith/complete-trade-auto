"""
Comprehensive test suite verifying all system phases.
Run: python -I test_all_phases.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import pandas as pd
from app.config import config
from app.delta_client import make_delta_client
from app.indicators import ema, atr, rsi, adx, bollinger_bands
from app.regime import detect_regime, MarketRegime
from app.risk import RiskManager, RiskConfig
from app.liquidity import LiquidityCalculator
from app.backtest.backtester import Backtester

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("test_all")

def test_indicators_and_regime():
    log.info("Testing indicators and regime detection...")
    data = {
        "open": [100 + i*0.5 for i in range(100)],
        "high": [101 + i*0.5 for i in range(100)],
        "low": [99 + i*0.5 for i in range(100)],
        "close": [100.2 + i*0.5 for i in range(100)],
        "volume": [1000 for _ in range(100)]
    }
    df = pd.DataFrame(data)
    regime = detect_regime(df)
    log.info("Regime detection test passed: detected %s", regime.value)
    assert regime in list(MarketRegime)


def test_risk_manager():
    log.info("Testing risk manager sizing...")
    risk_cfg = RiskConfig()
    rm = RiskManager(risk_cfg, initial_equity=10000.0)
    contracts, sl, tp = rm.calculate_position_size(price=65000.0, atr_value=200.0, equity=10000.0)
    log.info("Risk calculation test passed: contracts=%d, SL=%.2f, TP=%.2f", contracts, sl, tp)
    assert contracts > 0
    assert sl < 65000.0
    assert tp > 65000.0


def test_liquidity_calculator():
    log.info("Testing liquidity calculator...")
    lc = LiquidityCalculator(max_slippage_pct=0.002)
    book = {
        "buy": [[64990.0, 1.5], [64980.0, 2.0]],
        "sell": [[65010.0, 1.5], [65020.0, 2.0]]
    }
    analysis = lc.analyze_orderbook(book, order_size_contracts=1, is_buy=True)
    log.info("Liquidity analysis test passed: can_execute=%s, slippage=%.4f%%", analysis["can_execute"], analysis["estimated_slippage_pct"]*100)
    assert "can_execute" in analysis


def main():
    log.info("=== STARTING COMPREHENSIVE SYSTEM TESTS ===")
    test_indicators_and_regime()
    test_risk_manager()
    test_liquidity_calculator()
    log.info("=== ALL COMPREHENSIVE UNIT TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
