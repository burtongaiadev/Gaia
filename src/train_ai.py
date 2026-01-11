import pandas as pd
import numpy as np
import tensorflow as tf
import os
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Trainer")

# Constants
DATA_FILE = "data/raw/history_synth_PI_XBTUSD_3Y.csv"
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "model.tflite")
LOOKBACK = 5  # Number of past candles to analyze
FUTURE_HORIZON = 5 # Number of candles into future to predict
TARGET_PCT = 0.001 # 0.1% move required to be a "Buy"

def load_and_prep_data(filepath):
    logger.info(f"Loading data from {filepath}...")
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Simple feature engineering: Normalize changes
    # We use Log Returns for stability
    df['close_pct'] = df['price'].pct_change()
    df['vol_pct'] = df['volume'].pct_change()
    
    # Drop NaNs created by pct_change
    df = df.dropna().reset_index(drop=True)
    
    logger.info(f"Data Loaded: {len(df)} rows.")
    return df

def create_dataset(df):
    logger.info("Generating Features and Labels...")
    
    features = []
    labels = []
    
    # Convert columns to numpy for speed
    closes = df['price'].values
    opens = df['price'].values # In synth ticks, open~close sometimes, typically we'd use 'price' for all since it's ticks-as-candles csv usually? 
    # Wait, the downloader saves: timestamp, symbol, price, volume. 
    # BUT Backtester aggregates these into Candles.
    # Training on RAW TICKS is too noisy.
    # We should RESAMPLE the ticks into 1-minute candles for Training first!
    
    # ... Resampling Logic ...
    logger.info("Resampling ticks to 1-minute candles...")
    df_candles = df.set_index('timestamp').resample('1min').agg({
        'price': 'ohlc',
        'volume': 'sum'
    }).dropna()
    
    # Flatten MultiIndex columns (price -> open, high, low, close)
    df_candles.columns = ['open', 'high', 'low', 'close', 'volume']
    
    # Normalize features (Price relative to Open of that candle, or pct change)
    # Let's use basic normalization: (Value - Mean) / Std for the window
    # Actually, simpler for TFLite robustness: % change from window start.
    
    data = df_candles.values
    # data columns: 0=open, 1=high, 2=low, 3=close, 4=volume
    
    # We iterate through the data
    for i in range(LOOKBACK, len(data) - FUTURE_HORIZON):
        # Window of past LOOKBACK candles
        window = data[i-LOOKBACK:i] 
        current_price = window[-1, 3] # Close of last candle in window
        
        # TARGET: Look into future
        future_window = data[i:i+FUTURE_HORIZON]
        future_max = np.max(future_window[:, 1]) # Max High
        future_min = np.min(future_window[:, 2]) # Min Low
        future_close = future_window[-1, 3]
        
        # Labeling Logic:
        # If price goes up by TARGET_PCT within horizon -> Class 1 (Buy)
        # Else -> Class 0 (Ignore/Sell)
        
        # Simplest: Did close go up > 0.1% ?
        target_return = (future_close - current_price) / current_price
        
        label = 1 if target_return > TARGET_PCT else 0
        
        # Normalize Input Window
        # We normalize everything relative to the first candle OPEN in the window
        base_price = window[0, 0] # Open of first candle
        
        # Avoid division by zero
        if base_price == 0: continue
            
        # Select OHLCV (columns 0-4)
        # Normalize Price columns (0,1,2,3) by base_price
        norm_window = np.copy(window)
        norm_window[:, :4] = (window[:, :4] / base_price) - 1.0 # Percentage change from base
        
        # Normalize Volume (col 4) - harder, maybe log scale?
        # Let's just create log volume
        norm_window[:, 4] = np.log1p(window[:, 4])
        
        # Flatten for Dense input: 5 candles * 5 features = 25 inputs
        flat_features = norm_window.flatten()
        
        features.append(flat_features)
        labels.append(label)
        
    return np.array(features, dtype=np.float32), np.array(labels, dtype=np.float32)

def train_model():
    df = load_and_prep_data(DATA_FILE)
    X, y = create_dataset(df)
    
    logger.info(f"Training Set Size: {len(X)}")
    
    # Split Train/Test
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    # Build Model
    model = tf.keras.Sequential([
        # Input shape: LOOKBACK * 5 features
        tf.keras.layers.Dense(64, activation='relu', input_shape=(X.shape[1],)),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid') # Binary Classification (Buy or Not)
    ])
    
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    
    # Train
    logger.info("Training Model...")
    model.fit(X_train, y_train, epochs=5, batch_size=64, validation_data=(X_test, y_test))
    
    # Evaluate
    loss, acc = model.evaluate(X_test, y_test)
    logger.info(f"Test Accuracy: {acc:.4f}")
    
    # Convert to TFLite
    logger.info("Converting to TFLite...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_model = converter.convert()
    
    # Save
    with open(MODEL_PATH, "wb") as f:
        f.write(tflite_model)
        
    logger.info(f"Model saved to {MODEL_PATH}")
    logger.info("You can now run backtest with real AI filtering.")

if __name__ == "__main__":
    train_model()
