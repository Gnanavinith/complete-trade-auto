"""
Google Gemini AI Market Analyst & Notification Dispatcher.
Integrates Google AI Studio / Gemini API to analyze market metrics,
generate institutional-grade commentary, and dispatch alerts to Instagram & WhatsApp.
"""

import os
import time
import logging
import requests
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("ai_analyst")


class GeminiMarketAnalyst:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
        self.fallback_model = "gemini-3.5-flash-lite"
        self.latest_analysis: Optional[Dict[str, Any]] = None

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _call_gemini(self, prompt: str) -> Optional[str]:
        if not self.is_configured():
            log.warning("GEMINI_API_KEY is not configured.")
            return None

        models_to_try = [self.model, self.fallback_model]
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 600,
            }
        }

        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            try:
                res = requests.post(url, json=payload, timeout=12)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                log.warning("Gemini model %s returned status %d: %s", model_name, res.status_code, res.text[:200])
            except Exception as e:
                log.warning("Gemini model %s failed: %s", model_name, e)

        return None

    def analyze_market(
        self,
        symbol: str = "BTCUSD",
        price: float = 65000.0,
        regime: str = "TREND",
        rsi: float = 50.0,
        adx: float = 25.0,
        ema_fast: float = 0.0,
        ema_slow: float = 0.0,
        trend_1h: str = "BULLISH",
        score: float = 0.0,
        orderbook: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Runs deep AI market analysis over the latest quantitative parameters.
        """
        prompt = (
            f"You are a professional algorithmic cryptocurrency trading analyst for Bitcoin Perpetual futures on Delta Exchange.\n"
            f"Current quantitative market data:\n"
            f"- Symbol: {symbol}\n"
            f"- Current Price: ${price:,.2f}\n"
            f"- Market Regime: {regime}\n"
            f"- 15m RSI(14): {rsi:.1f}\n"
            f"- 15m ADX(14): {adx:.1f} (Trend strength)\n"
            f"- EMA Cross: Fast(9)=${ema_fast:,.2f} vs Slow(21)=${ema_slow:,.2f}\n"
            f"- 1h Higher Timeframe Trend: {trend_1h}\n"
            f"- Strategy Aggregator Signal Score: {score:+.2f} (-1.0 max short to +1.0 max long)\n\n"
            f"Provide a structured analysis in exactly the following format:\n"
            f"BIAS: [BULLISH | BEARISH | NEUTRAL]\n"
            f"CONFIDENCE: [e.g. 80%]\n"
            f"KEY_SUPPORT: [e.g. $89,500]\n"
            f"KEY_RESISTANCE: [e.g. $91,800]\n"
            f"SUMMARY: [One concise sentence summarizing the market stance]\n"
            f"INSIGHTS:\n"
            f"- [Bullet 1: Momentum & indicators evaluation]\n"
            f"- [Bullet 2: Support/Resistance & liquidity takeaway]\n"
            f"- [Bullet 3: Tactical advice for the automated bot (e.g. buy dips, hold flat, trail SL)]\n"
        )

        raw_text = self._call_gemini(prompt)

        bias = "NEUTRAL"
        confidence = "70%"
        key_support = f"${price * 0.98:,.0f}"
        key_resistance = f"${price * 1.02:,.0f}"
        summary = f"BTC trading at ${price:,.2f} in {regime} regime."
        insights = []

        if raw_text:
            lines = raw_text.splitlines()
            for line in lines:
                l = line.strip()
                if l.startswith("BIAS:"):
                    bias = l.replace("BIAS:", "").strip().upper()
                elif l.startswith("CONFIDENCE:"):
                    confidence = l.replace("CONFIDENCE:", "").strip()
                elif l.startswith("KEY_SUPPORT:"):
                    key_support = l.replace("KEY_SUPPORT:", "").strip()
                elif l.startswith("KEY_RESISTANCE:"):
                    key_resistance = l.replace("KEY_RESISTANCE:", "").strip()
                elif l.startswith("SUMMARY:"):
                    summary = l.replace("SUMMARY:", "").strip()
                elif l.startswith("- ") or l.startswith("• "):
                    insights.append(l[2:].strip())

        if not insights and raw_text:
            insights = [line.strip() for line in raw_text.splitlines() if line.strip() and not line.startswith(("BIAS:", "CONFIDENCE:", "KEY_", "SUMMARY:"))][:3]

        if not insights:
            insights = [
                f"Market regime identified as {regime} with ADX at {adx:.1f}.",
                f"RSI currently at {rsi:.1f} indicates {'overbought' if rsi > 70 else 'oversold' if rsi < 30 else 'balanced'} momentum.",
                f"Strategy signal score is {score:+.2f} with 1h higher-timeframe {trend_1h}.",
            ]

        analysis = {
            "symbol": symbol,
            "price": price,
            "regime": regime,
            "bias": bias,
            "confidence": confidence,
            "key_support": key_support,
            "key_resistance": key_resistance,
            "summary": summary,
            "insights": insights,
            "raw_text": raw_text or summary,
            "timestamp": int(time.time()),
            "iso_time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "model": self.model,
        }

        self.latest_analysis = analysis
        log.info("Gemini AI Market Analysis completed: Bias=%s (%s), Summary=%s", bias, confidence, summary)
        return analysis

    def format_for_messenger(self, analysis: Dict[str, Any]) -> str:
        """Formats analysis for Instagram Direct and WhatsApp messaging."""
        bias_emoji = "🟢" if "BULL" in analysis.get("bias", "") else "🔴" if "BEAR" in analysis.get("bias", "") else "🟡"
        insights_str = "\n".join([f"• {i}" for i in analysis.get("insights", [])])

        return (
            f"🤖 *AI MARKET INTELLIGENCE* (Google Gemini)\n\n"
            f"• *Asset:* {analysis.get('symbol')} (${analysis.get('price', 0):,.2f})\n"
            f"• *Stance:* {bias_emoji} {analysis.get('bias')} ({analysis.get('confidence')})\n"
            f"• *Regime:* {analysis.get('regime')}\n"
            f"• *Levels:* Supp: {analysis.get('key_support')} | Res: {analysis.get('key_resistance')}\n\n"
            f"📌 *Summary:* {analysis.get('summary')}\n\n"
            f"💡 *Key Insights:*\n{insights_str}\n\n"
            f"⏱️ _{analysis.get('iso_time')}_"
        )

    def dispatch_notifications(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches formatted message to Instagram and WhatsApp."""
        msg = self.format_for_messenger(analysis)
        results = {"instagram": False, "whatsapp": False, "details": {}}

        # Instagram
        try:
            from app.instagram import instagram_notifier
            if instagram_notifier.is_configured():
                ig_ok, ig_detail = instagram_notifier.send_message_detailed(msg)
                results["instagram"] = ig_ok
                results["details"]["instagram"] = ig_detail
        except Exception as e:
            results["details"]["instagram"] = str(e)

        # WhatsApp
        try:
            from app.whatsapp import whatsapp_notifier
            if whatsapp_notifier.is_configured():
                wa_ok = whatsapp_notifier.send_message(msg)
                results["whatsapp"] = wa_ok
                results["details"]["whatsapp"] = "Sent" if wa_ok else "Failed"
        except Exception as e:
            results["details"]["whatsapp"] = str(e)

        return results


ai_analyst = GeminiMarketAnalyst()

