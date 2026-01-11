import logging
from typing import Optional, Dict, Any
from src.core.broker import IBroker

logger = logging.getLogger("Gaia")

class RiskManager:
    def __init__(self, min_confidence: float = 0.70, max_position_size: float = 5.0):
        self.min_confidence = min_confidence
        self.max_position_size = max_position_size
        
        # Stats tracking if needed
        self.rejections = 0

    def validate_order(self, current_position: float, size: float, params: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validates if an order is safe to place.
        Returns True if safe, False otherwise.
        """
        # 1. AI Confidence Check
        if params and "ai_confidence" in params:
            confidence = params["ai_confidence"]
            if confidence < self.min_confidence:
                logger.warning(f"Risk Reject: Low Confidence ({confidence:.2f} < {self.min_confidence})")
                self.rejections += 1
                return False
        
        # 2. Max Position Size (Exposure) Check
        # If buying, new_pos = curr + size. If selling, new_pos = curr - size? 
        # Need to know side. Assuming size is absolute.
        # Ideally, we check current ABS exposure.
        # This is strictly Pre-Trade.
        return True

    def validate_execution(self, symbol: str, current_pos: float, new_size: float, side: str):
        # Calculate resulting position
        result_pos = current_pos
        if side == "buy":
            result_pos += new_size
        elif side == "sell":
            result_pos -= new_size
            
        if abs(result_pos) > self.max_position_size:
            logger.warning(f"Risk Reject: Max Position Limit ({abs(result_pos)} > {self.max_position_size})")
            self.rejections += 1
            return False
            
        return True

class SafeBroker(IBroker):
    """
    Proxy that wraps a real Broker (or BacktestBroker) and enforces Risk Rules.
    """
    def __init__(self, inner: IBroker, risk_manager: RiskManager):
        self.inner = inner
        self.risk_manager = risk_manager

    def get_position(self, symbol: str):
        return self.inner.get_position(symbol)

    async def place_order(self, symbol: str, side: str, order_type: str, size: float, price: Optional[float] = None, params: Optional[Dict[str, Any]] = None):
        # 1. Get Current State
        current_pos = self.inner.get_position(symbol)
        
        # 2. Validate General Rules (Confidence)
        if not self.risk_manager.validate_order(current_pos, size, params):
            return # Blocked
            
        # 3. Validate Execution Limits (Exposure)
        if not self.risk_manager.validate_execution(symbol, current_pos, size, side):
            return # Blocked

        # 4. Pass through to Inner Broker
        await self.inner.place_order(symbol, side, order_type, size, price, params)
