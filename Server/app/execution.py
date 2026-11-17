"""
Execution Engine: places orders, manages bracket orders (Entry + SL + TP),
and reconciles with actual exchange state.
"""
import logging
from typing import Optional, Dict, Any, List
from app.delta_client import DeltaClient

log = logging.getLogger("execution")


class ExecutionEngine:
    def __init__(self, client: DeltaClient):
        self.client = client

    def reconcile_position(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Queries Delta Exchange for open positions on product_id.
        Exchange is the source of truth.
        """
        try:
            positions = self.client.get_positions(product_id=product_id)
            for pos in positions:
                if int(pos.get("product_id", 0)) == product_id:
                    size = float(pos.get("size", 0))
                    if size != 0:
                        return {
                            "product_id": product_id,
                            "size": abs(size),
                            "side": "long" if size > 0 else "short",
                            "entry_price": float(pos.get("entry_price", 0)),
                            "liquidation_price": float(pos.get("liquidation_price", 0)),
                            "unrealized_pnl": float(pos.get("unrealized_pnl", 0)),
                        }
            return None
        except Exception as e:
            log.error("Failed to reconcile position with Delta: %s", e)
            return None

    def execute_bracket_order(self, product_id: int, side: str, contracts: int, stop_loss_price: float, take_profit_price: float) -> Dict[str, Any]:
        """
        Places market entry order along with bracket stop-loss and take-profit orders on Delta.
        """
        try:
            log.info("Executing %s order for %d contracts on product_id=%d (SL=%.2f, TP=%.2f)...",
                     side.upper(), contracts, product_id, stop_loss_price, take_profit_price)

            # 1. Place main entry order (Market)
            entry_res = self.client.place_order(
                product_id=product_id,
                size=contracts,
                side="buy" if side.lower() == "long" else "sell",
                order_type="market"
            )

            log.info("Entry order placed successfully: %s", entry_res)

            # 2. Place Stop Loss order
            sl_side = "sell" if side.lower() == "long" else "buy"
            sl_res = self.client.place_order(
                product_id=product_id,
                size=contracts,
                side=sl_side,
                order_type="stop_market", # or stop order
                stop_order_price=stop_loss_price
            )
            log.info("Stop Loss order placed successfully: %s", sl_res)

            # 3. Place Take Profit order
            tp_res = self.client.place_order(
                product_id=product_id,
                size=contracts,
                side=sl_side,
                order_type="limit_market", # or limit TP
                limit_price=take_profit_price
            )
            log.info("Take Profit order placed successfully: %s", tp_res)

            return {
                "success": True,
                "entry": entry_res,
                "stop_loss": sl_res,
                "take_profit": tp_res,
            }

        except Exception as e:
            log.error("Failed to execute bracket order: %s", e)
            return {
                "success": False,
                "error": str(e)
            }
