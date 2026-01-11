import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.connectors.kraken_ws import KrakenPublicWS

@pytest.mark.asyncio
async def test_parsing():
    client = KrakenPublicWS(["PI_XBTUSD"])
    
    # Valid Futures ticker message
    msg = json.dumps({
        "feed": "ticker",
        "product_id": "PI_XBTUSD",
        "last": 50000.0
    })
    
    with patch("src.connectors.kraken_ws.logger") as mock_logger:
        await client._handle_message(msg)
        
        # Verify it successfully parsed and logged
        mock_logger.debug.assert_called_with("Tick received: PI_XBTUSD $50000.0")
