import asyncio
import json
from typing import List, Optional
from datetime import datetime, timezone
import websockets
from websockets.exceptions import ConnectionClosed
from src.core.logger import logger
# MarketTick imported but we check if we need to add imports if missing from previous header
from src.core.models import MarketTick 
from src.config import settings

# Kraken Futures API v1
KRAKEN_WS_URL = "wss://futures.kraken.com/ws/v1"

class KrakenPublicWS:
    def __init__(self, symbols: Optional[List[str]] = None):
        self.symbols = symbols or settings.KRAKEN_SYMBOLS
        self.ws_url = KRAKEN_WS_URL
        self.running = False
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._reconnect_delay = 1.0
        self.listeners = [] # List of callbacks (async preferred)
        
    def add_listener(self, callback):
        """Register a callback for new ticks"""
        self.listeners.append(callback)

    async def start(self):
        """Start the WebSocket connection task"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"Starting Kraken Futures WS for symbols: {self.symbols}")
        # Run loop in background
        asyncio.create_task(self._connect_loop())

    async def stop(self):
        """Stop the WebSocket connection"""
        if not self.running:
            return
            
        logger.info("Stopping Kraken Futures WS...")
        self.running = False
        if self._ws:
            await self._ws.close()

    async def _connect_loop(self):
        """Main connection and reconnection loop"""
        while self.running:
            try:
                # Open connection
                logger.info(f"Connecting to {self.ws_url}...")
                async with websockets.connect(self.ws_url) as ws:
                    self._ws = ws
                    logger.info("Connected to Kraken Futures WS")
                    self._reconnect_delay = 1.0 # Reset backoff
                    
                    # Subscribe to Futures Ticker
                    subscribe_msg = {
                        "event": "subscribe",
                        "feed": "ticker",
                        "product_ids": self.symbols
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info(f"Subscribed to tickers: {self.symbols}")
                    
                    # Enter read loop
                    await self._read_loop(ws)
                    
            except (ConnectionRefusedError, ConnectionClosed, Exception) as e:
                # If we are stopping, ignore
                if not self.running:
                    break
                
                logger.warning(f"Kraken WS connection lost: {e}. Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60.0) # Backoff max 60s

    async def _read_loop(self, ws):
        """Read messages from WebSocket"""
        while self.running:
            try:
                # Heartbeat timeout monitoring (60s)
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=60.0)
                await self._handle_message(msg_raw)
            except asyncio.TimeoutError:
                logger.warning("Kraken WS Heartbeat Timeout. Reconnecting...")
                await ws.close()
                break
            except ConnectionClosed:
                raise
            except Exception as e:
                logger.error(f"Error in read loop: {e}")
                if not ws.open:
                    break

    async def _handle_message(self, msg_raw):
        """Parse and process incoming messages (Futures API)"""
        try:
            data = json.loads(msg_raw)
            
            # Futures API messages usually have 'event' for control, or 'feed' for data
            event = data.get("event")
            feed = data.get("feed")
            
            if event == "info":
                logger.info(f"Kraken Futures Info: {data.get('version')}")
                return
            elif event == "subscribed":
                logger.info(f"Successfully subscribed to {data.get('feed')} for {data.get('product_ids')}")
                return
            elif event == "error":
                logger.error(f"Kraken Futures Error: {data.get('message')}")
                return

            # Data Message
            if feed == "ticker":
                product_id = data.get("product_id")
                last = data.get("last")
                
                if product_id and last:
                    tick = MarketTick(
                        symbol=product_id, 
                        price=float(last), 
                        timestamp=datetime.now(timezone.utc)
                    )
                    
                    # Dispatch to listeners
                    for listener in self.listeners:
                        try:
                            if asyncio.iscoroutinefunction(listener):
                                await listener(tick)
                            else:
                                listener(tick)
                        except Exception as e:
                           logger.error(f"Listener error: {e}")
                
        except Exception as e:
            logger.error(f"Error parsing Kraken message: {e}", exc_info=True)

# Global instance
kraken_ws_client = KrakenPublicWS()
