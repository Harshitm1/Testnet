# ETH-USD Order Block Trading Bot

A live trading bot that identifies and trades order blocks on ETH-USD using Delta Exchange India. The bot includes real-time trade execution, Telegram alerts, and position management with trailing stops.

## Features

- Real-time order block detection
- Live trading execution on Delta Exchange
- Telegram alerts for trades and system status
- Automatic position management with trailing stops
- Risk management with configurable position sizes and stop losses
- WebSocket connection for real-time market data
- Comprehensive logging system

## Prerequisites

- Python 3.7+
- Delta Exchange API credentials
- Telegram Bot Token and Chat ID

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-directory>
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Configure your credentials:
   - Copy `config.py` to `config_local.py`
   - Update the following in `config_local.py`:
     - Delta Exchange API key and secret
     - Telegram bot token and chat ID
     - Adjust trading parameters if needed

## Configuration

The bot's behavior can be customized through the `config.py` file:

### Trading Configuration
- `symbol`: Trading pair (default: 'ETHUSD')
- `timeframe`: Candlestick timeframe (default: '1m')
- `initial_capital`: Initial capital for position sizing
- `max_position_size`: Maximum position size as percentage of capital
- `stop_loss_pct`: Initial stop loss percentage
- `trailing_stop_pct`: Trailing stop percentage

### Strategy Parameters
- `sensitivity`: Price movement threshold for order block detection
- `min_volume_percentile`: Minimum volume requirement
- `trend_period`: Period for trend calculation
- `min_trades_distance`: Minimum candles between trades

## Usage

1. Start the bot:
```bash
python live_trader.py
```

2. Monitor via Telegram:
   - The bot will send real-time updates to your Telegram channel
   - Alerts include:
     - System startup/shutdown
     - Trade entries and exits
     - Stop loss updates
     - Error notifications

## Telegram Alerts

The bot sends the following types of alerts:

- 🚀 System startup
- 📊 WebSocket connection status
- 💰 Account balance updates
- 🟢 Long entry signals
- 🔴 Short entry signals
- ✅ Trade execution details
- 🔄 Position updates and stop loss modifications
- ⚠️ Error notifications

## Risk Management

The bot implements several risk management features:

1. Position Sizing
   - Positions are sized based on account balance
   - Maximum position size is configurable

2. Stop Loss Management
   - Initial stop loss on entry
   - Trailing stop loss that moves with profitable trades
   - Automatic stop loss order updates

3. Trade Spacing
   - Minimum time between trades
   - Minimum number of candles between trades

## Error Handling

The bot includes comprehensive error handling:

- Automatic WebSocket reconnection
- API error handling and retries
- Position monitoring failsafes
- Detailed error logging

## Logging

All activities are logged to `trading.log`, including:

- Trade executions
- System events
- Errors and warnings
- Position updates

## Security Notes

1. Never commit your API credentials to version control
2. Use `config_local.py` for sensitive information
3. Keep your Telegram bot token secure
4. Regularly monitor the bot's activities

## Disclaimer

This trading bot is provided for educational purposes only. Use at your own risk. Always start with small position sizes and monitor the bot's performance carefully.

## License

[Your License] 