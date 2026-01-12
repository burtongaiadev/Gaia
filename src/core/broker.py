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
        self.positions = {} # {symbol: size} - Multi-symbol support
        self.last_prices = {}
        self.notifier = None # {symbol: price}
        self.current_time = None
        
        # Bracket Management
        self.active_orders = [] # List of dicts representing open Limit/Stop orders

    def update_market_state(self, price: float, timestamp, symbol: str):
        self.last_prices[symbol] = price
        self.current_time = timestamp
        self._check_triggers(price, timestamp, symbol)

    def _check_triggers(self, price: float, timestamp, symbol: str):
        """Check if any active orders are triggered by current price"""
        filled_bracket_ids = []
        
        # Iterate copy to allow modification. Only check orders for THIS symbol.
        for order in self.active_orders[:]:
            if order.get('symbol') != symbol:
                continue
                
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

    def set_notifier(self, callback):
        self.notifier = callback

    async def _execute_trade(self, symbol: str, side: str, qty: float, price: float, type_: str):
        cost = qty * price
        
        # Simple execution logic
        if side == "buy":
            self.positions[symbol] = self.positions.get(symbol, 0.0) + qty
            self.balance -= cost
        elif side == "sell":
            prev_pos = self.positions.get(symbol, 0.0)
            self.positions[symbol] = prev_pos - qty
            self.balance += cost
            
        trade_id = str(uuid.uuid4())
        self.trades.append({
            "id": trade_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "timestamp": datetime.utcnow()
        })
        
        entry = f"[BACKTEST] FILLED-TRIGGER {side.upper()} {qty} {symbol} @ {price} ({type_})"
        logger.info(entry)
        
        # Notify
        if self.notifier:
            try:
                # Format a nice message
                icon = "🟢" if side == "buy" else "🔴"
                msg = f"{icon} Executed: {side.upper()} {qty:.4f} {symbol} @ ${price:.2f}"
                await self.notifier(msg)
            except Exception as e:
                logger.error(f"Notification failed: {e}")

    async def place_order(self, symbol: str, side: str, order_type: str, size: float, price: Optional[float] = None, params: Optional[Dict[str, Any]] = None):
        last_price = self.last_prices.get(symbol, 0.0)
        if last_price <= 0:
            logger.warning(f"Cannot place order for {symbol}: No price data yet.")
            return

        # 1. Execute Main Market Order
        fill_price = last_price
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
                    logger.info(f"[BACKTEST] PLACED STOP {exit_side} {symbol} @ {sl_price}")
                    
                if tp_price:
                    self.active_orders.append({
                        "symbol": symbol, "side": exit_side, "size": size,
                        "price": tp_price, "type": "limit", "bracket_id": bracket_id
                    })
                    logger.info(f"[BACKTEST] PLACED LIMIT {exit_side} {symbol} @ {tp_price}")

    def get_position(self, symbol: str) -> float:
        return self.positions.get(symbol, 0.0)

    def get_stats(self):
        # Calculate Equity: Balance + Sum(Position * LastPrice)
        equity = self.balance
        for sym, pos in self.positions.items():
            if pos != 0:
                price = self.last_prices.get(sym, 0.0)
                equity += (pos * price)
                
        pnl = equity - self.initial_balance
        return {
            "equity": equity,
            "balance": self.balance,
            "pnl": pnl,
            "trades_count": len(self.trades),
            "positions": {k:v for k,v in self.positions.items() if v != 0}
        }
