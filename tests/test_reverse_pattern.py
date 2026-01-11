import pytest
from unittest.mock import patch
from datetime import datetime, timedelta
from src.core.models import OHLCV
from src.strategies.reverse_pattern import ReversePatternStrategy
import pandas as pd

def candle(offset_mins, open, high, low, close):
    return OHLCV(
        symbol="TEST",
        time=datetime(2025,1,1) + timedelta(minutes=offset_mins),
        open=open, high=high, low=low, close=close, volume=100, interval=1
    )

@pytest.mark.asyncio
async def test_bearish_signal_detection():
    strat = ReversePatternStrategy("TEST")
    strat.ma_period = 2 # Short MA for testing with few candles
    
    # Data Setup
    # Indices: 0(-6), 1(-5), 2(-4), 3(-3), 4(-2), 5(-1)
    data = [
        candle(0, 10, 10, 9, 10), 
        candle(1, 10, 10, 9, 10), 
        candle(2, 10, 10, 9, 10), 
        
        # P1 Pattern Start
        candle(3, 10, 12, 9, 11), # -3: Green (11>10). High 12.
        candle(4, 11, 12, 9, 10), # -2: Red (10<11). Low 9. High 12.
        candle(5, 9, 12, 8, 8)    # -1: Red/Break. Close 8 < Low 9. High 12.
    ]
    
    # Context Logic Verification:
    # Highs: [10, 10, 10, 12, 12, 12]
    # -3(12) > -5(10) -> OK
    # -2(12) > -6(10) -> OK
    # -1(12) > -5(10) -> OK
    # -1(12) > -6(10) -> OK
    
    for c in data:
        strat.candles.add_candle(c)
        
    with patch("src.strategies.reverse_pattern.logger") as mock_logger:
        await strat.execute()
        
        mock_logger.info.assert_called()
        args, _ = mock_logger.info.call_args
        assert "BEARISH DETECTED" in args[0]

@pytest.mark.asyncio
async def test_bullish_signal_detection():
    strat = ReversePatternStrategy("TEST")
    strat.ma_period = 2
    
    # Bullish P1: Red -> Green -> Break High
    # Context: Lower Lows
    # Lows: [10, 10, 10, 8, 8, 8]
    # -3(8) < -5(10)
    
    data = [
        candle(0, 10, 11, 10, 10), # -6
        candle(1, 10, 11, 10, 10), # -5
        candle(2, 10, 11, 10, 10), # -4
        
        # P1
        candle(3, 11, 11, 8, 9),   # -3: Red (9<11). Low 8.
        candle(4, 9, 10, 8, 11),   # -2: Green (11>9). High 10. Low 8.
        candle(5, 11, 12, 8, 12)   # -1: Break High. Close 12 > High 10.
    ]
    
    for c in data:
        strat.candles.add_candle(c)

    with patch("src.strategies.reverse_pattern.logger") as mock_logger:
        await strat.execute()
        
        mock_logger.info.assert_called()
        args, _ = mock_logger.info.call_args
        assert "BULLISH DETECTED" in args[0]
