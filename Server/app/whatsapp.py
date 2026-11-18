"""
WhatsApp Notification Service via Meta Cloud API (Graph API).
Sends alerts for market analysis, trade entries, exits, and PnL updates.
"""
import os
import logging
import requests
from typing import Dict, Any, Optional

log = logging.getLogger("whatsapp")


class WhatsAppNotifier:
    def __init__(self):
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.recipient_phone = os.getenv("WHATSAPP_RECIPIENT_PHONE", "")
        self.api_url = f"https://graph.facebook.com/v21.0/{self.phone_number_id}/messages"

    def is_configured(self) -> bool:
        return bool(self.access_token and self.phone_number_id and self.recipient_phone)

    def send_message(self, text: str) -> bool:
        if not self.is_configured():
            log.warning("WhatsApp credentials not configured. Skipping notification.")
            return False

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": self.recipient_phone,
            "type": "text",
            "text": {"body": text},
        }

        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=10)
            if response.status_code >= 400:
                log.error("Failed to send WhatsApp message [%d]: %s", response.status_code, response.text)
                return False
            log.info("WhatsApp notification sent successfully.")
            return True
        except Exception as e:
            log.error("Exception sending WhatsApp message: %s", e)
            return False

    def notify_analysis(self, symbol: str, regime: str, score: float, price: float, rsi_val: float, adx_val: float) -> bool:
        text = (
            f"📊 *Complete Trade Auto · Market Analysis*\n\n"
            f"• *Symbol:* {symbol}\n"
            f"• *Price:* ${price:,.2f}\n"
            f"• *Regime:* {regime}\n"
            f"• *Signal Score:* {score:+.2f}\n"
            f"• *RSI(14):* {rsi_val:.1f}\n"
            f"• *ADX(14):* {adx_val:.1f}\n"
            f"• *Status:* Monitoring / Waiting for threshold..."
        )
        return self.send_message(text)

    def notify_entry(self, symbol: str, side: str, price: float, qty: float, sl: float, tp: float) -> bool:
        emoji = "🟢" if side.lower() in ("long", "buy") else "🔴"
        text = (
            f"{emoji} *TRADE ENTRY EXECUTED*\n\n"
            f"• *Symbol:* {symbol}\n"
            f"• *Side:* {side.upper()}\n"
            f"• *Entry Price:* ${price:,.2f}\n"
            f"• *Quantity:* {qty} BTC\n"
            f"• *Stop Loss:* ${sl:,.2f}\n"
            f"• *Take Profit:* ${tp:,.2f}\n"
            f"• *Mode:* Active Bracket Order"
        )
        return self.send_message(text)

    def notify_exit(self, symbol: str, side: str, entry_price: float, exit_price: float, pnl: float, reason: str) -> bool:
        emoji = "✅" if pnl >= 0 else "❌"
        text = (
            f"{emoji} *TRADE EXIT / CLOSED*\n\n"
            f"• *Symbol:* {symbol}\n"
            f"• *Side:* {side.upper()}\n"
            f"• *Entry Price:* ${entry_price:,.2f}\n"
            f"• *Exit Price:* ${exit_price:,.2f}\n"
            f"• *Realized PnL:* ${pnl:+,.2f} USDT\n"
            f"• *Exit Reason:* {reason}"
        )
        return self.send_message(text)


whatsapp_notifier = WhatsAppNotifier()
