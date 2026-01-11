import pytest
import asyncio
from src.core.broker import BacktestBroker

@pytest.mark.asyncio
async def test_bracket_take_profit():
    broker = BacktestBroker()
    broker.update_market_state(100.0, "t1")
    
    # Buy @ 100, SL 90, TP 110
    params = {"sl": 90.0, "tp": 110.0}
    await broker.place_order("TEST", "buy", "mkt", 1.0, params=params)
    
    # Check Active Orders
    assert len(broker.active_orders) == 2
    assert broker.position == 1.0
    
    # Move Price UP to 105 (Nothing happens)
    broker.update_market_state(105.0, "t2")
    assert broker.position == 1.0
    
    # Move Price UP to 110 (TP Hit)
    broker.update_market_state(110.0, "t3")
    assert broker.position == 0.0 # Sold
    assert len(broker.active_orders) == 0 # OCO: SL cancelled

@pytest.mark.asyncio
async def test_bracket_stop_loss():
    broker = BacktestBroker()
    broker.update_market_state(100.0, "t1")
    
    # Buy @ 100, SL 90, TP 110
    params = {"sl": 90.0, "tp": 110.0}
    await broker.place_order("TEST", "buy", "mkt", 1.0, params=params)
    
    # Move Price DOWN to 90 (SL Hit)
    broker.update_market_state(90.0, "t2")
    
    assert broker.position == 0.0
    assert len(broker.active_orders) == 0
