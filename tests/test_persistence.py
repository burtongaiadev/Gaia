import pytest
import aiosqlite
import os
from src.core.persistence import PersistenceService

@pytest.mark.asyncio
async def test_persistence_kv(tmp_path):
    # Use tmp DB
    db_file = tmp_path / "test_state.db"
    service = PersistenceService(str(db_file))
    
    await service.init_db()
    
    await service.set_value("balance", "10500.0")
    val = await service.get_value("balance")
    
    assert val == "10500.0"

@pytest.mark.asyncio
async def test_persistence_positions(tmp_path):
    db_file = tmp_path / "test_state.db"
    service = PersistenceService(str(db_file))
    await service.init_db()
    
    await service.update_position("BTC", 1.5, 50000.0)
    pos = await service.get_position("BTC")
    
    assert pos is not None
    assert pos["size"] == 1.5
    assert pos["entry_price"] == 50000.0
