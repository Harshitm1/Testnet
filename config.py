# Trading configuration
TRADING_CONFIG = {
    'symbol': 'ETHUSD',
    'product_id': 1699,
    'timeframe': '15m',  # Using 15m as per original test
    'initial_capital': 100,
    'max_position_size': 1.0,  # Full position size
    'stop_loss_pct': 0.02,    # 2% stop loss as per original
    'trailing_stop_pct': 0.015, # 1.5% trailing stop as per original
    'order_type': 'market',  # Order type (market/limit)
}

# Telegram configuration
TELEGRAM_CONFIG = {
    'bot_token': '7203764992:AAEW7YINK48mYlNRodV_jqpP33LlD2uqOLg',
    'chat_id': '1099769493'   # Replace with your Telegram chat ID
}

# Delta Exchange API configuration
DELTA_CONFIG = {
    'api_key': 'qRYt3pqBMLiHmepIiQPjNriyZUjzXg',  # Testnet API Key
    'api_secret': 'RSqASLyRunSFl5JAAQLOAApGDvodSEv8PJWK9qrOa6fFUoJgLqK6DYjSboUk',  # Testnet API Secret
    'base_url': 'https://cdn-ind.testnet.deltaex.org',  # Updated India Testnet REST API URL
    'ws_url': 'wss://socket-ind.testnet.deltaex.org',  # India Testnet WebSocket URL
}

# Strategy parameters - Exactly as per original OrderBlocks class
STRATEGY_CONFIG = {
    'sensitivity': 0.015,           # 1.5% price movement threshold
    'min_volume_percentile': 50,    # Minimum volume percentile for valid trades
    'trend_period': 20,            # Period for trend calculation
    'min_trades_distance': 10,     # Minimum number of candles between trades
}

# Logging configuration
LOGGING_CONFIG = {
    'log_level': 'INFO',
    'log_file': 'trading.log',
    'max_log_size': 1024 * 1024 * 10,  # 10 MB
    'backup_count': 5
} 