"""
Aggregator: combines strategy votes into one decision, filtered by regime and 1h trend.
"""
import pandas as pd
from typing import List, Optional
from app.strategies.base import BaseStrategy
from app.regime import MarketRegime, detect_regime
from app.indicators import ema


class Aggregator:
    def __init__(self, strategies: List[BaseStrategy], weights: Optional[List[float]] = None):
        self.strategies = strategies
        self.weights = weights if weights else [1.0] * len(strategies)

    def decide(self, df_15m: pd.DataFrame, df_1h: Optional[pd.DataFrame] = None) -> tuple[str, float, MarketRegime]:
        """
        Runs all applicable strategies for the current market regime,
        computes weighted average vote, applies 1h trend hard rule,
        and returns ('long'|'short'|'flat', final_score, regime).
        """
        regime = detect_regime(df_15m)
        if regime == MarketRegime.CHAOS or regime == MarketRegime.UNKNOWN:
            return "flat", 0.0, regime

        total_weight = 0.0
        weighted_score = 0.0

        for strat, weight in zip(self.strategies, self.weights):
            if regime in strat.allowed_regimes:
                score = strat.vote(df_15m, df_1h)
                weighted_score += score * weight
                total_weight += weight

        if total_weight <= 0:
            return "flat", 0.0, regime

        final_score = weighted_score / total_weight

        # Hard rule: ignore trades against 1h trend unless regime is RANGE
        if regime != MarketRegime.RANGE and df_1h is not None and len(df_1h) >= 50:
            h_fast = ema(df_1h["close"], 50)
            h_slow = ema(df_1h["close"], 200) if len(df_1h) >= 200 else ema(df_1h["close"], 50)
            htf_bullish = h_fast.iloc[-1] >= h_slow.iloc[-1]
            htf_bearish = h_fast.iloc[-1] <= h_slow.iloc[-1]

            if final_score > 0.5 and not htf_bullish:
                final_score = 0.0  # veto long against bearish 1h trend
            elif final_score < -0.5 and not htf_bearish:
                final_score = 0.0  # veto short against bullish 1h trend

        # Threshold decision: LONG if > +0.6, SHORT if < -0.6, else FLAT
        if final_score >= 0.6:
            return "long", final_score, regime
        elif final_score <= -0.6:
            return "short", final_score, regime

        return "flat", final_score, regime
