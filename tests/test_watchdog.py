import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.core.watchdog import WatchdogService

@pytest.mark.asyncio
async def test_watchdog_monitor_lag():
    telegram = MagicMock()
    service = WatchdogService(telegram, check_interval=0.01)
    
    # Run loop briefly
    service.is_running = True
    task = asyncio.create_task(service._monitor())
    
    await asyncio.sleep(0.05)
    service.stop()
    await task
    
    # It should have run without error
    assert service.last_tick > 0

@pytest.mark.asyncio
async def test_watchdog_heartbeat():
    telegram = MagicMock()
    telegram.broadcast = AsyncMock()
    
    # Short heartbeat interval
    service = WatchdogService(telegram, check_interval=0.1, heartbeat_interval=0.1)
    
    service.is_running = True
    task = asyncio.create_task(service._heartbeat_loop())
    
    await asyncio.sleep(0.15) # Wait for 1 heartbeat
    service.stop()
    await task
    
    # Verify Broadcast called
    telegram.broadcast.assert_called()
