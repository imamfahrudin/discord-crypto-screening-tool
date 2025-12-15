# Discord Crypto Screening Tool 🤖📈

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An intelligent Discord bot that provides real-time cryptocurrency trading signals using technical analysis indicators like RSI (Relative Strength Index) and EMA (Exponential Moving Average). Features interactive slash commands, chart generation with position setup visualization, and support for multiple bot instances.

## 🌟 Features

- **Real-time Signal Generation**: Analyzes crypto pairs using RSI and EMA indicators
- **Discord Integration**: Posts trading signals directly to Discord channels
- **Multi-Exchange Support**: Support for Bybit, Binance, and Bitget Futures
- **WebSocket Price Feeds**: Real-time price data from Bybit exchange
- **Modern Slash Commands**: Interactive commands with dropdown menus for easy use
- **Chart Generation**: Visual position setup with entry/SL/TP levels, FVG zones, EMAs, and volume bars
- **Quick Commands**: Support for $ prefix for faster signal checks
- **Multi-Coin Scanning**: Analyze multiple coins simultaneously with best setup selection
- **Flexible Parameter Ordering**: Commands support any order for timeframe, direction, and custom EMAs
- **Custom EMA Support**: Configure short and long EMA periods for personalized analysis
- **Detailed Analysis**: Optional detailed technical analysis with comprehensive reasoning
- **Coin List Management**: Paginated list of all available trading pairs
- **Enhanced Signal Confidence**: Detailed reasoning with emoji indicators and specific values
- **Reply Behavior**: Commands reply to user messages for better conversation flow
- **Indonesian Help**: Localized help commands in Indonesian
- **Customizable Signals**: Configurable RSI and EMA parameters
- **Multiple Bot Instances**: Run multiple independent bots simultaneously
- **Docker Support**: Ready-to-deploy with Docker and Docker Compose
- **Dynamic Caching**: Automatically refreshes trading pairs cache every hour to include new listings and delistings
- **Network Resilience**: Automatic retry and connection pooling for reliable API access
- **Comprehensive Testing**: Included bot testing guide for all commands and scenarios
- **Error Handling**: Robust error handling and logging for reliable operation
- **Rate Limiting**: Built-in delays to respect API limits

## 📋 Prerequisites

- Python 3.9 or higher (tested with Python 3.9+ for datetime compatibility)
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
BOT_TITLE_PREFIX=💎 CRYPTO SIGNAL —
BOT_FOOTER_NAME=Crypto Bot
```

**Configuration Options:**
- **DISCORD_TOKEN** (required): Your Discord bot token - Must be unique for each bot instance
- **BYBIT_WS_URL** (optional): WebSocket URL for Bybit price feeds. Default: `wss://stream.bybit.com/v5/public/linear`
- **OHLC_LIMIT** (optional): Number of OHLC candles to fetch for analysis. Default: 500
- **BOT_TITLE_PREFIX** (optional): Prefix for embed titles. Default: `💎 CRYPTO SIGNAL —`
- **BOT_FOOTER_NAME** (optional): Name shown in embed footers. Default: `Crypto Bot`

### Multiple Bot Instances

You can run multiple bot instances simultaneously, each with different tokens serving different servers:

- Each bot instance has its own Discord token and can be invited to different servers
- Bots share the same codebase but run in separate containers
- Use different container names for easy identification
- All instances use the same pairs cache file

## 🔧 How It Works

1. **Initialization**: Bot loads configuration and establishes Discord connection
2. **Command Handling**: Listens for `!signal`, `$signal`, `!scan`, `!coinlist`, and `/signal`, `/scan`, `/coinlist` slash commands in Discord channels
3. **Data Fetching**: Retrieves real-time price data via WebSocket from Bybit
4. **Signal Calculation**: Applies RSI and EMA analysis to generate trading signals
5. **Chart Generation**: Creates visual charts with position setup, EMAs, FVG zones, and volume bars
6. **Response**: Posts formatted signals with embedded charts back to the Discord channel
7. **Caching**: Maintains pair cache for efficient lookups with automatic refresh

## 📊 Usage

### Supported Timeframes
The bot supports the following timeframes: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 1d, 1w, 1M.

### Commands
The bot supports both traditional prefix commands and modern slash commands:

#### Prefix Commands
- `!signal {coin} [timeframe] [long/short] [ema_short] [ema_long] [binance|bitget] [detail]` - General signal check with flexible parameters
- `!scan {coin1 coin2 ...} [ema_short] [ema_long] [binance|bitget]` - Scan multiple coins (max 5) and select best setup per coin
- `!coinlist [binance|bitget]` - Display paginated list of available trading coins

#### Quick Commands ($ Prefix)
- `$SYMBOL [TIMEFRAME] [long/short] [ema_short] [ema_long] [binance|bitget] [detail]` - Quick signal check with flexible parameters

#### Slash Commands (Recommended)
The bot now supports Discord's modern slash commands with dropdown helpers:
```
/signal          → Generate trading signal (with dropdowns for timeframe, direction, & custom EMAs)
/scan           → Scan multiple coins for best trading setups
/coinlist       → List all available trading coins with pagination
/help           → Show available commands and usage information (in Indonesian)
```

**Benefits of slash commands:**
- **Dropdown menus** for timeframe and direction selection
- **Better mobile experience** with touch-friendly interfaces
- **Parameter validation** prevents common mistakes
- **Autocomplete** for trading pair symbols

