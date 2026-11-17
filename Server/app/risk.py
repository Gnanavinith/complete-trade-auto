"""
Risk Manager: position sizing, stops, daily loss cap, kill switch, leverage limits.
"""
import logging
from typing import Optional, Dict, Any
from app.config import RiskConfig

log = logging.getLogger("risk")


class RiskManager:
    def __init__(self, cfg: RiskConfig, initial_equity: float = 10000.0):
        self.cfg = cfg
        self.equity = initial_equity
        self.starting_equity = initial_equity
        self.peak_equity = initial_equity
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.is_halted = False
        self.halt_reason = ""

    def update_equity(self, current_equity: float):
        self.equity = current_equity
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

        drawdown_pct = (self.peak_equity - self.equity) / self.peak_equity
        if drawdown_pct >= self.cfg.max_drawdown_pct:
            self.is_halted = True
            self.halt_reason = f"Max drawdown hit: {drawdown_pct*100:.2f}% >= {self.cfg.max_drawdown_pct*100}%"
            log.critical("KILL SWITCH TRIGGERED: %s", self.halt_reason)

        daily_loss_pct = -self.daily_pnl / self.starting_equity if self.starting_equity > 0 else 0
        if daily_loss_pct >= self.cfg.daily_loss_cap_pct:
            self.is_halted = True
            self.halt_reason = f"Daily loss cap hit: {daily_loss_pct*100:.2f}% >= {self.cfg.daily_loss_cap_pct*100}%"
            log.critical("KILL SWITCH TRIGGERED: %s", self.halt_reason)

    def check_gates(self) -> tuple[bool, str]:
        if self.is_halted:
            return False, f"Risk Halt Active: {self.halt_reason}"
        if self.consecutive_losses >= self.cfg.cooldown_bars:
            return False, f"Cooldown active after {self.consecutive_losses} consecutive losses"
        return True, "OK"

    def calculate_position_size(self, price: float, atr_value: float, equity: float) -> tuple[int, float, float]:
        """
        Fixed-fractional risk sizing for BTCUSD perpetual (contract unit = 0.001 BTC):
        Risk amount = equity * risk_per_trade_pct (e.g. 0.5%)
        Stop loss distance = 1.5 * ATR
        Contract size = 0.001 BTC
        Risk per contract = 0.001 * SL distance (in USD)
        """
        risk_amount = equity * self.cfg.risk_per_trade_pct
        sl_distance = 1.5 * atr_value
        if sl_distance <= 0 or price <= 0:
            return 0, 0.0, 0.0

        contract_unit_btc = 0.001
        risk_per_contract = contract_unit_btc * sl_distance
        if risk_per_contract <= 0:
            return 0, 0.0, 0.0

        num_contracts = int(risk_amount / risk_per_contract)
        if num_contracts < 1:
            num_contracts = 1  # Minimum 1 contract (0.001 BTC)

        stop_loss_price = price - sl_distance
        take_profit_price = price + (2.5 * atr_value)

        return num_contracts, stop_loss_price, take_profit_price

    def record_trade_result(self, pnl: float):
        self.daily_pnl += pnl
        self.equity += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
