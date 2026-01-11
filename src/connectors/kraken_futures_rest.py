import time
import base64
import hashlib
import hmac
import urllib.parse
from typing import Dict, Any, Optional, List
import httpx
from src.config import settings
from src.core.logger import logger

class KrakenFuturesREST:
    def __init__(self):
        # Base URL for Futures (Derivatives)
        self.base_url = "https://futures.kraken.com"
        self.api_key = settings.KRAKEN_API_KEY
        self.private_key = settings.KRAKEN_PRIVATE_KEY
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)

    def _generate_nonce(self) -> str:
        # Time in milliseconds
        return str(int(time.time() * 1000))

    def _sign_request(self, endpoint: str, post_data: str, nonce: str) -> str:
        """
        Generate Authent header for Kraken Futures v3.
        Formula: Base64( HMAC-SHA512( SHA256( postData + nonce + endpointPath ), Base64Decode(secret) ) )
        """
        if not self.private_key:
            raise ValueError("Kraken Private Key not set")

        # Concatenate inputs: postData + nonce + endpoint
        message = post_data + nonce + endpoint
        
        # SHA256 hash
        sha256_hash = hashlib.sha256(message.encode('utf-8')).digest()
        
        # HMAC-SHA512 with decoded secret
        secret = base64.b64decode(self.private_key)
        mac = hmac.new(secret, sha256_hash, hashlib.sha512)
        
        # Base64 encode the result
        return base64.b64encode(mac.digest()).decode('utf-8')

    async def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None):
        if params is None:
            params = {}

        nonce = self._generate_nonce()
        
        # Prepare postData string
        # For GET, params go in URL usually, but signature needs them?
        # Standard: postData is urlencoded params.
        data_str = urllib.parse.urlencode(params)
        
        # For GET requests, the query params are part of the 'endpoint' in strict terms? 
        # Or does postData cover them?
        # Search result said "hash the full, URL-encoded URI component".
        # If I strictly follow "postData + nonce + endpoint", data_str is postData.
        
        authent = self._sign_request(endpoint, data_str, nonce)
        
        headers = {
            "APIKey": self.api_key,
            "Authent": authent,
            "Nonce": nonce,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            if method == "POST":
                response = await self.client.post(endpoint, content=data_str, headers=headers)
            else:
                # GET
                url_with_params = f"{endpoint}?{data_str}" if data_str else endpoint
                response = await self.client.get(url_with_params, headers=headers)
                
            if response.status_code >= 400:
                logger.error(f"Kraken Futures API Error {response.status_code}: {response.text}")
                
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            # Log critical info for debugging (exclude keys)
            logger.error(f"HTTP Error: {e}")
            raise
        except Exception as e:
            logger.exception("Request failed")
            raise

    async def get_accounts(self):
        """Get Account Balances"""
        return await self._request("GET", "/derivatives/api/v3/accounts")

    async def get_open_positions(self):
        """Get Open Positions"""
        return await self._request("GET", "/derivatives/api/v3/openpositions")

    async def get_open_orders(self):
        """Get Open Orders"""
        return await self._request("GET", "/derivatives/api/v3/openorders")
        
    async def get_fills(self, last_fill_time: Optional[str] = None):
        """Get Fills/Executions"""
        params = {}
        if last_fill_time:
            params["lastFillTime"] = last_fill_time
        return await self._request("GET", "/derivatives/api/v3/fills", params)

    async def send_order(self, symbol: str, side: str, order_type: str, size: float, limit_price: Optional[float] = None, client_order_id: Optional[str] = None):
        """
        Send formatted order.
        side: 'buy' or 'sell'
        order_type: 'lmt', 'post', 'ioc', 'mkt', etc.
        """
        params = {
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "size": str(size),
        }
        if limit_price:
            params["limitPrice"] = str(limit_price)
        if client_order_id:
            params["cliOrdId"] = client_order_id
            
        return await self._request("POST", "/derivatives/api/v3/sendorder", params)

    async def cancel_order(self, order_id: str = None, client_order_id: str = None):
        """Cancel order by OrderID or CliOrdId"""
        params = {}
        if order_id:
            params["order_id"] = order_id
        elif client_order_id:
            params["cliOrdId"] = client_order_id
        else:
            raise ValueError("Must provide order_id or client_order_id")
            
        return await self._request("POST", "/derivatives/api/v3/cancelorder", params)

    async def cancel_all_orders(self, symbol: Optional[str] = None):
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("POST", "/derivatives/api/v3/cancelallorders", params)

# Global Instance
kraken_futures_rest = KrakenFuturesREST()
