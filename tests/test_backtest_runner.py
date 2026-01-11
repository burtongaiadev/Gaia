import pytest
import os
import csv
from src.backtest import BacktestRunner

@pytest.mark.asyncio
async def test_runner_execution(tmp_path):
    # Create valid CSV with 1 tick
    f = tmp_path / "data.csv"
    with open(f, "w") as fp:
        fp.write("time,symbol,price,volume\n")
        fp.write("2025-01-01T12:00:00,TEST,100.0,1.0\n")
        
    runner = BacktestRunner(str(f), "TEST")
    await runner.run()
    
    # Should run without error and process 1 tick
    assert runner.broker.current_price == 100.0
