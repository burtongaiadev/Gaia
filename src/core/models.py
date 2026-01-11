from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class MarketTick(BaseModel):
    """Represents a standardized market data update (Ticker/Trade)"""
    symbol: str
    price: float
    volume: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    feed: str = "kraken"
    
class OHLCV(BaseModel):
    """Represents a standardized Candle"""
    symbol: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    interval: int # in minutes
