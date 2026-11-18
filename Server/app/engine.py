"""
Engine: The single bot loop running once per closed candle.
Orchestrates gates, regime detection, strategy voting, aggregator, risk sizing, and execution.
"""
import logging
import time
import pandas as pd
from typing import Optional, Dict, Any

from app.config import AppConfig
from app.delta_client import DeltaClient
from app.regime import detect_regime, MarketRegime
from app.strategies.trend_ema import TrendEmaStrategy
from app.strategies.range_rsi_bb import RangeRsiBbStrategy
from app.aggregator import Aggregator
from app.risk import RiskManager
from app.liquidity import LiquidityCalculator
from app.execution import ExecutionEngine
from app.indicators import atr, adx, rolling_percentile, bollinger_bands, ema

log = logging.getLogger("engine")


class SingleBotEngine:
    def __init__(self, cfg: AppConfig, client: DeltaClient):
        self.cfg = cfg
        self.client = client
        self.risk_manager = RiskManager(cfg.risk, initial_equity=10000.0)
        self.liquidity_calc = LiquidityCalculator(max_slippage_pct=cfg.risk.max_slippage_pct)
        self.execution = ExecutionEngine(client)
        self.aggregator = Aggregator([TrendEmaStrategy(), RangeRsiBbStrategy()], weights=[1.0, 1.0])

        self.btc_product_id: Optional[int] = None
        self.btc_symbol: str = "BTCUSD"
        self.is_running: bool = True

    def initialize(self):
        self.btc_product_id = self.client.get_btc_product_id()
        self.btc_symbol = self.client._btc_symbol
        log.info("SingleBotEngine initialized for product_id=%d (%s)", self.btc_product_id, self.btc_symbol)

        # Sync wallet balance if real keys present
        try:
            bals = self.client.get_wallet_balances()
            for b in bals:
                if b.get("asset") in ("USDT", "USD", "USDC"):
                    bal = float(b.get("balance", b.get("free", 10000.0)))
                    if bal > 0:
                        self.risk_manager.equity = bal
                        self.risk_manager.starting_equity = bal
                        self.risk_manager.peak_equity = bal
                        log.info("Synced starting equity from wallet balance: $%.2f", bal)
                        break
        except Exception as e:
            log.warning("Could not fetch wallet balance for equity sync (using default $10,000): %s", e)

    def run_cycle(self) -> Dict[str, Any]:
        """
        Runs one evaluation cycle (once per closed candle).
        """
        if self.btc_product_id is None:
            self.initialize()

        timestamp = int(time.time())
        result = {"timestamp": timestamp, "status": "ok", "action": "none"}

        # Diagnostic variables
        candles_15m_count = 0
        candles_1h_count = 0
        last_closed_15m_time = None
        adx_val = 0.0
        atr_pct_val = 0.0
        bb_bw_pct_val = 0.0
        trend_1h_dir = "NEUTRAL"
        ema50_val = 0.0
        ema200_val = 0.0
        votes = {}
        final_score = 0.0
        regime_str = "UNKNOWN"
        gates_results = {}
        first_blocking_gate = None
        final_decision = "FLAT"
        flat_reason = "NONE"

        try:
            # 1. Fetch latest candles & orderbook
            df_15m = self.client.get_candles(symbol=self.btc_symbol, resolution="15m", limit=200)
            df_1h = self.client.get_candles(symbol=self.btc_symbol, resolution="1h", limit=100)
            orderbook = self.client.get_l2_orderbook(self.btc_product_id) # type: ignore

            candles_15m_count = len(df_15m)
            candles_1h_count = len(df_1h)

            if df_15m.empty:
                flat_reason = "Empty 15m candle data"
                result = {"status": "error", "reason": flat_reason}
                return result

            last_closed_15m_time = int(df_15m["time"].iloc[-1]) if "time" in df_15m.columns else timestamp
            price = float(df_15m["close"].iloc[-1])
            atr_val = float(atr(df_15m, 14).iloc[-1])

            # Calculate regime component values
            adx_series = adx(df_15m, period=14)
            adx_val = float(adx_series.iloc[-1]) if not adx_series.empty else 0.0

            atr_series = atr(df_15m, period=14)
            atr_pct_series = rolling_percentile(atr_series, window=100)
            atr_pct_val = float(atr_pct_series.iloc[-1]) if not atr_pct_series.empty else 50.0

            _, _, _, bb_bandwidth = bollinger_bands(df_15m["close"], period=20, std_dev=2.0)
            bb_bw_pct_series = rolling_percentile(bb_bandwidth, window=100)
            bb_bw_pct_val = float(bb_bw_pct_series.iloc[-1]) if not bb_bw_pct_series.empty else 50.0

            # 1h Trend values
            if df_1h is not None and len(df_1h) >= 50:
                h_fast = ema(df_1h["close"], 50)
                h_slow = ema(df_1h["close"], 200) if len(df_1h) >= 200 else ema(df_1h["close"], 50)
                ema50_val = float(h_fast.iloc[-1])
                ema200_val = float(h_slow.iloc[-1])
                if ema50_val > ema200_val:
                    trend_1h_dir = "BULLISH"
                elif ema50_val < ema200_val:
                    trend_1h_dir = "BEARISH"
                else:
                    trend_1h_dir = "SIDEWAYS"

            # 2. Reconcile position with exchange (Source of Truth)
            active_position = self.execution.reconcile_position(self.btc_product_id) # type: ignore

            is_halted_flag, halt_reason_str = self.risk_manager.check_gates()
            gates_results = {
                "is_halted": self.risk_manager.is_halted,
                "halt_reason": self.risk_manager.halt_reason,
                "consecutive_losses": self.risk_manager.consecutive_losses,
                "cooldown_bars": self.risk_manager.cfg.cooldown_bars,
                "passed": is_halted_flag,
                "gate_reason": halt_reason_str
            }

            if not is_halted_flag:
                if self.risk_manager.is_halted:
                    first_blocking_gate = f"Risk Halt: {self.risk_manager.halt_reason}"
                elif self.risk_manager.consecutive_losses >= self.risk_manager.cfg.cooldown_bars:
                    first_blocking_gate = f"Cooldown active ({self.risk_manager.consecutive_losses} losses >= {self.risk_manager.cfg.cooldown_bars})"
                else:
                    first_blocking_gate = halt_reason_str

            if active_position is not None:
                final_decision = "IN_POSITION"
                flat_reason = "Already in active position"
                result["action"] = "in_position"
                result["position"] = active_position
                result["diagnostic"] = self._build_diagnostic(
                    timestamp, last_closed_15m_time, candles_15m_count, candles_1h_count,
                    adx_val, atr_pct_val, bb_bw_pct_val, trend_1h_dir, ema50_val, ema200_val,
                    votes, final_score, regime_str, gates_results, first_blocking_gate, final_decision, flat_reason
                )
                return result

            # 3. Check Risk Gates
            passed, reason = self.risk_manager.check_gates()
            if not passed:
                final_decision = "FLAT"
                flat_reason = f"Gate blocked: {reason}"
                result["action"] = "halted"
                result["reason"] = reason
                log.info("Gate failed: %s", reason)
                result["diagnostic"] = self._build_diagnostic(
                    timestamp, last_closed_15m_time, candles_15m_count, candles_1h_count,
                    adx_val, atr_pct_val, bb_bw_pct_val, trend_1h_dir, ema50_val, ema200_val,
                    votes, final_score, regime_str, gates_results, first_blocking_gate, final_decision, flat_reason
                )
                return result

            # 4. Aggregator Decision (Regime + Strategies + 1h Trend Filter)
            # Collect individual strategy votes for logging
            regime = detect_regime(df_15m)
            regime_str = regime.value
            for strat, weight in zip(self.aggregator.strategies, self.aggregator.weights):
                s_vote = strat.vote(df_15m, df_1h)
                votes[strat.name] = {"vote": s_vote, "weight": weight, "allowed": regime in strat.allowed_regimes}

            action, score, regime = self.aggregator.decide(df_15m, df_1h)
            final_score = score
            result["regime"] = regime.value
            result["score"] = score
            result["decision"] = action

            if action == "flat":
                final_decision = "FLAT"
                if score == 0.0 and regime in (MarketRegime.CHAOS, MarketRegime.UNKNOWN):
                    flat_reason = f"Regime is {regime.value} (Blocked)"
                elif abs(score) < 0.6:
                    flat_reason = f"Aggregator score {score:.2f} did not meet threshold (+/- 0.6)"
                else:
                    flat_reason = "Aggregator or HTF trend filter vetoed trade"

                result["action"] = "stay_flat"
                result["diagnostic"] = self._build_diagnostic(
                    timestamp, last_closed_15m_time, candles_15m_count, candles_1h_count,
                    adx_val, atr_pct_val, bb_bw_pct_val, trend_1h_dir, ema50_val, ema200_val,
                    votes, final_score, regime_str, gates_results, first_blocking_gate, final_decision, flat_reason
                )
                return result

            # 5. Risk Sizing & Stop Loss / Take Profit Calculation
            is_buy = (action == "long")
            contracts, sl, tp = self.risk_manager.calculate_position_size(price, atr_val, self.risk_manager.equity)

            if action == "short":
                sl_dist = sl - price
                tp_dist = price - tp
                sl = price + sl_dist
                tp = price - tp_dist

            # 6. Liquidity Check (Orderbook Slippage)
            liq_analysis = self.liquidity_calc.analyze_orderbook(orderbook, contracts, is_buy)
            result["liquidity"] = liq_analysis

            if not liq_analysis["can_execute"]:
                final_decision = "FLAT"
                flat_reason = f"Liquidity check blocked: {liq_analysis['reason']}"
                first_blocking_gate = first_blocking_gate or liq_analysis["reason"]
                result["action"] = "blocked_by_liquidity"
                result["reason"] = liq_analysis["reason"]
                log.warning("Trade blocked by liquidity: %s", liq_analysis["reason"])
                result["diagnostic"] = self._build_diagnostic(
                    timestamp, last_closed_15m_time, candles_15m_count, candles_1h_count,
                    adx_val, atr_pct_val, bb_bw_pct_val, trend_1h_dir, ema50_val, ema200_val,
                    votes, final_score, regime_str, gates_results, first_blocking_gate, final_decision, flat_reason
                )
                return result

            # 7. Execute Order on Exchange
            final_decision = action.upper()
            flat_reason = "NONE"

            if self.cfg.paper_mode or not self.cfg.delta.api_key:
                log.info("[PAPER MODE] Simulated %s trade: %d contracts at %.2f (SL=%.2f, TP=%.2f)",
                         action.upper(), contracts, price, sl, tp)
                result["action"] = "simulated_trade_executed"
                result["trade"] = {"side": action, "contracts": contracts, "price": price, "sl": sl, "tp": tp}
            else:
                exec_res = self.execution.execute_bracket_order(
                    product_id=self.btc_product_id, # type: ignore
                    side=action,
                    contracts=contracts,
                    stop_loss_price=sl,
                    take_profit_price=tp
                )
                result["action"] = "live_trade_executed"
                result["execution"] = exec_res

            result["diagnostic"] = self._build_diagnostic(
                timestamp, last_closed_15m_time, candles_15m_count, candles_1h_count,
                adx_val, atr_pct_val, bb_bw_pct_val, trend_1h_dir, ema50_val, ema200_val,
                votes, final_score, regime_str, gates_results, first_blocking_gate, final_decision, flat_reason
            )

        except Exception as e:
            log.error("Error in SingleBotEngine cycle: %s", e)
            result["status"] = "error"
            result["reason"] = str(e)
            result["diagnostic"] = {
                "timestamp": timestamp,
                "error": str(e)
            }

        return result

    def _build_diagnostic(self, timestamp, last_closed_15m_time, candles_15m_count, candles_1h_count,
                          adx_val, atr_pct_val, bb_bw_pct_val, trend_1h_dir, ema50_val, ema200_val,
                          votes, final_score, regime_str, gates_results, first_blocking_gate, final_decision, flat_reason) -> Dict[str, Any]:
        return {
            "timestamp": timestamp,
            "last_closed_15m_candle_time": last_closed_15m_time,
            "candles_loaded": {
                "15m": candles_15m_count,
                "1h": candles_1h_count
            },
            "regime": regime_str,
            "regime_values": {
                "adx": round(adx_val, 2),
                "atr_percentile": round(atr_pct_val, 2),
                "bollinger_bandwidth_percentile": round(bb_bw_pct_val, 2)
            },
            "trend_1h": {
                "direction": trend_1h_dir,
                "ema50": round(ema50_val, 2),
                "ema200": round(ema200_val, 2)
            },
            "strategy_votes": votes,
            "aggregation": {
                "final_score": round(final_score, 4),
                "long_threshold": 0.6,
                "short_threshold": -0.6
            },
            "gates": gates_results,
            "first_blocking_gate": first_blocking_gate,
            "final_decision": final_decision,
            "flat_reason": flat_reason
        }
