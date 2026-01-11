import pytest
from datetime import datetime, timedelta
from src.core.models import MarketTick, OHLCV
from src.core.strategy import TickAggregator, CandleBuffer

def test_tick_aggregator():
    agg = TickAggregator()
    
    t1 = datetime(2025, 1, 1, 12, 0, 10)
    tick1 = MarketTick(symbol="X", price=100, volume=1, timestamp=t1)
    
    res = agg.on_tick(tick1)
    assert res is None # Open candle
    
    tick2 = MarketTick(symbol="X", price=105, volume=1, timestamp=t1 + timedelta(seconds=20))
    res = agg.on_tick(tick2)
    assert res is None # Same bucket
    
    # New bucket
    t2 = datetime(2025, 1, 1, 12, 1, 5)
    tick3 = MarketTick(symbol="X", price=102, volume=1, timestamp=t2)
    
    res = agg.on_tick(tick3)
    assert isinstance(res, OHLCV)
    assert res.high == 105
    assert res.low == 100
    assert res.close == 105
    assert res.volume == 2
    assert res.time == datetime(2025, 1, 1, 12, 0)

def test_candle_buffer_indicators():
    buf = CandleBuffer(max_size=50)
    base_time = datetime(2025, 1, 1)
    
    # Add 30 candles (Linear Up Trend)
    # Prices: 10, 11, 12, ... 39
    for i in range(30):
        c = OHLCV(symbol="X", time=base_time+timedelta(minutes=i),
                  open=10, high=10, low=10, close=10 + i, volume=100, interval=1)
        buf.add_candle(c)
        
    sma = buf.sma(period=5)
    # Last 5 prices: 35, 36, 37, 38, 39
    # Mean: 37
    assert sma.iloc[-1] == 37.0
    
    # RSI Test (Linear Up Trend -> RSI 100)
    rsi = buf.rsi(period=14)
    assert rsi.iloc[-1] > 99.0
