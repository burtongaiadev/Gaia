import pytest
from unittest.mock import AsyncMock, MagicMock
from src.core.recovery import RecoveryService

@pytest.mark.asyncio
async def test_recovery_reconcile_ghost_order():
    # Setup Mocks
    persistence = MagicMock()
    persistence.get_active_orders = AsyncMock(return_value=[]) # Local DB Empty
    persistence.save_order = AsyncMock()
    persistence.update_position = AsyncMock()
    
    exchange = MagicMock()
    # Remote has 1 order
    remote_orders = [{'order_id': 'ghost_1', 'symbol': 'BTC', 'size': 1.0, 'status': 'OPEN'}]
    exchange.get_open_orders = AsyncMock(return_value=remote_orders)
    exchange.get_positions = AsyncMock(return_value=[])
    
    service = RecoveryService(persistence, exchange)
    
    # Run
    await service.reconcile()
    
    # Verify: Ghost order should be saved to DB
    persistence.save_order.assert_called_once_with(remote_orders[0])

@pytest.mark.asyncio
async def test_recovery_reconcile_stale_order():
    # Setup Mocks
    persistence = MagicMock()
    # Local DB has 1 order
    local_orders = [{'order_id': 'stale_1', 'symbol': 'BTC', 'size': 1.0, 'status': 'OPEN'}]
    persistence.get_active_orders = AsyncMock(return_value=local_orders)
    persistence.update_order_status = AsyncMock()
    persistence.update_position = AsyncMock()
    
    exchange = MagicMock()
    exchange.get_open_orders = AsyncMock(return_value=[]) # Remote Empty
    exchange.get_positions = AsyncMock(return_value=[])
    
    service = RecoveryService(persistence, exchange)
    
    # Run
    await service.reconcile()
    
    # Verify: Stale order marked as CLOSED
    persistence.update_order_status.assert_called_once_with('stale_1', 'CLOSED')
