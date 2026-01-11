import pytest
from unittest.mock import AsyncMock, patch
import base64
from src.connectors.kraken_futures_rest import KrakenFuturesREST

@pytest.mark.asyncio
async def test_signing_structure():
    with patch("src.connectors.kraken_futures_rest.settings") as mock_settings:
        mock_settings.KRAKEN_API_KEY = "mock_key"
        # "test_secret" base64 encoded
        mock_settings.KRAKEN_PRIVATE_KEY = base64.b64encode(b"test_secret").decode('utf-8')
        
        client = KrakenFuturesREST()
        
        # Mock httpx client
        client.client = AsyncMock()
        client.client.get.return_value.status_code = 200
        client.client.get.return_value.json.return_value = {"result": "success"}
        
        # Test get_accounts
        await client.get_accounts()
        
        client.client.get.assert_called_once()
        args, kwargs = client.client.get.call_args
        headers = kwargs["headers"]
        
        assert headers["APIKey"] == "mock_key"
        assert "Authent" in headers
        assert "Nonce" in headers
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"

@pytest.mark.asyncio
async def test_send_order_post():
    with patch("src.connectors.kraken_futures_rest.settings") as mock_settings:
        mock_settings.KRAKEN_API_KEY = "mock_key"
        mock_settings.KRAKEN_PRIVATE_KEY = base64.b64encode(b"test_secret").decode('utf-8')
        
        client = KrakenFuturesREST()
        client.client = AsyncMock()
        client.client.post.return_value.status_code = 200
        client.client.post.return_value.json.return_value = {"sendStatus": "placed"}
        
        await client.send_order("PI_XBTUSD", "buy", "lmt", 1.0, 50000.0)
        
        client.client.post.assert_called_once()
        args, kwargs = client.client.post.call_args
        content = kwargs["content"]
        
        # Verify params in content
        assert "symbol=PI_XBTUSD" in content
        assert "side=buy" in content
        assert "limitPrice=50000.0" in content
