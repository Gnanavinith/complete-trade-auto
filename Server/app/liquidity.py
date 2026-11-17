"""
Liquidity Calculator: computes spread, depth, imbalance, and estimated slippage by walking the L2 orderbook.
"""
import logging
from typing import Dict, Any, Optional

log = logging.getLogger("liquidity")


class LiquidityCalculator:
    def __init__(self, max_slippage_pct: float = 0.002):
        self.max_slippage_pct = max_slippage_pct

    def analyze_orderbook(self, orderbook: Dict[str, Any], order_size_contracts: int, is_buy: bool) -> Dict[str, Any]:
        """
        Analyzes L2 orderbook (Delta format: {"buy": [[price, size], ...], "sell": [[price, size], ...], ...})
        Returns metrics: spread, depth_01_pct, depth_05_pct, imbalance, estimated_slippage_pct, can_execute.
        """
        bids = orderbook.get("buy", orderbook.get("bids", []))
        asks = orderbook.get("sell", orderbook.get("asks", []))

        if not bids or not asks:
            return {
                "spread": 0.0,
                "depth_01": 0.0,
                "depth_05": 0.0,
                "imbalance": 0.0,
                "estimated_slippage_pct": 0.0,
                "can_execute": False,
                "reason": "Empty orderbook"
            }

        # Sort bids descending, asks ascending
        try:
            bids = sorted(bids, key=lambda x: float(x[0]), reverse=True)
            asks = sorted(asks, key=lambda x: float(x[0]), reverse=False)
        except Exception:
            pass

        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid_price = (best_bid + best_ask) / 2.0
        spread = best_ask - best_bid
        spread_pct = spread / mid_price if mid_price > 0 else 0.0

        # Depth within +/- 0.1% and +/- 0.5%
        depth_01_bids = sum(float(b[1]) for b in bids if float(b[0]) >= mid_price * 0.999)
        depth_01_asks = sum(float(a[1]) for a in asks if float(a[0]) <= mid_price * 1.001)
        depth_01 = depth_01_bids + depth_01_asks

        depth_05_bids = sum(float(b[1]) for b in bids if float(b[0]) >= mid_price * 0.995)
        depth_05_asks = sum(float(a[1]) for a in asks if float(a[0]) <= mid_price * 1.005)
        depth_05 = depth_05_bids + depth_05_asks

        total_bid_qty = sum(float(b[1]) for b in bids[:20])
        total_ask_qty = sum(float(a[1]) for a in asks[:20])
        imbalance = (total_bid_qty - total_ask_qty) / (total_bid_qty + total_ask_qty) if (total_bid_qty + total_ask_qty) > 0 else 0.0

        # Estimate fill price by walking the book for order size (contracts * 0.001 BTC)
        target_btc_qty = order_size_contracts * 0.001
        book_side = asks if is_buy else bids
        filled_qty = 0.0
        total_cost = 0.0

        for level in book_side:
            p = float(level[0])
            sz = float(level[1])
            take_qty = min(sz, target_btc_qty - filled_qty)
            total_cost += p * take_qty
            filled_qty += take_qty
            if filled_qty >= target_btc_qty:
                break

        if filled_qty < target_btc_qty and book_side:
            # fallback if book is thin
            avg_fill_price = float(book_side[-1][0])
        elif filled_qty > 0:
            avg_fill_price = total_cost / filled_qty
        else:
            avg_fill_price = best_ask if is_buy else best_bid

        benchmark_price = best_ask if is_buy else best_bid
        slippage_pct = abs(avg_fill_price - benchmark_price) / benchmark_price if benchmark_price > 0 else 0.0

        can_execute = slippage_pct <= self.max_slippage_pct

        return {
            "spread": spread,
            "spread_pct": spread_pct,
            "depth_01": depth_01,
            "depth_05": depth_05,
            "imbalance": imbalance,
            "estimated_fill_price": avg_fill_price,
            "estimated_slippage_pct": slippage_pct,
            "can_execute": can_execute,
            "reason": "OK" if can_execute else f"Slippage {slippage_pct*100:.3f}% exceeds max allowed {self.max_slippage_pct*100:.3f}%"
        }
