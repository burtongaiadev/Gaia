import asyncio
import csv
import os
import httpx
from datetime import datetime, timezone, timedelta
import time

# Binance Symbol to mimic Kraken's PI_XBTUSD
BINANCE_SYMBOL = "BTCUSDT"
TARGET_SYMBOL = "PI_XBTUSD"
DAYS_HISTORY = 1095  # 3 Years

async def fetch_candles(client, symbol, start_ts, end_ts):
    url = "https://fapi.binance.com/fapi/v1/klines"
    limit = 1500 # Binance max limit
    
    params = {
        "symbol": symbol,
        "interval": "1m",
        "limit": limit,
        "startTime": int(start_ts * 1000),
        "endTime": int(end_ts * 1000)
    }
    
    try:
        resp = await client.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Request failed: {e}")
        return []

async def main():
    print(f"Starting bulk download: {DAYS_HISTORY} days of 1m data for {BINANCE_SYMBOL}...")
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=DAYS_HISTORY)
    
    current_start = start_date.timestamp()
    final_end = end_date.timestamp()
    
    os.makedirs("data/raw", exist_ok=True)
    filename = f"data/raw/history_synth_{TARGET_SYMBOL}_3Y.csv"
    
    total_candles = 0
    
    async with httpx.AsyncClient() as client:
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "symbol", "price", "volume"])
            
            print(f"Fetching data from {start_date.isoformat()} to {end_date.isoformat()}")
            
            while current_start < final_end:
                # Fetch next batch
                batch = await fetch_candles(client, BINANCE_SYMBOL, current_start, final_end)
                
                if not batch or not isinstance(batch, list):
                    print("No data returned or error. Retrying in 2s...")
                    await asyncio.sleep(2)
                    continue

                # Process batch
                for c in batch:
                    try:
                        ts_ms = c[0]
                        o = float(c[1])
                        h = float(c[2])
                        l = float(c[3])
                        cl = float(c[4])
                        v = float(c[5])
                        
                        # Generate 4 synthetic ticks
                        dt = datetime.fromtimestamp(ts_ms/1000, timezone.utc)
                        
                        # 1. Open
                        writer.writerow([dt.isoformat(), TARGET_SYMBOL, o, v/4])
                        # 2. High
                        writer.writerow([(dt + timedelta(seconds=15)).isoformat(), TARGET_SYMBOL, h, v/4])
                        # 3. Low
                        writer.writerow([(dt + timedelta(seconds=30)).isoformat(), TARGET_SYMBOL, l, v/4])
                        # 4. Close
                        writer.writerow([(dt + timedelta(seconds=59)).isoformat(), TARGET_SYMBOL, cl, v/4])
                    except ValueError:
                        continue

                count = len(batch)
                total_candles += count
                
                # Update start time for next batch to be (last_candle_close_time + 1ms)
                # kline: [open_time, open, high, low, close, vol, close_time, ...]
                last_close_ts = batch[-1][6] 
                current_start = (last_close_ts + 1) / 1000.0
                
                # Progress
                progress = (current_start - start_date.timestamp()) / (final_end - start_date.timestamp())
                progress = min(max(progress, 0), 1.0)
                print(f"Progress: {progress:.1%} | Total Candles: {total_candles} | Current: {dt}")
                
                if count < 1500:
                    # We reached the end of available data (if less than limit returned)
                    break
                    
                # Rate limit safety
                await asyncio.sleep(0.1)

    print(f"\nSuccess! Saved {total_candles} candles ({total_candles*4} ticks) to: {filename}")
    print(f"You can now use this file for training or huge backtests.")

if __name__ == "__main__":
    asyncio.run(main())
