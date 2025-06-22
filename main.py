import websocket
import json
import logging
import time
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from delta_rest_client import DeltaRestClient, OrderType, TimeInForce
from config import DELTA_CONFIG, TRADING_CONFIG, STRATEGY_CONFIG, TELEGRAM_CONFIG

# Enable websocket-client debug trace
websocket.enableTrace(True)

class LiveTrader:
    def __init__(self):
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trading.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = TRADING_CONFIG
        self.telegram_config = TELEGRAM_CONFIG
        self.strategy_config = STRATEGY_CONFIG
        
        # Initialize Delta Exchange API
        self.client = DeltaRestClient(
            base_url=DELTA_CONFIG['base_url'],
            api_key=DELTA_CONFIG['api_key'],
            api_secret=DELTA_CONFIG['api_secret']
        )
        
        # Trading parameters
        self.symbol = self.config['symbol']
        self.product_id = self.config['product_id']
        self.timeframe = self.config['timeframe']
        self.stop_loss_pct = 0.02  # 2% for 15m timeframe
        self.trailing_stop_pct = 0.015  # 01.5% for 15m timeframe
        
        # Strategy parameters
        self.sensitivity = 0.015  # 1.5% for 15mtimeframe
        self.min_volume_percentile = 50
        self.trend_period = 20  # 20 for 15m timeframe
        self.min_trades_distance = 10  # 10 for 15m timeframe
        
        # Initialize data structures
        self.candles = []
        self.current_position = None  # None: no position, 'long': long position, 'short': short position
        self.stop_loss_price = None
        self.trailing_stop_price = None
        self.entry_price = None
        self.last_trade_index = -self.min_trades_distance
        self.position_size = 0
        self.last_heartbeat = time.time()
        self.ws = None  # WebSocket instance
        self.is_ws_connected = False
        
        # Initialize account tracking
        self.initial_capital = 100  # Starting with $100
        self.current_capital = self.initial_capital
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0
        
        # Try to get initial wallet balance for verification
        try:
            # Get USDT balance (asset_id = 3)
            usdt_balance = self.client.get_balances(asset_id=3)
            self.logger.info(f"USDT Balance: {usdt_balance}")
            self.available_balance = float(usdt_balance['available_balance'])
            self.send_telegram_message(
                f"🚀 Bot Started\n"
                f"Initial Capital: ${self.initial_capital}\n"
                f"Exchange Balance: ${self.available_balance}"
            )
        except Exception as e:
            self.logger.error(f"Error getting wallet balances: {str(e)}")
            self.available_balance = 0
            self.send_telegram_message(f"⚠️ Bot Started with error: {str(e)}")

    def send_telegram_message(self, message):
        """Send message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_config['bot_token']}/sendMessage"
            data = {
                "chat_id": self.telegram_config['chat_id'],
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=data)
            if not response.ok:
                self.logger.error(f"Failed to send Telegram message: {response.text}")
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {str(e)}")

    def on_ping(self, ws, message):
        """Handle ping message by sending a pong response"""
        ws.send(json.dumps({"type": "pong"}))
        self.last_heartbeat = time.time()
        self.logger.debug("Received ping, sent pong")

    def on_pong(self, ws, message):
        """Handle pong message"""
        self.last_heartbeat = time.time()
        self.logger.debug("Received pong")

    def check_connection_health(self):
        """Check if connection is healthy"""
        current_time = time.time()
        if current_time - self.last_heartbeat > 30:  # Reduced from 60 to 30 seconds
            self.logger.warning("No heartbeat received for over 30 seconds")
            self.send_telegram_message("⚠️ Warning: No market data received for over 30 seconds")
            if self.ws and self.is_ws_connected:
                self.logger.info("Sending ping to check connection")
                try:
                    self.ws.send(json.dumps({"type": "ping"}))
                except Exception as e:
                    self.logger.error(f"Failed to send ping: {str(e)}")
                    self.is_ws_connected = False
                    return False
            return False
        return True

    def calc_indicators(self, df):
        """Calculate technical indicators"""
        # Calculate percentage change over 4 bars
        df['pc'] = (df['open'] - df['open'].shift(4)) / df['open'].shift(4) * 100
        
        # Calculate volume metrics
        df['volume_ma'] = df['volume'].rolling(window=20).mean() 
        df['volume_percentile'] = df['volume'].rolling(window=50).apply(  
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100
        )
        
        # Calculate trend indicators
        df['sma20'] = df['close'].rolling(window=self.trend_period).mean()
        df['sma50'] = df['close'].rolling(window=50).mean()  
        
        # Calculate ATR for volatility filtering
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=14).mean()  
        
        # Momentum indicator
        df['roc'] = (df['close'] - df['close'].shift(10)) / df['close'].shift(10) * 100  

    def is_valid_trade_condition(self, df, idx, trade_type='long'):
        """Check if trade conditions are valid"""
        # Check if enough distance from last trade
        if idx - self.last_trade_index < self.min_trades_distance:
            return False
            
        # Check volume conditions
        if df['volume_percentile'].iloc[idx] < self.min_volume_percentile:
            return False
            
        # Check trend conditions
        if trade_type == 'long':
            if not (df['sma20'].iloc[idx] > df['sma50'].iloc[idx] and
                   df['roc'].iloc[idx] > 0):
                return False
        else:  # short
            if not (df['sma20'].iloc[idx] < df['sma50'].iloc[idx] and
                   df['roc'].iloc[idx] < 0):
                return False
                
        # Volatility check - avoid excessive volatility
        current_atr = df['atr'].iloc[idx]
        avg_atr = df['atr'].rolling(window=20).mean().iloc[idx]
        if current_atr > avg_atr * 1.5:  # Skip if volatility is too high
            return False
            
        return True

    def place_order(self, side, size, order_type='market', price=None, stop_price=None):
        """Place an order"""
        try:
            order_params = {
                'product_id': self.product_id,
                'size': size,
                'side': side.lower(),
                'order_type': OrderType.MARKET if order_type == 'market' else OrderType.LIMIT,
                'time_in_force': TimeInForce.IOC if order_type == 'market' else TimeInForce.GTC
            }
            
            if price and order_type != 'market':
                order_params['limit_price'] = str(price)
            if stop_price:
                order_params['stop_price'] = str(stop_price)
                
            response = self.client.place_order(**order_params)
            self.logger.info(f"Order placed: {response}")
            
            # Send Telegram notification
            order_type_str = "Stop Loss" if stop_price else "Market"
            self.send_telegram_message(
                f"📊 {order_type_str} Order Placed\n"
                f"Side: {side}\n"
                f"Size: {size}\n"
                f"Price: {'Market' if order_type == 'market' else price}\n"
                f"Stop Price: {stop_price if stop_price else 'N/A'}"
            )
            
            return response
        except Exception as e:
            error_msg = f"Error placing order: {str(e)}"
            self.logger.error(error_msg)
            self.send_telegram_message(f"⚠️ {error_msg}")
            return None

    def update_trade_stats(self, pnl):
        """Update trading statistics"""
        self.total_trades += 1
        self.total_pnl += pnl
        if pnl > 0:
            self.winning_trades += 1
        
        win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        avg_pnl = self.total_pnl / self.total_trades if self.total_trades > 0 else 0
        
        stats = (
            f"📊 Trade Statistics\n"
            f"Total Trades: {self.total_trades}\n"
            f"Win Rate: {win_rate:.2f}%\n"
            f"Total PnL: ${self.total_pnl:.2f}\n"
            f"Average PnL: ${avg_pnl:.2f}\n"
            f"Current Capital: ${self.current_capital:.2f}"
        )
        self.send_telegram_message(stats)

    def execute_trade(self, signal_type, current_price):
        """Execute a trade based on the signal"""
        try:
            # Use entire current capital for position sizing (compounding)
            position_value = self.current_capital
            size = position_value / current_price
            
            # Close existing position if any
            if self.current_position:
                close_side = 'sell' if self.current_position == 'long' else 'buy'
                self.place_order(close_side, self.position_size)
                
                # Calculate PnL
                if self.current_position == 'long':
                    pnl = (current_price - self.entry_price) / self.entry_price * self.current_capital
                else:  # short
                    pnl = (self.entry_price - current_price) / self.entry_price * self.current_capital
                
                # Update capital
                self.current_capital += pnl
                
                # Log trade result
                self.logger.info(f"Closed {self.current_position} position at {current_price}")
                self.send_telegram_message(
                    f"🔄 Position Closed\n"
                    f"Type: {self.current_position}\n"
                    f"Entry: ${self.entry_price}\n"
                    f"Exit: ${current_price}\n"
                    f"Size: {self.position_size}\n"
                    f"PnL: ${pnl:.2f}\n"
                    f"Current Capital: ${self.current_capital:.2f}"
                )
                
                # Update trade statistics
                self.update_trade_stats(pnl)
            
            # If it's a close signal, don't open new position
            if signal_type == 'close':
                return
            
            # Open new position
            side = 'buy' if signal_type == 'long' else 'sell'
            order = self.place_order(side, size)
            
            if order:
                self.current_position = signal_type
                self.entry_price = current_price
                self.position_size = size
                
                # Set stop loss
                self.stop_loss_price = (
                    current_price * (1 - self.stop_loss_pct) if signal_type == 'long'
                    else current_price * (1 + self.stop_loss_pct)
                )
                
                # Set initial trailing stop same as stop loss
                self.trailing_stop_price = self.stop_loss_price
                
                # Place stop loss order
                stop_side = 'sell' if signal_type == 'long' else 'buy'
                self.place_order(stop_side, size, 'stop_market', stop_price=self.stop_loss_price)
                
                trade_info = (
                    f"✅ New {signal_type.upper()} Position\n"
                    f"Entry Price: ${current_price}\n"
                    f"Size: {size}\n"
                    f"Value: ${self.current_capital:.2f}\n"
                    f"Stop Loss: ${self.stop_loss_price}\n"
                    f"Risk: 2%\n"
                    f"Trailing Stop: 1.5%"
                )
                self.logger.info(trade_info)
                self.send_telegram_message(trade_info)
                
        except Exception as e:
            error_msg = f"Error executing trade: {str(e)}"
            self.logger.error(error_msg)
            self.send_telegram_message(f"⚠️ {error_msg}")

    def process_candle(self, candle_data):
        """Process candlestick data and update trading logic"""
        try:
            self.last_heartbeat = time.time()  # Update heartbeat
            self.logger.info(f"Processing candle: {candle_data}")
            
            # Add candle to our list
            candle = {
                'timestamp': datetime.fromtimestamp(candle_data['time']),
                'open': float(candle_data['open']),
                'high': float(candle_data['high']),
                'low': float(candle_data['low']),
                'close': float(candle_data['close']),
                'volume': float(candle_data['volume'])
            }
            self.candles.append(candle)
            
            # Keep only last 100 candles
            if len(self.candles) > 100:
                self.candles.pop(0)
            
            # Convert to DataFrame for indicator calculation
            df = pd.DataFrame(self.candles)
            self.calc_indicators(df)
            
            # Get current index
            current_idx = len(df) - 1
            
            # Calculate percentage change
            if current_idx >= 4:
                pc = df['pc'].iloc[current_idx]
                prev_pc = df['pc'].iloc[current_idx-1]
                
                # Log indicator values
                self.logger.info(
                    f"Indicators:\n"
                    f"PC: {pc:.2f}%\n"
                    f"Prev PC: {prev_pc:.2f}%\n"
                    f"Volume Percentile: {df['volume_percentile'].iloc[current_idx]:.2f}\n"
                    f"SMA20: {df['sma20'].iloc[current_idx]:.2f}\n"
                    f"SMA50: {df['sma50'].iloc[current_idx]:.2f}\n"
                    f"ROC: {df['roc'].iloc[current_idx]:.2f}"
                )
                
                # Check for bearish order block
                if (prev_pc > -self.sensitivity and pc <= -self.sensitivity and 
                    self.current_position != 'short'):
                    
                    if self.is_valid_trade_condition(df, current_idx, 'short'):
                        self.execute_trade('short', candle['close'])
                        self.last_trade_index = current_idx
                
                # Check for bullish order block
                elif (prev_pc < self.sensitivity and pc >= self.sensitivity and 
                      self.current_position != 'long'):
                    
                    if self.is_valid_trade_condition(df, current_idx, 'long'):
                        self.execute_trade('long', candle['close'])
                        self.last_trade_index = current_idx
                        
        except Exception as e:
            error_msg = f"Error processing candle: {str(e)}"
            self.logger.error(error_msg)
            self.send_telegram_message(f"⚠️ {error_msg}")

    def process_ticker(self, ticker_data):
        """Process ticker data for real-time price updates"""
        try:
            self.last_heartbeat = time.time()  # Update heartbeat
            self.logger.info(f"Processing ticker: {ticker_data}")
            
            if self.current_position and self.stop_loss_price:
                current_price = float(ticker_data['mark_price'])
                
                # Check stop loss
                if self.current_position == 'long':
                    if current_price <= self.stop_loss_price:
                        self.logger.info(f"Stop loss triggered at {current_price}")
                        self.send_telegram_message(
                            f"🛑 Stop Loss Triggered\n"
                            f"Position: LONG\n"
                            f"Price: ${current_price}\n"
                            f"Stop Level: ${self.stop_loss_price}"
                        )
                        self.execute_trade('close', current_price)
                    elif current_price > self.entry_price:
                        # Update trailing stop
                        new_stop = current_price * (1 - self.trailing_stop_pct)
                        if new_stop > self.trailing_stop_price:
                            self.trailing_stop_price = new_stop
                            self.stop_loss_price = new_stop
                            self.logger.info(f"Updated trailing stop to {new_stop}")
                            self.send_telegram_message(
                                f"📈 Trailing Stop Updated\n"
                                f"New Stop: ${new_stop}\n"
                                f"Current Price: ${current_price}"
                            )
                
                elif self.current_position == 'short':
                    if current_price >= self.stop_loss_price:
                        self.logger.info(f"Stop loss triggered at {current_price}")
                        self.send_telegram_message(
                            f"🛑 Stop Loss Triggered\n"
                            f"Position: SHORT\n"
                            f"Price: ${current_price}\n"
                            f"Stop Level: ${self.stop_loss_price}"
                        )
                        self.execute_trade('close', current_price)
                    elif current_price < self.entry_price:
                        # Update trailing stop
                        new_stop = current_price * (1 + self.trailing_stop_pct)
                        if new_stop < self.trailing_stop_price:
                            self.trailing_stop_price = new_stop
                            self.stop_loss_price = new_stop
                            self.logger.info(f"Updated trailing stop to {new_stop}")
                            self.send_telegram_message(
                                f"📉 Trailing Stop Updated\n"
                                f"New Stop: ${new_stop}\n"
                                f"Current Price: ${current_price}"
                            )
                        
        except Exception as e:
            error_msg = f"Error processing ticker: {str(e)}"
            self.logger.error(error_msg)
            self.send_telegram_message(f"⚠️ {error_msg}")

    def on_error(self, ws, error):
        error_msg = f"WebSocket Error: {error}"
        self.logger.error(error_msg)
        self.send_telegram_message(f"⚠️ {error_msg}")
        self.is_ws_connected = False

    def on_close(self, ws, close_status_code, close_msg):
        msg = f"WebSocket closed with status: {close_status_code} and message: {close_msg}"
        self.logger.info(msg)
        self.send_telegram_message(f"🔴 {msg}")
        self.is_ws_connected = False

    def on_open(self, ws):
        self.logger.info("WebSocket connection established")
        self.send_telegram_message("🟢 Connected to Delta Exchange")
        self.is_ws_connected = True
        self.last_heartbeat = time.time()
        
        # Subscribe to the candlestick channel for our symbol
        self.subscribe(ws, f"candlestick_{self.timeframe}", [self.symbol])
        # Subscribe to ticker for real-time price updates
        self.subscribe(ws, "v2/ticker", [self.symbol])
        
        # Send initial ping
        ws.send(json.dumps({"type": "ping"}))

    def subscribe(self, ws, channel, symbols):
        payload = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": channel,
                        "symbols": symbols
                    }
                ]
            }
        }
        ws.send(json.dumps(payload))
        self.logger.info(f"Subscribed to {channel} for symbols {symbols}")
        self.send_telegram_message(f"📊 Subscribed to {channel} for {symbols}")

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            self.logger.debug(f"Received message: {data}")
            
            # Update heartbeat on any message
            self.last_heartbeat = time.time()
            
            # Process different types of messages
            if "type" in data:
                if data["type"] == "candlestick":
                    self.process_candle(data["payload"])
                elif data["type"] == "ticker":
                    self.process_ticker(data["payload"])
                elif data["type"] == "ping":
                    self.on_ping(ws, message)
                elif data["type"] == "pong":
                    self.on_pong(ws, message)
                    
            # Check connection health
            self.check_connection_health()
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            self.logger.error(error_msg)
            self.send_telegram_message(f"⚠️ {error_msg}")

    def run(self):
        self.logger.info("Starting LiveTrader...")
        
        while True:
            try:
                # Create new WebSocket connection with updated settings
                self.ws = websocket.WebSocketApp(
                    DELTA_CONFIG['ws_url'],
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_open=self.on_open
                )
                
                # Run WebSocket with ping interval and timeout
                self.ws.run_forever(
                    ping_interval=20,  # Send ping every 20 seconds
                    ping_timeout=10,   # Wait 10 seconds for pong response
                    reconnect=5        # Reconnect after 5 seconds on failure
                )
                
                if not self.is_ws_connected:
                    self.logger.info("Connection lost, waiting 5 seconds before reconnecting...")
                    time.sleep(5)
                    
            except Exception as e:
                error_msg = f"WebSocket connection failed: {str(e)}"
                self.logger.error(error_msg)
                self.logger.info("Attempting to reconnect in 5 seconds...")
                self.send_telegram_message(f"⚠️ {error_msg}\nRetrying in 5 seconds...")
                time.sleep(5)

if __name__ == "__main__":
    trader = LiveTrader()
    trader.run() 
