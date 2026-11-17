"""
Base strategy class for voting in the decision pipeline.
"""
from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional
from app.regime import MarketRegime


class BaseStrategy(ABC):
    def __init__(self, name: str, allowed_regimes: list[MarketRegime]):
        self.name = name
        self.allowed_regimes = allowed_regimes

    @abstractmethod
    def vote(self, df_15m: pd.DataFrame, df_1h: Optional[pd.DataFrame] = None) -> float:
        """
        Returns a score between -1.0 (strong short) and +1.0 (strong long).
        0.0 means neutral / no vote.
        """
        pass
