import psutil
from functools import wraps
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes, CommandHandler
from src.config import settings
from src.core.logger import logger

def authorized_only(func):
    """Decorator to check if user is in ALLOWED_IDS"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in settings.TELEGRAM_ALLOWED_IDS:
            logger.warning(f"Unauthorized access attempt from User ID: {user_id}")
            return # Silent ignore
        return await func(update, context, *args, **kwargs)
    return wrapper

@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Gaia Online v{settings.APP_VERSION}")

@authorized_only
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mem = psutil.virtual_memory()
    msg = [
        f"✅ Gaia Online v{settings.APP_VERSION}",
        f"🧠 Memory: {mem.percent}% used"
    ]
    
    if telegram_service.broker:
        try:
            stats = telegram_service.broker.get_stats()
            # Stats: equity, pnl, trades_count, positions
            equity = stats.get('equity', 0.0)
            pnl = stats.get('pnl', 0.0)
            trades = stats.get('trades_count', 0)
            positions = stats.get('positions', {})
            
            icon = "📈" if pnl >= 0 else "📉"
            msg.append(f"{icon} PnL: ${pnl:.2f}")
            msg.append(f"💰 Equity: ${equity:.2f}")
            msg.append(f"🔢 Trades: {trades}")
            
            if positions:
                pos_list = [f"{sym}: {amt:.4f}" for sym, amt in positions.items()]
                msg.append(f"✊ Open Pos: {', '.join(pos_list)}")
            else:
                msg.append("😴 Market Flat")
                
        except Exception as e:
            msg.append(f"⚠️ Data Error: {e}")
            
    await update.message.reply_text("\n".join(msg))

from src.core.control import trading_control

@authorized_only
async def panic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    await update.message.reply_text(f"🚨 PANIC command received from {user}!")
    
    result = await trading_control.execute_panic()
    await update.message.reply_text(f"ℹ️ Status: {result}")

class TelegramService:
    def __init__(self):
        self.app: Application | None = None
        self.broker = None
        
    def set_broker(self, broker):
        self.broker = broker
    
    async def start(self):
        if not settings.TELEGRAM_TOKEN:
             logger.warning("Telegram Token not set. Bot service disabled.")
             return

        self.app = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()
        
        self.app.add_handler(CommandHandler("start", start_command))
        self.app.add_handler(CommandHandler("status", status_command))
        self.app.add_handler(CommandHandler("panic", panic_command))
        
        await self.app.initialize()
        await self.app.start()
        
        # Start polling (non-blocking)
        # Note: In PTB v20+,updater is optional but ApplicationBuilder().build() includes it by default unless disabled.
        # We use standard polling.
        # Start polling (non-blocking)
        await self.app.updater.start_polling()
        
        logger.info(f"Telegram Bot Started. Authorized IDs: {settings.TELEGRAM_ALLOWED_IDS}")
        await self.broadcast(f"🚀 Gaia Bot Online! Mode: {settings.RUN_MODE}")

    async def broadcast(self, message: str):
        """Send a message to all authorized users"""
        if not self.app or not settings.TELEGRAM_ALLOWED_IDS:
            return
            
        for chat_id in settings.TELEGRAM_ALLOWED_IDS:
            try:
                await self.app.bot.send_message(chat_id=chat_id, text=message)
            except Exception as e:
                logger.error(f"Failed to send Telegram message to {chat_id}: {e}")

    async def stop(self):
        if self.app:
            logger.info("Stopping Telegram Bot...")
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info("Telegram Bot Stopped")

telegram_service = TelegramService()
