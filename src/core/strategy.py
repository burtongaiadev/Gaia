import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional
from src.core.models import MarketTick, OHLCV
from src.core.logger import logger

class CandleBuffer:
    def __init__(self, max_size=1000):
        self.max_size = max_size
        # Initialize empty DataFrame with float columns provided to avoid dtype issues later
        self.df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        self.df.index.name = "time"

    def add_candle(self, candle: OHLCV):
        # Create single row DataFrame
        new_row = pd.DataFrame({
            "open": [float(candle.open)],
            "high": [float(candle.high)],
            "low": [float(candle.low)],
            "close": [float(candle.close)],
            "volume": [float(candle.volume)]
        }, index=[candle.time])
        
        # Concat is standard for appending in Pandas (though slightly expensive)
        # For high-freq, dictionary buffer + occasional DF construction is faster.
        # But for 1m candles (low freq), concat is fine.
        if self.df.empty:
            self.df = new_row
        else:
            self.df = pd.concat([self.df, new_row])
            # Drop duplicates if receiving update for same candle (not expected with Aggregator logic)
            self.df = self.df[~self.df.index.duplicated(keep='last')]
        
        # Trim
        if len(self.df) > self.max_size:
            self.df = self.df.iloc[-self.max_size:]

    # --- Indicators ---
    
    def sma(self, period=20) -> pd.Series:
        return self.df["close"].rolling(window=period).mean()

    def ema(self, period=20) -> pd.Series:
        return self.df["close"].ewm(span=period, adjust=False).mean()

    def rsi(self, period=14) -> pd.Series:
        """Relative Strength Index (Wilder's Method)"""
        delta = self.df["close"].diff()
        
        up = delta.copy()
        down = delta.copy()
        up[up < 0] = 0
        down[down > 0] = 0
        down = abs(down) # Positive values
        
        # Wilder's Smoothing: alpha = 1/period
        roll_up = up.ewm(alpha=1/period, adjust=False).mean()
        roll_down = down.ewm(alpha=1/period, adjust=False).mean()
        
        rs = roll_up / roll_down
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

class TickAggregator:
    def __init__(self, interval_minutes=1):
        self.interval = interval_minutes
        self.current_candle: Optional[OHLCV] = None
        self.last_bucket: Optional[datetime] = None

    def on_tick(self, tick: MarketTick) -> Optional[OHLCV]:
        """
        Accepts a tick. Returns a COMPLETED candle if the bucket has rolled over.
        Returns None otherwise.
        """
        t = tick.timestamp
        # Round down to start of minute
        bucket = t.replace(second=0, microsecond=0)
        
        closed_candle = None
        
        if self.last_bucket and bucket > self.last_bucket:
             # Bucket change: Close previous
             closed_candle = self.current_candle
             # Start new
             self.current_candle = self._new_candle(tick, bucket)
             self.last_bucket = bucket
        elif self.current_candle is None:
             # First tick ever
             self.current_candle = self._new_candle(tick, bucket)
             self.last_bucket = bucket
        else:
             # Update current candle
             c = self.current_candle
             c.high = max(c.high, tick.price)
             c.low = min(c.low, tick.price)
             c.close = tick.price
             c.volume += tick.volume
             # Time remains bucket start
             
        return closed_candle

    def _new_candle(self, tick, bucket):
        return OHLCV(
            symbol=tick.symbol,
            time=bucket,
            open=tick.price,
            high=tick.price,
            low=tick.price,
            close=tick.price,
            volume=tick.volume,
            interval=self.interval
        )

from src.core.broker import IBroker

class Strategy:
    """Base Strategy Class"""
    def __init__(self, symbol: str, broker: Optional[IBroker] = None):
        self.symbol = symbol
        self.candles = CandleBuffer()
        self.aggregator = TickAggregator()
        self.broker = broker
        
    async def on_tick(self, tick: MarketTick):
        # Aggregate tick -> candle
        closed_candle = self.aggregator.on_tick(tick)
        if closed_candle:
            logger.info(f"Candle Closed: {closed_candle.time} C={closed_candle.close}")
            await self.on_candle(closed_candle)

    async def on_candle(self, candle: OHLCV):
        self.candles.add_candle(candle)
        await self.execute()

    async def execute(self):
        """Override in subclass"""
        pass