**Examples:**
- `!signal BTC` - Check for signals on BTC/USDT 1h (default timeframe, Bybit)
- `!signal BTC 1h` - Check for both long and short signals on BTC/USDT 1-hour chart
- `!signal BTC 1h long` - Check specifically for long signals on BTC/USDT 1-hour chart
- `!signal BTC binance` - Check signals using Binance Futures data
- `!signal BTC bitget` - Check signals using Bitget Futures data
- `!signal ETH 4h short ema20 ema50` - Check for short signals with custom EMA 20/50
- `!signal SOL long ema9 ema21 4h detail` - Flexible parameter order with detailed analysis
- `!scan BTC ETH SOL` - Scan BTC, ETH, SOL and show best setup for each (Bybit)
- `!scan BTC,ETH ema20 ema50 binance` - Scan with custom EMA periods using Binance
- `!scan BTC ETH bitget` - Scan BTC and ETH using Bitget Futures
- `!coinlist` - Show paginated list of all available coins (Bybit)
- `!coinlist binance` - Show coins from Binance Futures
- `!coinlist bitget` - Show coins from Bitget Futures
- `$BTC` - Quick check for BTC signals (1h default, Bybit)
- `$ETH 4h long ema20 ema50 bitget detail` - Quick command with all parameters using Bitget
- `/signal` - Use the interactive slash command with dropdowns
- `/scan` - Interactive multi-coin scanning
- `/coinlist` - Paginated coin list
- `/help` - Show help information in Indonesian

**Supported Parameters:**
- **COIN**: Cryptocurrency symbol (e.g., BTC, ETH, HYPE). USDT is automatically added.
- **TIMEFRAME**: Optional, default 1h. Supported: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 1d, 1w, 1M
- **EXCHANGE**: Optional, default Bybit. Supported: bybit, binance, bitget
- **DIRECTION**: Auto (default), Long, or Short
- **EMA_SHORT**: Short EMA period (default: 13, range: 5-200)
- **EMA_LONG**: Long EMA period (default: 21, range: 5-200)
- **DETAIL**: Optional 'detail' flag for comprehensive technical analysis

## 📊 Chart Features

The bot generates professional trading charts with comprehensive position setup visualization:

### Chart Elements
- **Candlestick Charts**: 100-period candlestick display with modern styling
- **Technical Indicators**: Custom EMA periods (user-configurable short/long) with dynamic labels
- **Position Levels**: Entry, Stop Loss, Take Profit 1 & 2 levels with labels
- **Risk/Reward Zones**: Visual shaded areas showing risk (red) and reward (green) zones
- **FVG Zones**: Fair Value Gaps highlighted with semi-transparent overlays
- **Order Blocks**: OB High/Low levels marked with dotted lines
- **Volume Bars**: Color-coded volume histogram (green/red) below price chart
- **Current Price**: Yellow horizontal line with price label
- **Direction Indicator**: Large arrow (▲ for LONG, ▼ for SHORT) at top-left
- **TradingView Links**: Direct links to TradingView charts for each signal

### Chart Styling
- **Modern Theme**: Light background with black borders and enhanced readability
- **High Resolution**: 200 DPI output for crisp chart images
- **Responsive Layout**: Optimized for Discord embed display
- **Professional Appearance**: TradingView-style design with clear legends

### Customizing Signal Parameters

The bot supports custom EMA periods directly through commands. You can also modify default parameters in the code:

```python
# Example: Change default EMA periods in signal_logic.py
def generate_trade_plan(symbol: str, timeframe: str, exchange: str='bybit', 
                       forced_direction: str = None, return_dict: bool = False, 
                       ema_short: int = 13, ema_long: int = 21):
    # ema_short and ema_long can be customized per command
```

**Command Examples with Custom EMAs:**
- `!signal BTC 1h long ema20 ema50` - Use EMA 20/50 instead of default 13/21
- `/signal symbol:BTC timeframe:1h direction:long ema_short:20 ema_long:50` - Slash command with custom EMAs
- `$BTC 4h ema9 ema21` - Quick command with custom EMAs

**EMA Period Ranges:**
- Short EMA: 5-200 periods
- Long EMA: 5-200 periods
- Short EMA must be less than Long EMA

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

## 🧪 Testing

The project includes a comprehensive bot testing guide (`bot_test_guide.md`) with:

- **Command Testing Checklist**: Step-by-step testing for all command types
- **Parameter Validation**: Testing edge cases and error handling
- **Performance Expectations**: Response time guidelines
- **Environment Setup**: Testing environment configuration
- **Troubleshooting**: Common issues and debug information

Run the testing guide to ensure all features work correctly:
```bash
# The testing guide is available at bot_test_guide.md
# Follow the checklist to validate bot functionality
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
- [Binance](https://www.binance.com/) for Binance Futures data
- [Bitget](https://www.bitget.com/) for Bitget Futures data
- [TA Library](https://github.com/bukosabino/ta) for technical analysis
- [pandas](https://pandas.pydata.org/) for data manipulation

## 📧 Contact

**Repository**: [https://github.com/imamfahrudin/discord-crypto-screening-tool](https://github.com/imamfahrudin/discord-crypto-screening-tool)

**Issues**: [Report a bug or request a feature](https://github.com/imamfahrudin/discord-crypto-screening-tool/issues)

---

Made with ❤️ for the crypto trading community
