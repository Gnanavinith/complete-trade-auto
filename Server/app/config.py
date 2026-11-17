"""
Central configuration for BTC-only single-bot trading system on Delta Exchange India.
All values are overridable via environment variables.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

# auto-load .env next to Server/ or parent
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except Exception:
    pass


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _b(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes")


def _env_first(*names: str, default: str = "") -> str:
    for n in names:
        v = os.getenv(n)
        if v not in (None, ""):
            return v
    return default


@dataclass
class DeltaConfig:
    env: str = os.getenv("DELTA_ENV", "testnet").lower()  # "testnet" or "production"
    api_key: str = _env_first("DELTA_API_KEY", "API_KEY", default="")
    api_secret: str = _env_first("DELTA_API_SECRET", "API_SECRET", default="")
    live_trading: bool = _b("LIVE_TRADING", False)

    # Base URLs per Delta Exchange India rules
    # Production: https://api.india.delta.exchange
    # Testnet: https://cdn-ind.testnet.deltaex.org
    base_url: str = field(init=False)

    def __post_init__(self):
        env_lower = self.env.strip().lower()
        if env_lower == "production":
            self.base_url = os.getenv("DELTA_BASE_URL", "https://api.india.delta.exchange")
        else:
            self.base_url = os.getenv("DELTA_BASE_URL", "https://cdn-ind.testnet.deltaex.org")


@dataclass
class RiskConfig:
    risk_per_trade_pct: float = _f("RISK_PER_TRADE_PCT", 0.5) / 100  # 0.5% equity risk per trade
    max_leverage: int = _i("MAX_LEVERAGE", 10)
    daily_loss_cap_pct: float = _f("DAILY_LOSS_CAP_PCT", 3.0) / 100  # 3% daily loss cap
    max_drawdown_pct: float = _f("MAX_DRAWDOWN_PCT", 10.0) / 100  # 10% max drawdown halt
    cooldown_bars: int = _i("COOLDOWN_BARS", 4)  # cooldown after N consecutive losses
    max_slippage_pct: float = _f("MAX_SLIPPAGE_PCT", 0.2) / 100  # 0.2% max acceptable slippage


@dataclass
class StrategyConfig:
    timeframe: str = os.getenv("SIGNAL_TIMEFRAME", "15m")
    symbol: str = os.getenv("TRADING_SYMBOL", "BTCUSD")  # BTC perpetual symbol on Delta


@dataclass
class AppConfig:
    delta: DeltaConfig = field(default_factory=DeltaConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    api_port: int = int(_env_first("PYTHON_ENGINE_PORT", "PORT", default="8000"))
    paper_mode: bool = _b("PAPER_MODE", True)
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_db_name: str = os.getenv("MONGODB_DB_NAME", "complete_trade_auto")


config = AppConfig()
