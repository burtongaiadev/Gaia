import asyncio
import csv
import argparse
import logging
from datetime import datetime
from src.core.models import MarketTick
from src.core.broker import BacktestBroker
from src.strategies.reverse_pattern import ReversePatternStrategy
from src.core.inference import InferenceService

# Reset logger to output to console cleanly
logger = logging.getLogger("Gaia")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(ch)

class BacktestRunner:
    def __init__(self, filepath, symbol="PI_XBTUSD"):
        self.filepath = filepath
        self.symbol = symbol
        self.broker = BacktestBroker(initial_balance=10000.0)
        
        # Initialize AI
        self.inference = InferenceService()  # Will load models/model.tflite
        
        # Using default settings (filters off) for basic backtest
        self.strategy = ReversePatternStrategy(symbol, broker=self.broker, inference_service=self.inference)
        
    async def run(self):
        print(f"Starting Backtest on {self.filepath}...")
        
        count = 0
        try:
            with open(self.filepath, 'r') as f:
                reader = csv.reader(f)
                header = next(reader)  # Skip Header
                
                for row in reader:
                    if not row: continue
                    try:
                        ts = datetime.fromisoformat(row[0])
                        # Filter by symbol if mixed?
                        row_symbol = row[1]
                        if row_symbol != self.symbol:
                            continue
                            
                        price = float(row[2])
                        volume = float(row[3])
                        
                        # Update Broker
                        self.broker.update_market_state(price, ts)
                        
                        tick = MarketTick(
                            symbol=self.symbol,
                            price=price,
                            volume=volume,
                            timestamp=ts
                        )
                        
                        # Feed Strategy
                        await self.strategy.on_tick(tick)
                        count += 1
                        
                        if count % 10000 == 0:
                            print(f"Processed {count} ticks...", end='\r')
                            
                    except ValueError as e:
                        # Skip malformed lines
                        continue
                        
        except FileNotFoundError:
            print(f"Error: File {self.filepath} not found.")
            return

        # Final Report
        stats = self.broker.get_stats()
        print("\n\n=== Backtest Report ===")
        print(f"File: {self.filepath}")
        print(f"Ticks Processed: {count}")
        print(f"Trades Executed: {stats['trades_count']}")
        print(f"Final PnL: ${stats['pnl']:.2f}")
        print(f"Final Equity: ${stats['equity']:.2f}")
        print(f"Open Position: {stats['position']}")
        print("=======================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gaia Backtest Tool")
    parser.add_argument("--file", required=True, help="Path to CSV recording")
    parser.add_argument("--symbol", default="PI_XBTUSD", help="Symbol to backtest")
    
    args = parser.parse_args()
    
    runner = BacktestRunner(args.file, args.symbol)
    asyncio.run(runner.run())
