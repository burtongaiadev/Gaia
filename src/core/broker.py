from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from src.core.logger import logger
import uuid

class IBroker(ABC):
    @abstractmethod
    async def place_order(self, symbol: str, side: str, order_type: str, size: float, price: Optional[float] = None, params: Optional[Dict[str, Any]] = None):
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> float:
        pass

class BacktestBroker(IBroker):
    def __init__(self, initial_balance=10000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.trades = []
        self.position = 0.0
        self.current_price = 0.0
        self.current_time = None
        
        # Bracket Management
        self.active_orders = [] # List of dicts representing open Limit/Stop orders

    def update_market_state(self, price: float, timestamp):
        self.current_price = price
        self.current_time = timestamp
        self._check_triggers(price, timestamp)

    def _check_triggers(self, price: float, timestamp):
        """Check if any active orders are triggered by current price"""
        filled_bracket_ids = []
        
        # Iterate copy to allow modification
        for order in self.active_orders[:]:
            trigger = False
            side = order['side']
            trigger_price = order['price']
            o_type = order['type']
            
            # Logic for STOP and LIMIT fills
            if side == 'sell':
                # Sell Stop (SL for Long): Price drops below trigger
                if o_type == 'stop' and price <= trigger_price:
                    trigger = True
                # Sell Limit (TP for Long): Price rises above trigger
                elif o_type == 'limit' and price >= trigger_price:
                    trigger = True
            elif side == 'buy':
                # Buy Stop (SL for Short): Price rises above trigger
                if o_type == 'stop' and price >= trigger_price:
                    trigger = True
                # Buy Limit (TP for Short): Price drops below trigger
                elif o_type == 'limit' and price <= trigger_price:
                    trigger = True
                    
            if trigger:
                self._execute_trade(order['symbol'], side, order['size'], price, timestamp, o_type)
                self.active_orders.remove(order)
                if 'bracket_id' in order:
                    filled_bracket_ids.append(order['bracket_id'])

        # OCO Logic: Cancel siblings
        if filled_bracket_ids:
            self.active_orders = [o for o in self.active_orders if o.get('bracket_id') not in filled_bracket_ids]

    def _execute_trade(self, symbol, side, size, price, timestamp, type_str):
        cost = price * size
        if side == "buy":
            self.position += size
            self.balance -= cost
        elif side == "sell":
            self.position -= size
            self.balance += cost
            
        self.trades.append({
            "symbol": symbol, "side": side, "size": size, 
            "price": price, "time": timestamp, "type": type_str
        })
        logger.info(f"[BACKTEST] FILLED-TRIGGER {side.upper()} {size} @ {price} ({type_str})")

    async def place_order(self, symbol: str, side: str, order_type: str, size: float, price: Optional[float] = None, params: Optional[Dict[str, Any]] = None):
        if self.current_price <= 0:
            return

        # 1. Execute Main Market Order
        fill_price = self.current_price
        self._execute_trade(symbol, side, size, fill_price, self.current_time, "market")
        
        # 2. Handle Brackets (sl, tp parameters)
        if params:
            sl_price = params.get('sl')
            tp_price = params.get('tp')
            
            if sl_price or tp_price:
                bracket_id = str(uuid.uuid4())
                exit_side = "sell" if side == "buy" else "buy"
                
                if sl_price:
                    self.active_orders.append({
                        "symbol": symbol, "side": exit_side, "size": size,
                        "price": sl_price, "type": "stop", "bracket_id": bracket_id
                    })
                    logger.info(f"[BACKTEST] PLACED STOP {exit_side} @ {sl_price}")
                    
                if tp_price:
                    self.active_orders.append({
                        "symbol": symbol, "side": exit_side, "size": size,
                        "price": tp_price, "type": "limit", "bracket_id": bracket_id
                    })
                    logger.info(f"[BACKTEST] PLACED LIMIT {exit_side} @ {tp_price}")

    def get_position(self, symbol: str) -> float:
        return self.position

    def get_stats(self):
        equity = self.balance + (self.position * self.current_price)
        pnl = equity - self.initial_balance
        return {
            "equity": equity,
            "pnl": pnl,
            "trades_count": len(self.trades),
            "position": self.position
        }
