import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import config
from app.delta_client import DeltaClient
from app.engine import SingleBotEngine
from app.aggregator import Aggregator
from app.regime import detect_regime
from app.risk import RiskManager
from app.execution import ExecutionEngine
from app.ai_analyst import GeminiMarketAnalyst
from app.strategies.trend_ema import TrendEmaStrategy
from app.strategies.range_rsi_bb import RangeRsiBbStrategy
from app.indicators import atr
import pandas as pd

def run_checks():
    print("=" * 65)
    print("🚀 AUTOMATED DEPLOYMENT & ENTRY LOGIC VERIFICATION")
    print("=" * 65)

    # 1. Config Check
    print("\n[1] CONFIGURATION SETTINGS:")
    print(f"   Delta Env:         {config.delta.env}")
    print(f"   Delta Base URL:    {config.delta.base_url}")
    print(f"   Paper Mode:        {config.paper_mode}")
    print(f"   Live Trading:      {config.delta.live_trading}")
    print(f"   Default Symbol:    {config.strategy.symbol}")
    print(f"   Timeframe:         {config.strategy.timeframe}")
    print(f"   Risk Per Trade:    {config.risk.risk_per_trade_pct * 100}%")
    print(f"   Max Leverage:      {config.risk.max_leverage}x")

    # 2. Delta Client & Auth
    print("\n[2] DELTA EXCHANGE API & AUTHENTICATION:")
    client = DeltaClient(config.delta)
    try:
        balances = client.get_wallet_balances()
        print("   ✅ API Authentication Successful!")
        funded = [b for b in balances if float(b.get("balance", 0)) > 0]
        if funded:
            for b in funded:
                print(f"   💰 Asset: {b.get('asset_symbol')} | Balance: {b.get('balance')} | Available: {b.get('available_balance')}")
        else:
            print("   ⚠️ No assets with balance > 0 found.")
    except Exception as e:
        print(f"   ❌ Delta API Failed: {e}")
        return

    # 3. Market Data & Indicator Aggregator
    print("\n[3] MARKET DATA & INDICATORS:")
    try:
        ticker = client.get_ticker(config.strategy.symbol)
        mark_price = float(ticker.get("mark_price") or ticker.get("close") or 0)
        print(f"   ✅ Live BTCUSD Mark Price: ${mark_price:,.2f}")

        candles_15m = client.get_candles(config.strategy.symbol, config.strategy.timeframe, limit=100)
        print(f"   ✅ {config.strategy.timeframe} Candles Fetched: {len(candles_15m)}")
        
        df_15m = pd.DataFrame(candles_15m)
        for col in ["open", "high", "low", "close", "volume"]:
            df_15m[col] = df_15m[col].astype(float)
            
        candles_1h = client.get_candles(config.strategy.symbol, "1h", limit=100)
        df_1h = pd.DataFrame(candles_1h)
        for col in ["open", "high", "low", "close", "volume"]:
            df_1h[col] = df_1h[col].astype(float)
        
        strategies = [TrendEmaStrategy(), RangeRsiBbStrategy()]
        aggregator = Aggregator(strategies)
        action, score, regime = aggregator.decide(df_15m, df_1h)
        print(f"   ✅ Aggregator Signal Evaluated:")
        print(f"      - Action:       {action.upper()}")
        print(f"      - Score:        {score:.2f} (Entry Threshold: >= +0.6 for BUY, <= -0.6 for SELL)")
        print(f"      - Regime:       {regime.name}")
    except Exception as e:
        print(f"   ❌ Market Data Failed: {e}")

    # 4. Gemini AI Analyst
    print("\n[4] GEMINI AI MARKET ANALYST:")
    try:
        analyst = GeminiMarketAnalyst()
        res = analyst.analyze_and_broadcast(df_15m, notify=False)
        print(f"   ✅ Gemini AI Generation Success!")
        print(f"      - Bias:         {res.get('bias')} ({res.get('confidence_pct')}%)")
        print(f"      - Summary:      {res.get('summary')[:90]}...")
    except Exception as e:
        print(f"   ❌ Gemini AI Error: {e}")

    # 5. Risk Management & Position Sizing
    print("\n[5] RISK MANAGEMENT & POSITION SIZING:")
    risk_mgr = RiskManager(config.risk, initial_equity=0.60978)
    can_trade, reason = risk_mgr.check_gates()
    print(f"   - Risk Gate Check: Allowed={can_trade} (Status: {reason})")
    
    current_atr = atr(df_15m, 14).iloc[-1]
    num_contracts, sl_price, tp_price = risk_mgr.calculate_position_size(mark_price, current_atr, 0.60978)
    print(f"   - Position Sizing for BTCUSD ($0.61 equity): {num_contracts} contract(s)")
    print(f"   - Calculated ATR (14): ${current_atr:.2f}")
    print(f"   - Projected Stop Loss: ${sl_price:.2f}")
    print(f"   - Projected Take Profit: ${tp_price:.2f}")
    
    min_margin_for_1_contract = (mark_price * 0.001) / config.risk.max_leverage
    print(f"   - Min Margin needed for 1 BTCUSD contract at {config.risk.max_leverage}x leverage: ${min_margin_for_1_contract:.2f} USD")

    # 6. Live Engine Cycle Verification (Will it take entry right now?)
    print("\n[6] LIVE ENGINE RUN_CYCLE (ENTRY CHECK):")
    engine = SingleBotEngine(config, client)
    cycle = engine.run_cycle()
    print(f"   - Engine Action:   {cycle.get('action')}")
    if cycle.get("action") == "stay_flat":
        print(f"   - Why No Entry:    {cycle.get('flat_reason') or cycle.get('reason')}")
    elif cycle.get("action") in ["open_long", "open_short"]:
        print(f"   - 🎯 ENTRY TRIGGERED! Trade: {cycle.get('trade')}")
    elif cycle.get("error"):
        print(f"   - ⚠️ Cycle Error:  {cycle.get('error')}")

    # 7. Execution Engine & Product ID
    print("\n[7] EXECUTION ENGINE & PRODUCT ID:")
    exec_engine = ExecutionEngine(client)
    product_id = client.get_btc_product_id()
    print(f"   - BTC Product ID:  {product_id} ({client._btc_symbol})")
    print(f"   - Live Trading:    {config.delta.live_trading}")
    print(f"   - Paper Mode:      {config.paper_mode}")

    print("\n" + "=" * 65)
    print("🏁 SUMMARY OF FINDINGS COMPLETED")
    print("=" * 65)

if __name__ == "__main__":
    run_checks()
