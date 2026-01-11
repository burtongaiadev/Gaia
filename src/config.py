from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    APP_NAME: str = "Gaia"
    APP_VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"
    RUN_MODE: str = Field(default="LIVE", description="Execution Mode: LIVE, RECORDER, BACKTEST")
    
    # Kraken (Placeholder for future stories)
    KRAKEN_API_KEY: str = Field(default="", description="Kraken API Key")
    KRAKEN_PRIVATE_KEY: str = Field(default="", description="Kraken Private Key")
    
    # Telegram (Placeholder)
    TELEGRAM_TOKEN: str = Field(default="", description="Telegram Bot Token")
    TELEGRAM_ALLOWED_IDS: List[int] = Field(default=[], description="List of authorized User IDs")
    
    # Market Data
    KRAKEN_SYMBOLS: List[str] = Field(default=[
        "PI_XBTUSD", "PI_ETHUSD", "PI_SOLUSD", "PI_BNBUSD", 
        "PI_DOGEUSD", "PI_SUIUSD", "PI_XRPUSD", "PI_TRXUSD", 
        "PI_LTCUSD", "PI_LINKUSD", "PI_AAVEUSD", "PI_AVAXUSD", "PI_CHZUSD"
    ], description="Symbols to subscribe to")

    from pydantic import field_validator

    @field_validator("TELEGRAM_ALLOWED_IDS", mode="before")
    @classmethod
    def parse_ids(cls, v):
        if isinstance(v, int):
            return [v]
        if isinstance(v, str) and not v.strip().startswith("["):
            # Handle comma-separated string: "123,456"
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v

settings = Settings()
