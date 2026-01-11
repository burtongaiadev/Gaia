import asyncio
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("Gaia")

from src.connectors.telegram import telegram_service

class WatchdogService:
    def __init__(self, telegram_bot=None, check_interval: float = 1.0, heartbeat_interval: float = 60.0):
        self.telegram = telegram_bot
        self.check_interval = check_interval
        self.heartbeat_interval = heartbeat_interval
        self.last_tick = time.time()
        self.is_running = False
        self.start_time = datetime.now()
        
    async def start(self):
        self.is_running = True
        asyncio.create_task(self._monitor())
        asyncio.create_task(self._heartbeat_loop())
        logger.info("[WATCHDOG] Started.")

    async def _monitor(self):
        while self.is_running:
            start_check = time.time()
            await asyncio.sleep(self.check_interval)
            end_check = time.time()
            
            # If sleep(1.0) took 2.0s, we have lag
            lag = (end_check - start_check) - self.check_interval
            
            if lag > 0.5: # 500ms lag threshold
                logger.warning(f"[WATCHDOG] SYSTEM LAG DETECTED: {lag*1000:.2f}ms")
            
            self.last_tick = end_check

    async def _heartbeat_loop(self):
        while self.is_running:
            try:
                # Send Heartbeat
                uptime = datetime.now() - self.start_time
                msg = f"🟢 *Gaia Status: OK*\nUptime: {uptime}\nTop: Running Smoothly"
                
                # We need a chat_id. Typically this comes from Config or broadcast to allowed_ids.
                # Assuming telegram_bot has a broadcast method or we grab the first allowed ID.
                # Story 1.2 implemented specific command handlers, but not a generic broadcast?
                # I'll rely on telegram service having a send method if I know the chat_id.
                # For now, I'll log it if I can't send.
                # Log Heartbeat but do not spam Telegram
                # User prefers on-demand /status command
                logger.info(f"[HEARTBEAT] {msg.replace('*', '').replace(chr(10), ' ')}")
                
                # if hasattr(self.telegram, "broadcast"):
                #     await self.telegram.broadcast(msg)
                
            except Exception as e:
                logger.error(f"[WATCHDOG] Heartbeat Error: {e}")
                
            await asyncio.sleep(self.heartbeat_interval)

    def stop(self):
        self.is_running = False

# Singleton Instance
watchdog = WatchdogService(telegram_bot=telegram_service, heartbeat_interval=60.0)
