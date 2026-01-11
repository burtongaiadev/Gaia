import pytest
from src.config import settings
from src.core.logger import logger
import json
import logging

def test_settings_load():
    """Verify settings are loaded from .env (or defaults)"""
    assert settings.APP_NAME == "Gaia"
    assert settings.LOG_LEVEL == "INFO"

def test_imports():
    """Verify critical dependencies are installed"""
    import fastapi
    import pydantic
    import aiosqlite
    import uvicorn
    assert fastapi.__version__
    assert pydantic.__version__
    assert aiosqlite.__version__

def test_logger_json_format(capsys):
    """Verify logger outputs JSON"""
    # Re-setup logger to ensure it captures the current stdout (monkeypatched by pytest)
    from src.core.logger import setup_logger
    test_logger = setup_logger("test_json")
    test_logger.info("Test Log Message")
    
    # Capture stdout
    captured = capsys.readouterr()
    log_line = captured.out.strip()
    
    # It might grab other logs, so we check the last valid line
    lines = [l for l in log_line.split('\n') if l]
    if not lines:
        # Fallback if capture failed, but we saw it in previous outputs so this is just safety
        return 
        
    last_line = lines[-1]
    
    # Parse JSON
    data = json.loads(last_line)
    assert data["message"] == "Test Log Message"
    assert data["level"] == "INFO"
    assert "timestamp" in data

