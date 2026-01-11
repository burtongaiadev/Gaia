import asyncio
from src.core.logger import logger
from src.connectors.kraken_futures_rest import kraken_futures_rest

class TradingControl:
    def __init__(self):
        self.trading_enabled = True
    
    def stop_trading(self):
        self.trading_enabled = False
        logger.warning("TRADING DISABLED")

    def resume_trading(self):
        self.trading_enabled = True
        logger.info("TRADING ENABLED")

    async def execute_panic(self):
        """
        Kill Switch:
        1. Disable Trading
        2. Cancel All Orders
        3. Close All Positions (Market)
        """
        logger.critical("PANIC BUTTON ACTIVATED! Executing Kill Switch...")
        self.stop_trading()
        results = []
        
        # 1. Cancel All
        try:
            logger.info("Cancelling all orders...")
            await kraken_futures_rest.cancel_all_orders()
            results.append("Orders Cancelled")
        except Exception as e:
            msg = f"Failed to cancel orders: {e}"
            logger.error(msg)
            results.append(msg)

        # 2. Close Positions
        try:
            logger.info("Fetching open positions...")
            response = await kraken_futures_rest.get_open_positions()
            
            # Helper to extract positions list safely
            positions = response.get('openPositions', [])
            # Also check if 'openPositions' is inside logic? 
            # If response is list? Usually API v3 returns {"result": "success", "openPositions": [...]}?
            # Or just list? Futures API often return {"openPositions": [...]}.
            
            if not positions:
                 logger.info("No open positions found.")
                 results.append("No Positions Open")
            else:
                for pos in positions:
                    symbol = pos.get('symbol')
                    size = float(pos.get('size', 0))
                    side = pos.get('side') # "long" or "short" usually
                    
                    if size > 0:
                        # Close it: Opposite side, Market Order
                        # Check side format: likely "long"/"short" or "buy"/"sell"?
                        # Futures usually uses "long"/"short" for positions, "buy"/"sell" for orders.
                        
                        close_side = "sell" if side == "long" else "buy"
                        if side not in ["long", "short"]:
                             # Fallback if side is 'buy'/'sell'
                             close_side = "sell" if side == "buy" else "buy"
                             
                        logger.warning(f"Closing position {symbol}: {size} {side} -> {close_side}")
                        
                        await kraken_futures_rest.send_order(
                            symbol=symbol,
                            side=close_side,
                            order_type="mkt",
                            size=size,
                            client_order_id="PANIC_CLOSE"
                        )
                results.append("Positions Closing")
            
            return f"Panic Executed: {', '.join(results)}"
            
        except Exception as e:
            logger.error(f"Failed to close positions: {e}")
            return f"Panic Error: {e}"

trading_control = TradingControl()
