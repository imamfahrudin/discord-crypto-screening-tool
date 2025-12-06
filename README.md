# Discord Crypto Screening Tool 🤖📈

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An intelligent Discord bot that provides real-time cryptocurrency trading signals using technical analysis indicators like RSI (Relative Strength Index) and EMA (Exponential Moving Average). Perfect for crypto traders looking for automated screening and signal generation.

## 🌟 Features

- **Real-time Signal Generation**: Analyzes crypto pairs using RSI and EMA indicators
- **Discord Integration**: Posts trading signals directly to Discord channels
- **WebSocket Price Feeds**: Real-time price data from Bybit exchange
- **Modern Slash Commands**: Interactive commands with dropdown menus for easy use
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
   # Copy the example env file and edit with your Discord bot token
   cp .env.example .env
   nano .env
   ```

3. **Build and run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **View logs**
   ```bash
   docker-compose logs -f
   ```

#### Multiple Bot Instances

The project supports running multiple independent bot instances. Each instance uses its own environment file and runs in a separate container.

To run multiple instances:

1. Create additional environment files:
   ```bash
   cp .env .env2  # Copy settings for second instance
   # Edit .env2 with a different bot token
   ```

2. Uncomment the second service in `docker-compose.yml`:
   ```yaml
   # discord-crypto-bot-2:
   #   build: .
   #   container_name: discord-crypto-screening-tool-2
   #   env_file: .env2
   #   volumes:
   #     - ./pairs_cache.json:/app/pairs_cache.json
   #   restart: unless-stopped
   #   dns:
   #     - 127.0.0.1
   ```

3. Start multiple instances:
   ```bash
   # Start all instances
   docker-compose up -d

   # Start specific instances
   docker-compose up -d discord-crypto-bot discord-crypto-bot-2

   # View logs for specific instance
   docker-compose logs -f discord-crypto-bot-2
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

4. **Update .env with your Discord bot token**

5. **Run the bot**
   ```bash
   python discord_bot.py
   ```

## ⚙️ Configuration

### Environment Files

Create environment files for each bot instance. The project supports multiple independent bots:

```bash
# Copy the example file for your first bot
cp .env.example .env

# For additional bots, create more env files
cp .env .env2  # Copy settings for second instance
```

Then edit each `.env` file with your settings:

```
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN_HERE
BYBIT_WS_URL=wss://stream.bybit.com/v5/public/linear
OHLC_LIMIT=500
```

**Configuration Options:**
- **DISCORD_TOKEN** (required): Your Discord bot token - Must be unique for each bot instance
- **BYBIT_WS_URL** (optional): WebSocket URL for Bybit price feeds. Default: `wss://stream.bybit.com/v5/public/linear`
- **OHLC_LIMIT** (optional): Number of OHLC candles to fetch for analysis. Default: 500

### Multiple Bot Instances

You can run multiple bot instances simultaneously, each with different tokens serving different servers:

- Each bot instance has its own Discord token and can be invited to different servers
- Bots share the same codebase but run in separate containers
- Use different container names for easy identification
- All instances use the same pairs cache file

## 🔧 How It Works

1. **Initialization**: Bot loads configuration and establishes Discord connection
2. **Command Handling**: Listens for `!signal` commands and `/signal` slash commands in Discord channels
3. **Data Fetching**: Retrieves real-time price data via WebSocket from Bybit
4. **Signal Calculation**: Applies RSI and EMA analysis to generate trading signals
5. **Response**: Posts formatted signals back to the Discord channel
6. **Caching**: Maintains pair cache for efficient lookups

## 📊 Usage

### Supported Timeframes
The bot supports the following timeframes: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 1d, 1w, 1M.

### Commands
The bot supports both traditional prefix commands and modern slash commands:

#### Prefix Commands
- `!signal {coin} {timeframe}` - General signal check (shows both long and short signals)
- `!signal {coin} {timeframe} {long/short}` - Specific direction signal check

#### Slash Commands (Recommended)
The bot now supports Discord's modern slash commands with dropdown helpers:
```
/signal          → Generate trading signal (with dropdowns for timeframe & direction)
/help           → Show available commands and usage information (in Indonesian)
```

**Benefits of slash commands:**
- **Dropdown menus** for timeframe and direction selection
- **Better mobile experience** with touch-friendly interfaces
- **Parameter validation** prevents common mistakes
- **Autocomplete** for trading pair symbols

**Examples:**
- `!signal BTC 1h` - Check for both long and short signals on BTC/USDT 1-hour chart
- `!signal BTC 1h long` - Check specifically for long signals on BTC/USDT 1-hour chart
- `!signal ETH 4h short` - Check for short signals on ETH/USDT 4-hour chart
- `!signal HYPE 1d` - Check for signals on HYPE/USDT daily chart
- `/signal` - Use the interactive slash command with dropdowns
- `/help` - Show help information in Indonesian

**Supported Parameters:**
- **COIN**: Cryptocurrency symbol (e.g., BTC, ETH, HYPE). USDT is automatically added.
- **TIMEFRAME**: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 1d, 1w, 1M
- **DIRECTION**: Auto (default), Long, or Short

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
# Docker - all instances
docker-compose logs -f

# Docker - specific instance
docker-compose logs -f discord-crypto-bot-2

# Local Python
# Logs appear in the console where you ran python discord_bot.py
```

## 🐛 Troubleshooting

### Bot doesn't start
- **Issue**: Invalid Discord token
- **Solution**: Verify token in `.env` file and ensure bot has proper permissions

### No signals generated
- **Issue**: API connection failure or invalid pair
- **Solution**: Check internet connection and verify trading pair exists on Bybit

### WebSocket errors
- **Issue**: Connection issues with Bybit
- **Solution**: Ensure stable internet and check Bybit API status

### Multiple Bot Issues
- **Issue**: Bots not responding or conflicting
- **Solution**: Ensure each bot instance has a unique Discord token and different container names. Check logs for each service individually: `docker-compose logs -f discord-crypto-bot-2`

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
