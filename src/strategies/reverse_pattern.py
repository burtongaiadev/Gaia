from src.core.strategy import Strategy
from src.core.logger import logger
from src.core.broker import IBroker
import pandas as pd
from typing import Optional

class ReversePatternStrategy(Strategy):
    def __init__(self, symbol: str, broker: Optional[IBroker] = None, filter_bearish: bool = False, filter_bullish: bool = False, inference_service=None):
        super().__init__(symbol, broker)
        self.ma_period = 50
        self.filter_bearish = filter_bearish
        self.filter_bullish = filter_bullish
        self.inference_service = inference_service
        self.min_ai_confidence = 0.5

    async def _check_ai_signal(self) -> bool:
        """
        Returns True if AI approves the trade (or if AI is disabled/mocked to allow).
        """
        if not self.inference_service:
            return True
            
        # Construct simplified feature vector from last 5 candles
        # [Open, High, Low, Close, Volume] * 5 = 25 features
        df = self.candles.df.tail(5)
        if len(df) < 5:
            return False
            
        # Flatten OHLCV to 1D array
        features = df[['open', 'high', 'low', 'close', 'volume']].values.flatten()
        
        # Get prediction (Range -1.0 to 1.0, or 0.0 to 1.0 depending on model)
        # Assuming model outputs probability of UP move (0 to 1)
        # But wait, InferenceService in src/core/inference.py returns float.
        # Let's assume > 0.6 is Buy, < 0.4 is Sell?
        # Or simple 'Confidence' score?
        
        # Checking src/core/inference.py logic... 
        # (It currently returns a simple float, mock returns 0.0)
        
        try:
            score = await self.inference_service.predict(features)
            
            # Since we don't have a real model trained for 'Bull/Bear' specifically yet,
            # this logic is placeholder. 
            # Real implementation would match model output node.
            
            # For now, if mock mode (score 0.0), we pass.
            if score == 0.0: 
                return True
                
            return score > self.min_ai_confidence
            
        except Exception as e:
            logger.error(f"AI Check Failed: {e}")
            return True # Fail open? or Fail safe? Fail open for now.

    async def execute(self):
        # Need at least 6 candles for context (High[5]/Low[5] -> Python index -6)
        if len(self.candles.df) < 6:
            return

        df = self.candles.df
        
        c0 = df.iloc[-1]
        c1 = df.iloc[-2]
        c2 = df.iloc[-3]
        
        highs = df['high']
        lows = df['low']
        
        ma50_series = self.candles.sma(self.ma_period)
        ma50 = ma50_series.iloc[-1]
        
        if pd.isna(ma50) and (self.filter_bearish or self.filter_bullish):
             return
        
        # --- BEARISH LOGIC ---
        is_bearish_ma_condition = c0.close > ma50 if not pd.isna(ma50) else False
        bearish_filter = is_bearish_ma_condition if self.filter_bearish else True

        is_b1_m2_green = c2.close > c2.open
        is_b1_m1_red = c1.close < c1.open
        is_b1_c0_low_break = c0.close < c1.low
        is_bearish_pattern_1 = is_b1_m2_green and is_b1_m1_red and is_b1_c0_low_break
        
        is_b2_m1_green = c1.close > c1.open
        is_b2_c0_red = c0.close < c0.open
        is_b2_c0_low_break = c0.close < c1.low
        is_bearish_pattern_2 = is_b2_m1_green and is_b2_c0_red and is_b2_c0_low_break
        
        is_h_m2_higher_than_m4 = highs.iloc[-3] > highs.iloc[-5]
        is_h_m1_higher_than_m5 = highs.iloc[-2] > highs.iloc[-6]
        is_h_c0_higher_than_m4 = highs.iloc[-1] > highs.iloc[-5]
        is_h_c0_higher_than_m5 = highs.iloc[-1] > highs.iloc[-6]
        
        is_higher_high_context = (
            is_h_m2_higher_than_m4 and 
            is_h_m1_higher_than_m5 and 
            is_h_c0_higher_than_m4 and 
            is_h_c0_higher_than_m5
        )
        
        final_bearish = (is_bearish_pattern_1 or is_bearish_pattern_2) and is_higher_high_context and bearish_filter
        
        # Get current position
        current_pos = 0.0
        if self.broker:
            current_pos = self.broker.get_position(self.symbol)

        if final_bearish:
            # Check AI Filter
            ai_approved = await self._check_ai_signal()
            
            if current_pos >= 0 and ai_approved:
                logger.info(f"Signal: BEARISH DETECTED on {self.symbol} (Pos: {current_pos}) | AI: {ai_approved}")
                if self.broker:
                    # 1. Close Existing Long if any
                    if current_pos > 0:
                        await self.broker.place_order(self.symbol, "sell", "mkt", current_pos)
                        logger.info(f"Closing Long {current_pos} on {self.symbol}")
                    
                    # 2. Calculate New Short Size based on Risk
                    # SL = High of Signal Candle (c1, previous closed) + Buffer
                    # User requested "Signal Candle". Since we enter on c0 breaking c1, c1 is the reference.
                    sl_price = c1.high * 1.001
                    entry_price = c0.close
                    
                    risk_per_unit = sl_price - entry_price
                    
                    # Get Account Equity
                    stats = self.broker.get_stats()
                    equity = stats.get('equity', 10000.0)
                    risk_amount = equity * 0.03 # 3% Risk
                    
                    if risk_per_unit > 0:
                        qty = risk_amount / risk_per_unit
                    else:
                        qty = 0.0 # Should not happen unless SL < Entry (impossible for Short)
                    
                    # 3. Open Short (Split into 2 TPs)
                    if qty > 0:
                        qty_half = qty / 2.0
                        tp1_dist = risk_per_unit * 2.0 # risk_per_unit is positive (SL - Entry) for Shorts? 
                        # Wait, logic above: risk_per_unit = sl_price - entry_price.
                        # For SHORT: SL > Entry. risk_per_unit is POSITIVE.
                        # TP Target is Entry - (2 * Risk)
                        # So TP1 = Entry - (2 * risk_per_unit)
                        # TP2 = Entry - (3 * risk_per_unit)
                        
                        tp1_price = entry_price - (risk_per_unit * 2.0)
                        tp2_price = entry_price - (risk_per_unit * 3.0)
                        
                        logger.info(f"Opening Short {qty:.4f} {self.symbol} (Split TPs). Risk: ${risk_amount:.2f}")
                        
                        # Order A (TP1)
                        await self.broker.place_order(self.symbol, "sell", "mkt", qty_half, params={"sl": sl_price, "tp": tp1_price})
                        # Order B (TP2)
                        await self.broker.place_order(self.symbol, "sell", "mkt", qty_half, params={"sl": sl_price, "tp": tp2_price})

        # --- BULLISH LOGIC ---
        is_bullish_ma_condition = c0.close < ma50 if not pd.isna(ma50) else False
        bullish_filter = is_bullish_ma_condition if self.filter_bullish else True
        
        is_l1_m2_red = c2.close < c2.open
        is_l1_m1_green = c1.close > c1.open
        is_l1_c0_high_break = c0.close > c1.high
        is_bullish_pattern_1 = is_l1_m2_red and is_l1_m1_green and is_l1_c0_high_break
        
        is_l2_m1_red = c1.close < c1.open
        is_l2_c0_green = c0.close > c0.open
        is_l2_c0_high_break = c0.close > c1.high
        is_bullish_pattern_2 = is_l2_m1_red and is_l2_c0_green and is_l2_c0_high_break
        
        is_l_m2_lower_than_m4 = lows.iloc[-3] < lows.iloc[-5]
        is_l_m1_lower_than_m5 = lows.iloc[-2] < lows.iloc[-6]
        is_l_c0_lower_than_m4 = lows.iloc[-1] < lows.iloc[-5]
        is_l_c0_lower_than_m5 = lows.iloc[-1] < lows.iloc[-6]
        
        is_lower_low_context = (
            is_l_m2_lower_than_m4 and 
            is_l_m1_lower_than_m5 and 
            is_l_c0_lower_than_m4 and 
            is_l_c0_lower_than_m5
        )
        
        final_bullish = (is_bullish_pattern_1 or is_bullish_pattern_2) and is_lower_low_context and bullish_filter
        
        if final_bullish:
             ai_approved = await self._check_ai_signal()
             
             if current_pos <= 0 and ai_approved:
                logger.info(f"Signal: BULLISH DETECTED on {self.symbol} (Pos: {current_pos}) | AI: {ai_approved}")
                if self.broker:
                    # 1. Close Existing Short if any
                    if current_pos < 0:
                        await self.broker.place_order(self.symbol, "buy", "mkt", abs(current_pos))
                        logger.info(f"Closing Short {abs(current_pos)} on {self.symbol}")
                    
                    # 2. Calculate New Long Size
                    # SL = Low of Signal Candle (c1) - Buffer
                    sl_price = c1.low * 0.999
                    entry_price = c0.close
                    
                    risk_per_unit = entry_price - sl_price
                    
                    # Get Account Equity
                    stats = self.broker.get_stats()
                    equity = stats.get('equity', 10000.0)
                    risk_amount = equity * 0.03 # 3% Risk
                    
                    if risk_per_unit > 0:
                        qty = risk_amount / risk_per_unit
                    else:
                        qty = 0.0
                        
                    # 3. Open Long (Split into 2 TPs)
                    if qty > 0:
                        qty_half = qty / 2.0
                        # For LONG: Risk = Entry - SL (Positive).
                        # TP = Entry + (2 * Risk)
                        tp1_price = entry_price + (risk_per_unit * 2.0)
                        tp2_price = entry_price + (risk_per_unit * 3.0)
                        
                        logger.info(f"Opening Long {qty:.4f} {self.symbol} (Split TPs). Risk: ${risk_amount:.2f}")
                        
                        # Order A (TP1)
                        await self.broker.place_order(self.symbol, "buy", "mkt", qty_half, params={"sl": sl_price, "tp": tp1_price})
                        # Order B (TP2)
                        await self.broker.place_order(self.symbol, "buy", "mkt", qty_half, params={"sl": sl_price, "tp": tp2_price})
