import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.core.control import TradingControl

@pytest.mark.asyncio
async def test_panic_execution():
    # Patch the global instance or the import inside control.py?
    # control.py imports: from src.connectors.kraken_futures_rest import kraken_futures_rest
    # so we patch src.core.control.kraken_futures_rest
    with patch("src.core.control.kraken_futures_rest") as mock_kraken:
        # Create fresh instance to avoid global state issues
        control = TradingControl()
        
        # Verification vars
        mock_kraken.cancel_all_orders = AsyncMock()
        mock_kraken.get_open_positions = AsyncMock(return_value={
            "result": "success",
            "openPositions": [
                {"symbol": "PI_XBTUSD", "size": "1.5", "side": "long"},
                {"symbol": "PI_ETHUSD", "size": "0.0", "side": "short"} 
            ]
        })
        mock_kraken.send_order = AsyncMock(return_value={"sendStatus": "placed"})
        
        # Execute
        result = await control.execute_panic()
        
        # Verify State
        assert control.trading_enabled is False
        
        # Verify Cancel
        mock_kraken.cancel_all_orders.assert_called_once()
        
        # Verify Position Closing (Only size > 0)
        mock_kraken.send_order.assert_called_once()
        args, kwargs = mock_kraken.send_order.call_args
        
        assert kwargs["symbol"] == "PI_XBTUSD"
        assert kwargs["side"] == "sell" # Long -> Sell
        assert kwargs["size"] == 1.5
        assert kwargs["order_type"] == "mkt"
        assert kwargs["client_order_id"] == "PANIC_CLOSE"
        
        assert "Positions Closing" in result
