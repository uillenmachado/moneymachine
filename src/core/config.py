"""Configuração centralizada via Pydantic Settings.

Carregada de variáveis de ambiente (com prefixo MDD_) ou arquivo .env.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    TESTNET = "testnet"
    PRODUCTION = "production"


class RiskSettings(BaseSettings):
    """Limites do Risk Engine. Valores conservadores; calibrar após backtest."""

    model_config = SettingsConfigDict(env_prefix="MDD_RISK_", extra="ignore")

    max_daily_drawdown_pct: float = Field(default=3.0, gt=0, le=100)
    max_position_per_side_pct: float = Field(default=30.0, gt=0, le=100)
    latency_p99_ms_limit: int = Field(default=500, gt=0)
    inventory_skew_limit: float = Field(default=0.5, gt=0, le=1.0)


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    db: str = "mdd"
    user: str = "mdd"
    password: SecretStr = SecretStr("change_me_in_local_only")

    @property
    def dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.db}"
        )


class TelegramSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MDD_TELEGRAM_", extra="ignore")

    bot_token: SecretStr | None = None
    chat_id: str | None = None

    @property
    def enabled(self) -> bool:
        return self.bot_token is not None and self.chat_id is not None


class Settings(BaseSettings):
    """Configuração global do sistema."""

    model_config = SettingsConfigDict(
        env_prefix="MDD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_json: bool = False

    # Exchange
    exchange: str = "binance"
    exchange_testnet: bool = True
    api_key: SecretStr = SecretStr("")
    api_secret: SecretStr = SecretStr("")

    # Métricas
    metrics_port: int = 9100

    # Capital
    capital_usd: float = Field(default=500.0, gt=0)

    # Sub-configs
    risk: RiskSettings = Field(default_factory=RiskSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna instância singleton de Settings (cacheada)."""
    return Settings()
