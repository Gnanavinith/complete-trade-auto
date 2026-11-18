"""
Backtest Script: Runs the SingleBotEngine over historical candles and outputs evaluation metrics.
"""
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Optional

from app.aggregator import Aggregator
from app.strategies.trend_ema import TrendEmaStrategy
from app.strategies.range_rsi_bb import RangeRsiBbStrategy
from app.risk import RiskManager, RiskConfig
from app.indicators import atr

log = logging.getLogger("backtester")


class Backtester:
    def __init__(self, df_15m: pd.DataFrame, df_1h: Optional[pd.DataFrame] = None, initial_equity: float = 10000.0, taker_fee_pct: float = 0.0005, slippage_pct: float = 0.0002):
        self.df_15m = df_15m.copy()
        self.df_1h = df_1h.copy() if df_1h is not None else None
        self.initial_equity = initial_equity
        self.taker_fee_pct = taker_fee_pct
        self.slippage_pct = slippage_pct
        self.risk_manager = RiskManager(RiskConfig(), initial_equity=initial_equity)
        self.aggregator = Aggregator([TrendEmaStrategy(), RangeRsiBbStrategy()], weights=[1.0, 1.0])

    def run(self) -> Dict[str, Any]:
        equity = self.initial_equity
        trades: List[Dict[str, Any]] = []
        equity_curve: List[float] = [equity]

        position = None
        warmup = 50
        n = len(self.df_15m)

        cycles_evaluated = 0
        flat_reasons_count: Dict[str, int] = {}
        trades_taken = 0

        for i in range(warmup, n):
            cycles_evaluated += 1
            current_bar = self.df_15m.iloc[:i+1]
            price = float(current_bar["close"].iloc[-1])
            atr_val = float(atr(current_bar, 14).iloc[-1])
            timestamp = current_bar["time"].iloc[-1] if "time" in current_bar.columns else i

            # 1. Manage active position (check SL / TP)
            if position is not None:
                side = position["side"]
                entry_price = position["entry_price"]
                sl = position["stop_loss"]
                tp = position["take_profit"]
                contracts = position["contracts"]
                contract_val_btc = contracts * 0.001

                hit_exit = False
                exit_price = price
                exit_reason = "HOLD"

                if side == "long":
                    if current_bar["low"].iloc[-1] <= sl:
                        exit_price = sl * (1 - self.slippage_pct)
                        exit_reason = "STOP_LOSS"
                        hit_exit = True
                    elif current_bar["high"].iloc[-1] >= tp:
                        exit_price = tp * (1 - self.slippage_pct)
                        exit_reason = "TAKE_PROFIT"
                        hit_exit = True
                else:
                    if current_bar["high"].iloc[-1] >= sl:
                        exit_price = sl * (1 + self.slippage_pct)
                        exit_reason = "STOP_LOSS"
                        hit_exit = True
                    elif current_bar["low"].iloc[-1] <= tp:
                        exit_price = tp * (1 + self.slippage_pct)
                        exit_reason = "TAKE_PROFIT"
                        hit_exit = True

                if hit_exit:
                    pnl_raw = (exit_price - entry_price) * contract_val_btc if side == "long" else (entry_price - exit_price) * contract_val_btc
                    fee = (entry_price + exit_price) * contract_val_btc * self.taker_fee_pct
                    net_pnl = pnl_raw - fee

                    equity += net_pnl
                    self.risk_manager.record_trade_result(net_pnl)

                    trades.append({
                        "entry_time": position["entry_time"],
                        "exit_time": timestamp,
                        "side": side,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "exit_reason": exit_reason,
                        "contracts": contracts,
                        "net_pnl": net_pnl,
                        "return_pct": (net_pnl / (entry_price * contract_val_btc)) * 100
                    })
                    position = None

            # 2. Check gates & open new position if FLAT via Aggregator decision
            if position is None:
                passed, gate_reason = self.risk_manager.check_gates()
                if not passed:
                    r_key = f"Gate Blocked: {gate_reason}"
                    flat_reasons_count[r_key] = flat_reasons_count.get(r_key, 0) + 1
                else:
                    # Slice 1h dataframe up to current timestamp if available
                    df_1h_slice = None
                    if self.df_1h is not None and not self.df_1h.empty and "time" in self.df_1h.columns:
                        df_1h_slice = self.df_1h[self.df_1h["time"] <= timestamp]
                        if df_1h_slice.empty:
                            df_1h_slice = self.df_1h.iloc[:50] # fallback

                    action, score, regime = self.aggregator.decide(current_bar, df_1h_slice)
                    if action == "flat":
                        if regime.value in ("CHAOS", "UNKNOWN"):
                            r_key = f"Regime: {regime.value}"
                        elif abs(score) < 0.6:
                            r_key = f"Score Threshold Unmet ({score:.2f})"
                        else:
                            r_key = "HTF Trend / Veto Filter"
                        flat_reasons_count[r_key] = flat_reasons_count.get(r_key, 0) + 1
                    else:
                        trades_taken += 1
                        contracts, sl, tp = self.risk_manager.calculate_position_size(price, atr_val, equity)
                        if action == "long":
                            entry_price = price * (1 + self.slippage_pct)
                            position = {
                                "side": "long",
                                "entry_price": entry_price,
                                "stop_loss": sl,
                                "take_profit": tp,
                                "contracts": contracts,
                                "entry_time": timestamp,
                            }
                        elif action == "short":
                            sl_dist = sl - price
                            tp_dist = price - tp
                            sl = price + sl_dist
                            tp = price - tp_dist
                            entry_price = price * (1 - self.slippage_pct)
                            position = {
                                "side": "short",
                                "entry_price": entry_price,
                                "stop_loss": sl,
                                "take_profit": tp,
                                "contracts": contracts,
                                "entry_time": timestamp,
                            }

            equity_curve.append(equity)

        total_trades = len(trades)
        winning_trades = [t for t in trades if t["net_pnl"] > 0]
        losing_trades = [t for t in trades if t["net_pnl"] <= 0]
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0.0
        net_pnl = equity - self.initial_equity
        gross_profit = sum(t["net_pnl"] for t in winning_trades)
        gross_loss = abs(sum(t["net_pnl"] for t in losing_trades))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        peak = self.initial_equity
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        return {
            "cycles_evaluated": cycles_evaluated,
            "flat_reasons_count": flat_reasons_count,
            "trades_taken": trades_taken,
            "initial_equity": self.initial_equity,
            "final_equity": round(equity, 2),
            "net_pnl": round(net_pnl, 2),
            "return_pct": round((net_pnl / self.initial_equity) * 100, 2),
            "total_trades": total_trades,
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "inf",
            "max_drawdown_pct": round(max_dd * 100, 2),
            "trades": trades,
        }
