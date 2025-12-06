# Discord Crypto Screening Tool 🤖📈

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An intelligent Discord bot that provides real-time cryptocurrency trading signals using technical analysis indicators like RSI (Relative Strength Index) and EMA (Exponential Moving Average). Perfect for crypto traders looking for automated screening and signal generation.

## 🌟 Features

- **Real-time Signal Generation**: Analyzes crypto pairs using RSI and EMA indicators
- **Discord Integration**: Posts trading signals directly to Discord channels
- **WebSocket Price Feeds**: Real-time price data from Bybit exchange
- **Customizable Signals**: Configurable RSI and EMA parameters
- **Docker Support**: Ready-to-deploy with Docker and Docker Compose
- **Persistent Caching**: Caches trading pairs for faster lookups
- **Error Handling**: Robust error handling and logging for reliable operation
- **Rate Limiting**: Built-in delays to respect API limits

## 📋 Prerequisites

- Python 3.9 or higher
- Docker and Docker Compose (optional, for containerized deployment)
- Discord bot token
- Internet connection for API access

## 🚀 Quick Start

### Option 1: Docker Deployment (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/imamfahrudin/discord-crypto-screening-tool.git
   cd discord-crypto-screening-tool
   ```

2. **Update configuration**
   ```bash
   # Edit config.json with your Discord bot token
   nano config.json
   ```

3. **Build and run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **View logs**
   ```bash
   docker-compose logs -f
   ```

### Option 2: Local Python Deployment

1. **Clone the repository**
   ```bash
   git clone https://github.com/imamfahrudin/discord-crypto-screening-tool.git
   cd discord-crypto-screening-tool
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Update config.json with your Discord bot token**

5. **Run the bot**
   ```bash
   python discord_bot.py
   ```

## ⚙️ Configuration

### config.json

Update the `config.json` file with your Discord bot token and optional settings:

```json
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN_HERE",
  "bybit_ws_url": "wss://stream.bybit.com/v5/public/linear",
  "ohlc_limit": 500
}
```

**Configuration Options:**
- **discord_token** (required): Your Discord bot token
- **bybit_ws_url** (optional): WebSocket URL for Bybit price feeds. Default: `wss://stream.bybit.com/v5/public/linear`
- **ohlc_limit** (optional): Number of OHLC candles to fetch for analysis. Default: 500

## 🔧 How It Works

1. **Initialization**: Bot loads configuration and establishes Discord connection
2. **Command Handling**: Listens for `!signal` commands in Discord channels
3. **Data Fetching**: Retrieves real-time price data via WebSocket from Bybit
4. **Signal Calculation**: Applies RSI and EMA analysis to generate trading signals
5. **Response**: Posts formatted signals back to the Discord channel
6. **Caching**: Maintains pair cache for efficient lookups

## 📊 Usage

### Supported Timeframes
The bot supports the following timeframes: 1m, 5m, 15m, 30m, 1h, 4h, and 1d.

### Commands
The bot has two command formats:

- `!signal {coin} {timeframe}` - General signal check (shows both long and short signals)
- `!signal {coin} {timeframe} {long/short}` - Specific direction signal check

**Examples:**
- `!signal BTC 1h` - Check for both long and short signals on BTC/USDT 1-hour chart
- `!signal BTC 1h long` - Check specifically for long signals on BTC/USDT 1-hour chart
- `!signal ETH 4h short` - Check for short signals on ETH/USDT 4-hour chart
- `!signal HYPE 1d` - Check for signals on HYPE/USDT daily chart

**Supported Parameters:**
- **COIN**: Cryptocurrency symbol (e.g., BTC, ETH, HYPE). USDT is automatically added.
- **TIMEFRAME**: 1m, 5m, 15m, 30m, 1h, 4h, 1d
- **DIRECTION**: long or short (optional)

## 🛠️ Advanced Usage

### Customizing Signal Parameters

Edit `signal_logic.py` to adjust RSI and EMA parameters:

```python
# Example: Change RSI overbought/oversold levels
rsi_overbought = 70
rsi_oversold = 30

# Example: Change EMA periods
ema_short_period = 9
ema_long_period = 21
```

### Adding New Indicators

Extend `signal_logic.py` to include additional technical indicators using the `ta` library.

## 📝 Logging

The bot provides console logging for monitoring:

- **[INFO]**: General information and status updates
- **[ERROR]**: Critical errors that require attention
- **[SIGNAL]**: Trading signal generation details

View logs in real-time:
```bash
# Docker
docker-compose logs -f

# Local Python
# Logs appear in the console where you ran python discord_bot.py
```

## 🐛 Troubleshooting

### Bot doesn't start
- **Issue**: Invalid Discord token
- **Solution**: Verify token in `config.json` and ensure bot has proper permissions

### No signals generated
- **Issue**: API connection failure or invalid pair
- **Solution**: Check internet connection and verify trading pair exists on Bybit

### WebSocket errors
- **Issue**: Connection issues with Bybit
- **Solution**: Ensure stable internet and check Bybit API status

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Discord.py](https://github.com/Rapptz/discord.py) for Discord API integration
- [Bybit](https://www.bybit.com/) for exchange data
- [TA Library](https://github.com/bukosabino/ta) for technical analysis
- [pandas](https://pandas.pydata.org/) for data manipulation

## 📧 Contact

**Repository**: [https://github.com/imamfahrudin/discord-crypto-screening-tool](https://github.com/imamfahrudin/discord-crypto-screening-tool)

**Issues**: [Report a bug or request a feature](https://github.com/imamfahrudin/discord-crypto-screening-tool/issues)

---

Made with ❤️ for the crypto trading community
