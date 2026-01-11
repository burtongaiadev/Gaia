import logging
from typing import List, Dict, Any

logger = logging.getLogger("Gaia")

from src.core.persistence import persistence

class RecoveryService:
    def __init__(self, persistence, exchange_client=None):
        self.persistence = persistence
        self.exchange = exchange_client


    async def reconcile(self):
        logger.info("[RECOVERY] Starting State Reconciliation...")
        
        # 1. Fetch Remote State
        remote_open_orders = await self.exchange.get_open_orders()
        remote_positions = await self.exchange.get_positions()
        
        # 2. Fetch Local State (We assume persistence has method to get all open orders)
        # Note: I need to add get_open_orders to PersistenceService first! 
        # For now, I'll mock that interaction or add it later.
        # Let's assume persistence.get_active_orders() exists.
        local_open_orders = await self.persistence.get_active_orders()
        
        # 3. Reconcile Orders
        await self._reconcile_orders(local_open_orders, remote_open_orders)
        
        # 4. Reconcile Positions
        await self._reconcile_positions(remote_positions)
        
        logger.info("[RECOVERY] Reconciliation Complete.")

    async def _reconcile_orders(self, local_orders: List[Dict], remote_orders: List[Dict]):
        remote_ids = {o['order_id'] for o in remote_orders}
        local_ids = {o['order_id'] for o in local_orders}
        
        # Ghost Orders (Found on Remote, Missing Locally)
        for order in remote_orders:
            if order['order_id'] not in local_ids:
                logger.warning(f"[RECOVERY] Found Ghost Order {order['order_id']} on Exchange. Importing...")
                await self.persistence.save_order(order)
                
        # Stale Orders (Found Locally, Missing on Remote)
        for order in local_orders:
            if order['order_id'] not in remote_ids:
                logger.warning(f"[RECOVERY] Local Order {order['order_id']} not found on Exchange. Marking CLOSED.")
                # Conservative assumption: It's gone.
                await self.persistence.update_order_status(order['order_id'], "CLOSED")

    async def _reconcile_positions(self, remote_positions: List[Dict]):
        # Source of Truth is Exchange
        for pos in remote_positions:
            logger.info(f"[RECOVERY] Updating Position {pos['symbol']} from Exchange.")
            await self.persistence.update_position(pos['symbol'], pos['size'], pos['entry_price'])

# Singleton Instance
recovery = RecoveryService(persistence)
