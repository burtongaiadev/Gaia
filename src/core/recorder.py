import os
import csv
import asyncio
from datetime import datetime
from src.core.models import MarketTick
from src.core.logger import logger
from src.config import settings

class DataRecorder:
    def __init__(self, data_dir="data/raw"):
        self.data_dir = data_dir
        self.queue = asyncio.Queue()
        self.running = False
        self._task = None
        self.current_date = None
        self.file_handle = None
        self.csv_writer = None
        
        # Ensure dir
        os.makedirs(self.data_dir, exist_ok=True)

    async def start(self):
        self.running = True
        self._task = asyncio.create_task(self._process_queue())
        logger.info(f"Data Recorder Started. Storage: {self.data_dir}")

    async def stop(self):
        self.running = False
        if self._task:
            # Wait for queue to empty if we care about last ticks
            # Or just cancel if we need fast shutdown.
            # Best effort:
            if not self.queue.empty():
                try:
                    await asyncio.wait_for(self.queue.join(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
            self._task.cancel()
        self._close_file()
        logger.info("Data Recorder Stopped")

    async def record_tick(self, tick: MarketTick):
        if self.running:
            await self.queue.put(tick)

    async def _process_queue(self):
        batch = []
        while self.running:
            try:
                # Wait for at least one
                tick = await self.queue.get()
                batch.append(tick)
                
                # Drain queue (max 100)
                count = 0
                while not self.queue.empty() and count < 100:
                    batch.append(self.queue.get_nowait())
                    count += 1
                
                # Write batch via Executor
                await asyncio.to_thread(self._write_batch, list(batch))
                
                # Mark done
                for _ in batch:
                    self.queue.task_done()
                batch.clear()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Recorder Error: {e}")

    def _write_batch(self, batch):
        if not batch:
            return
            
        first_tick = batch[0]
        now_date = first_tick.timestamp.date().isoformat()
        
        if now_date != self.current_date:
            self._rotate_file(now_date)

        if not self.file_handle:
            self._rotate_file(now_date)
            
        try:
            for tick in batch:
                self.csv_writer.writerow([
                    tick.timestamp.isoformat(),
                    tick.symbol,
                    tick.price,
                    tick.volume
                ])
            self.file_handle.flush()
        except Exception as e:
            logger.error(f"Write Batch Error: {e}")

    def _rotate_file(self, new_date):
        self._close_file()
        self.current_date = new_date
        filename = f"ticker_{new_date}.csv"
        filepath = os.path.join(self.data_dir, filename)
        
        exists = os.path.exists(filepath)
        self.file_handle = open(filepath, 'a', newline='')
        self.csv_writer = csv.writer(self.file_handle)
        
        if not exists:
            self.csv_writer.writerow(["time", "symbol", "price", "volume"])
            
        logger.info(f"Recorder rotated to {filename}")

    def _close_file(self):
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None
            self.csv_writer = None

recorder = DataRecorder()
