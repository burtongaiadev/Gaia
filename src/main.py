import asyncio
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.logger import logger
from src.config import settings
from src.connectors.telegram import telegram_service
from src.connectors.kraken_ws import kraken_ws_client
from src.core.recorder import recorder
from src.core.control import trading_control
from src.core.models import MarketTick

# Core Components
from src.core.persistence import persistence
from src.core.recovery import recovery
from src.core.watchdog import watchdog
from src.core.inference import InferenceService
from src.core.risk import RiskManager
from src.core.broker import BacktestBroker, IBroker
from src.strategies.reverse_pattern import ReversePatternStrategy

# Global Strategy Instance (to reference inside listeners)
bot_strategies = {}
paper_broker = None

async def on_tick_processor(tick: MarketTick):
    """
    Central loop for processing live ticks in PAPER/LIVE mode.
    """
    try:
        # Update Broker State (Mark-to-Market)
        if paper_broker:
            paper_broker.update_market_state(tick.price, tick.timestamp, tick.symbol)
            
        # Execute Strategy (Route to correct instance)
        if tick.symbol in bot_strategies:
            await bot_strategies[tick.symbol].on_tick(tick)
            
    except Exception as e:
        logger.error(f"Tick Processing Error: {e}", exc_info=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_strategies, paper_broker
    
    # Startup
    logger.info("Gaia System Initialized", extra={"version": settings.APP_VERSION, "mode": settings.RUN_MODE})
    
    # 1. Start Resilience Services
    await persistence.init_db()
    await watchdog.start()
    
    if settings.RUN_MODE == "RECORDER":
        logger.info("Starting in RECORDER MODE - Trading Disabled")
        trading_control.stop_trading()
        await recorder.start()
        kraken_ws_client.add_listener(recorder.record_tick)

    elif settings.RUN_MODE == "PAPER":
        logger.info("Starting in PAPER MODE - Virtual Trading Active")
        trading_control.resume_trading()
        
        # A. Initialize Broker (Virtual/Backtest Broker for Paper Trading)
        # We start with $10,000 Paper Money
        paper_broker = BacktestBroker(initial_balance=10000.0)
        
        # B. Initialize AI
        ai_service = InferenceService()
        
        # C. Initialize Risk Manager
        # We increase max_position_size because Strategies now manage risk sizing dynamically.
        # Set to 1000.0 as a sanity limit.
        risk_engine = RiskManager(min_confidence=0.5, max_position_size=1000.0)
        
        # Wrap the Paper Broker with SafeBroker if we want risk checks
        from src.core.risk import SafeBroker
        safe_broker = SafeBroker(inner=paper_broker, risk_manager=risk_engine)

        # D. Initialize Strategies (Multi-Symbol)
        bot_strategies = {}
        for sym in settings.KRAKEN_SYMBOLS:
            bot_strategies[sym] = ReversePatternStrategy(
                symbol=sym,
                broker=safe_broker,
                filter_bearish=True,
                filter_bullish=True,
                inference_service=ai_service
            )
            logger.info(f"Strategy Initialized for {sym}")

        # E. Wire Data Feed
        # Also record data while trading for analysis
        await recorder.start()
        kraken_ws_client.add_listener(recorder.record_tick)
        kraken_ws_client.add_listener(on_tick_processor)
        
        # F. Recovery (Simulated)
        # In real LIVE mode, we would call recovery.reconcile(broker, exchange)
        # In PAPER, our 'exchange' is the empty BacktestBroker, so nothing to reconcile yet.
        
        telegram_service.set_broker(paper_broker)
        logger.info("PAPER Trading Environment Ready. Waiting for Ticks...")

    await telegram_service.start()
    await kraken_ws_client.start()
    
    yield
    
    # Shutdown
    logger.info("Shutdown Initiated...")
    await kraken_ws_client.stop()
    await telegram_service.stop()
    watchdog.stop()
    
    if settings.RUN_MODE in ["RECORDER", "PAPER"]:
        await recorder.stop()
        
    if paper_broker:
        stats = paper_broker.get_stats()
        logger.info(f"Paper Trading Session Ended. PnL: ${stats['pnl']:.2f}")

    logger.info("Gaia System Shutdown Complete")

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

async def main():
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Keep the app running
    stop_event = asyncio.Event()
    
    def handle_signal():
        stop_event.set()
        
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, handle_signal)
    loop.add_signal_handler(signal.SIGTERM, handle_signal)
    
    # Run application lifecycle
    async with lifespan(app):
        logger.info("Gaia Core Loop Running")
        await stop_event.wait()
        logger.info("Shutdown signal received")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
