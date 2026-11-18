"""
Instagram Graph API & Messenger Notification Service.
Sends automated Direct Messages (DMs) / alerts for market analysis, trade entries, exits, and PnL updates.
"""
import os
import logging
import requests

log = logging.getLogger("instagram")


class InstagramNotifier:
    def __init__(self):
        self.access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "EAGm6KHqlW7IBTNEZBnsTozGeHRBIhHzUvMkiPoSdq6RXh4oLwG9SZC12WZBXW7FE0FtsjAFCKMywg91UefpGJwyygRf35Yiki0cqazTB2CdJVbLuI3wVZCBcJFjqpkdHeW2sh79mgw2BU2KIvvEeUFTW8ZAdkxuKAeDZBE8eEJMH9iXgiX1IkZBgMtIB6GK4dpz5aCLdUj49aMdsONESIDTo8cFWuymrOHjMncFZBz4fslEHTxQv3ogFEwZDZD")
        self.ig_user_id = os.getenv("INSTAGRAM_USER_ID", "17841472775037140")
        self.recipient_id = os.getenv("INSTAGRAM_RECIPIENT_ID", "1440272061051862")
        self.api_url = f"https://graph.facebook.com/v21.0/{self.ig_user_id}/messages"

    def is_configured(self) -> bool:
        return bool(self.access_token and self.ig_user_id)

    def send_message(self, text: str) -> bool:
        if not self.is_configured():
            log.warning("Instagram credentials not fully configured. Skipping DM notification.")
            return False

        recipient = self.recipient_id if self.recipient_id and self.recipient_id != "your_recipient_ig_scoped_user_id" else self.ig_user_id

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "recipient": {"id": recipient},
            "message": {"text": text},
            "messaging_type": "RESPONSE"
        }

        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=10)
            if response.status_code >= 400:
                log.error("Failed to send Instagram DM [%d]: %s", response.status_code, response.text)
                return False
            log.info("Instagram DM notification sent successfully.")
            return True
        except Exception as e:
            log.error("Exception sending Instagram DM: %s", e)
            return False

    def notify_analysis(self, symbol: str, regime: str, score: float, price: float, rsi_val: float, adx_val: float) -> bool:
        text = (
            f"📊 [Complete Trade Auto] Market Analysis\n\n"
            f"• Symbol: {symbol}\n"
            f"• Price: ${price:,.2f}\n"
            f"• Regime: {regime}\n"
            f"• Signal Score: {score:+.2f}\n"
            f"• RSI(14): {rsi_val:.1f}\n"
            f"• ADX(14): {adx_val:.1f}"
        )
        return self.send_message(text)

    def notify_entry(self, symbol: str, side: str, price: float, qty: float, sl: float, tp: float) -> bool:
        text = (
            f"🟢 TRADE ENTRY EXECUTED\n\n"
            f"• Symbol: {symbol}\n"
            f"• Side: {side.upper()}\n"
            f"• Entry: ${price:,.2f}\n"
            f"• Qty: {qty} BTC\n"
            f"• SL: ${sl:,.2f}\n"
            f"• TP: ${tp:,.2f}"
        )
        return self.send_message(text)

    def notify_exit(self, symbol: str, side: str, entry_price: float, exit_price: float, pnl: float, reason: str) -> bool:
        emoji = "✅" if pnl >= 0 else "❌"
        text = (
            f"{emoji} TRADE EXIT / CLOSED\n\n"
            f"• Symbol: {symbol}\n"
            f"• Side: {side.upper()}\n"
            f"• Entry: ${entry_price:,.2f}\n"
            f"• Exit: ${exit_price:,.2f}\n"
            f"• Realized PnL: ${pnl:+,.2f} USDT\n"
            f"• Reason: {reason}"
        )
        return self.send_message(text)


instagram_notifier = InstagramNotifier()
