import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.connectors.telegram import status_command, start_command, authorized_only
from telegram import Update, User

@pytest.mark.asyncio
async def test_status_command():
    with patch("src.connectors.telegram.psutil") as mock_psutil:
        # Mock memory usage
        mock_mem = MagicMock()
        mock_mem.percent = 45.5
        mock_psutil.virtual_memory.return_value = mock_mem
        
        # Mock Update and Context
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 12345
        update.message = AsyncMock() # args for reply_text
        
        context = MagicMock()
        
        # We need to mock settings for the auth check inside status_command decorator?
        # status_command is decorated with @authorized_only
        
        with patch("src.connectors.telegram.settings") as mock_settings:
            mock_settings.TELEGRAM_ALLOWED_IDS = [12345]
            
            await status_command(update, context)
            
            update.message.reply_text.assert_called_once()
            args, _ = update.message.reply_text.call_args
            assert "45.5%" in args[0]
            assert "System Online" in args[0]

@pytest.mark.asyncio
async def test_auth_block():
    update = MagicMock(spec=Update)
    update.effective_user.id = 999 # Unauthorized
    update.message = AsyncMock()
    context = MagicMock()
    
    with patch("src.connectors.telegram.settings") as mock_settings:
        mock_settings.TELEGRAM_ALLOWED_IDS = [12345] # 999 not here
        
        with patch("src.connectors.telegram.logger") as mock_logger:
            await start_command(update, context)
            
            # Message should NOT be sent
            update.message.reply_text.assert_not_called()
            # Warning should be logged
            mock_logger.warning.assert_called_once()
            assert "Unauthorized" in mock_logger.warning.call_args[0][0]

