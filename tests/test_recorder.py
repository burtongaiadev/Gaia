import pytest
import os
import shutil
import asyncio
from datetime import datetime
from src.core.recorder import DataRecorder
from src.core.models import MarketTick

@pytest.fixture
def clean_data_dir():
    dir_path = "tests/data_temp"
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    yield dir_path
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)

@pytest.mark.asyncio
async def test_recorder_write_flow(clean_data_dir):
    recorder = DataRecorder(data_dir=clean_data_dir)
    await recorder.start()
    
    # Tick with specific time
    ts = datetime(2025, 1, 1, 12, 0, 0)
    tick = MarketTick(symbol="TEST", price=100.0, volume=5.0, timestamp=ts)
    
    await recorder.record_tick(tick)
    
    # Give generic executor time to finish
    await asyncio.sleep(0.2)
    
    await recorder.stop()
    
    # Check file
    expected_file = os.path.join(clean_data_dir, "ticker_2025-01-01.csv")
    assert os.path.exists(expected_file)
    
    with open(expected_file, 'r') as f:
        lines = f.readlines()
        assert len(lines) == 2 # Header + 1 row
        assert "time,symbol,price,volume" in lines[0]
        assert "2025-01-01T12:00:00" in lines[1]
        assert "TEST,100.0,5.0" in lines[1]

@pytest.mark.asyncio
async def test_recorder_rotation(clean_data_dir):
    recorder = DataRecorder(data_dir=clean_data_dir)
    await recorder.start()
    
    # Day 1
    t1 = datetime(2025, 1, 1, 23, 59)
    await recorder.record_tick(MarketTick(symbol="A", price=10, timestamp=t1))
    
    await asyncio.sleep(0.1)
    
    # Day 2
    t2 = datetime(2025, 1, 2, 0, 1)
    await recorder.record_tick(MarketTick(symbol="A", price=11, timestamp=t2))
    
    await asyncio.sleep(0.1)
    await recorder.stop()
    
    assert os.path.exists(os.path.join(clean_data_dir, "ticker_2025-01-01.csv"))
    assert os.path.exists(os.path.join(clean_data_dir, "ticker_2025-01-02.csv"))
