import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from src.core.broker import IBroker
from src.core.risk import RiskManager, SafeBroker

class MockBroker(IBroker):
    def __init__(self):
        self._place_order_mock = AsyncMock()
        self._get_position_mock = MagicMock(return_value=0.0)

    async def place_order(self, *args, **kwargs):
        return await self._place_order_mock(*args, **kwargs)

    def get_position(self, symbol: str) -> float:
        return self._get_position_mock(symbol)

@pytest.mark.asyncio
async def test_risk_low_confidence_rejection():
    inner = MockBroker()
    risk = RiskManager(min_confidence=0.8)
    safe_broker = SafeBroker(inner, risk)
    
    # Attempt order with Low Confidence
    params = {"ai_confidence": 0.5}
    await safe_broker.place_order("TEST", "buy", "mkt", 1.0, params=params)
    
    # Should NOT satisfy
    inner._place_order_mock.assert_not_called()
    assert risk.rejections == 1

@pytest.mark.asyncio
async def test_risk_valid_order_passthrough():
    inner = MockBroker()
    risk = RiskManager(min_confidence=0.8)
    safe_broker = SafeBroker(inner, risk)
    
    # Attempt order with High Confidence
    params = {"ai_confidence": 0.9}
    await safe_broker.place_order("TEST", "buy", "mkt", 1.0, params=params)
    
    # Should Pass
    inner._place_order_mock.assert_called_once()

@pytest.mark.asyncio
async def test_risk_max_position_limit():
    inner = MockBroker()
    # Mock current position is already 4.5
    inner._get_position_mock.return_value = 4.5
    
    risk = RiskManager(max_position_size=5.0)
    safe_broker = SafeBroker(inner, risk)
    
    # Attempt to buy 1.0 (Result 5.5 > 5.0)
    await safe_broker.place_order("TEST", "buy", "mkt", 1.0)
    
    # Should Reject
    inner._place_order_mock.assert_not_called()
