# Discord Crypto Screening Tool 🤖📈

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An intelligent Discord bot that provides real-time cryptocurrency trading signals using technical analysis indicators like RSI (Relative Strength Index) and EMA (Exponential Moving Average). Features interactive slash commands, chart generation with position setup visualization, and support for multiple bot instances.

## 🌟 Features

- **Real-time Signal Generation**: Analyzes crypto pairs using RSI and EMA indicators
- **Discord Integration**: Posts trading signals directly to Discord channels
- **Multi-Exchange Support**: Support for Bybit, Binance, Bitget, and Gate.io Futures
- **WebSocket Price Feeds**: Real-time price data from Bybit exchange
- **Modern Slash Commands**: Interactive commands with dropdown helpers for easy use (Help command available)
- **Chart Generation**: Visual position setup with entry/SL/TP levels, FVG zones, EMAs, and volume bars
- **Quick Commands**: Support for $ prefix for faster signal checks
- **Multi-Coin Scanning**: Analyze multiple coins simultaneously with best setup selection
- **Scalp Command**: Specialized scanning for short timeframes (15m/30m) for scalping opportunities
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
- **Coin Image Thumbnails**: Automatic coin logo fetching and caching for enhanced embeds
- **EMA Switch Buttons**: Interactive buttons to switch between EMA periods (13/21 ↔ 25/50)
- **Ping Benchmark**: Test bot latency and exchange response times

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

#### Docker Features
- **Cloudflare WARP Integration**: Optional DNS over HTTPS for enhanced privacy and reliability
- **Health Checks**: Automatic container health monitoring with DNS connectivity tests
- **Persistent Caching**: Automatic cache persistence for trading pairs and coin images
- **Network Configuration**: Custom bridge network with IPv6 support
- **Privileged Mode**: Required for WARP VPN functionality

#### Environment Variables for Docker
Add these optional variables to your `.env` file:
```
USE_WARP=true  # Enable Cloudflare WARP for DNS over HTTPS (default: false)
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
   #     - ./cache:/app/cache
   #   restart: unless-stopped
   #   privileged: true
   #   cap_add:
   #     - NET_ADMIN
   #     - SYS_MODULE
   #   devices:
   #     - /dev/net/tun:/dev/net/tun
   #   sysctls:
   #     - net.ipv6.conf.all.disable_ipv6=0
   #     - net.ipv4.conf.all.src_valid_mark=1
   #   networks:
   #     - custom_bridge
   #   healthcheck:
   #     test: ["CMD", "nslookup", "google.com", "1.1.1.1"]
   #     interval: 30s
   #     timeout: 10s
   #     retries: 3
   #     start_period: 30s
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
OHLC_LIMIT=500
BOT_TITLE_PREFIX=💎 CRYPTO SIGNAL —
BOT_FOOTER_NAME=Crypto Bot
USE_WARP=false
```

**Configuration Options:**
- **DISCORD_TOKEN** (required): Your Discord bot token - Must be unique for each bot instance
- **OHLC_LIMIT** (optional): Number of OHLC candles to fetch for analysis. Default: 500
- **BOT_TITLE_PREFIX** (optional): Prefix for embed titles. Default: `💎 CRYPTO SIGNAL —`
- **BOT_FOOTER_NAME** (optional): Name shown in embed footers. Default: `Crypto Bot`
- **USE_WARP** (optional): Enable Cloudflare WARP for DNS over HTTPS in Docker. Default: `false`

### Multiple Bot Instances

You can run multiple bot instances simultaneously, each with different tokens serving different servers:

- Each bot instance has its own Discord token and can be invited to different servers
- Bots share the same codebase but run in separate containers
- Use different container names for easy identification
- All instances share the same cache directory for trading pairs and coin images

## 🔧 How It Works

1. **Initialization**: Bot loads configuration and establishes Discord connection
2. **Command Handling**: Listens for `!signal`, `$signal`, `!scan`, `!scalp`, `!coinlist`, `!ping`, and `/help` commands in Discord channels
3. **Data Fetching**: Retrieves real-time price data from supported exchanges (Bybit, Binance, Bitget, Gate.io)
4. **Signal Calculation**: Applies RSI and EMA analysis to generate trading signals
5. **Chart Generation**: Creates visual charts with position setup, EMAs, FVG zones, and volume bars
6. **Response**: Posts formatted signals with embedded charts back to the Discord channel
7. **Caching**: Maintains pair cache for efficient lookups with automatic refresh

## 📊 Usage

### Supported Timeframes
The bot supports the following timeframes: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 1d, 1w, 1M.

### Commands
The bot supports traditional prefix commands and quick commands. A help slash command is available for guidance:

#### Prefix Commands
- `!signal {coin} [timeframe] [long/short] [ema_short] [ema_long] [binance|bitget|gateio] [detail]` - General signal check with flexible parameters
- `!scan {coin1 coin2 ...} [ema_short] [ema_long] [binance|bitget|gateio]` - Scan multiple coins (max 5) and select best setup per coin
- `!scalp {coin1 coin2 ...} [ema_short] [ema_long] [binance|bitget|gateio]` - Scalp multiple coins (max 5) on short timeframes (15m/30m)
- `!coinlist [binance|bitget|gateio]` - Display paginated list of available trading coins
- `!ping` - Check bot latency and benchmark exchange response times

#### Quick Commands ($ Prefix)
- `$SYMBOL [TIMEFRAME] [long/short] [ema_short] [ema_long] [binance|bitget|gateio] [detail]` - Quick signal check with flexible parameters

#### Slash Commands
- `/help` - Show available commands and usage information (in Indonesian)

**Examples:**
- `!signal BTC` - Check for signals on BTC/USDT 1h (default timeframe, Bybit)
- `!signal BTC 1h` - Check for both long and short signals on BTC/USDT 1-hour chart
- `!signal BTC 1h long` - Check specifically for long signals on BTC/USDT 1-hour chart
- `!signal BTC binance` - Check signals using Binance Futures data
- `!signal BTC bitget` - Check signals using Bitget Futures data
- `!signal BTC gateio` - Check signals using Gate.io Futures data
- `!signal ETH 4h short ema20 ema50` - Check for short signals with custom EMA 20/50
- `!signal SOL long ema9 ema21 4h detail` - Flexible parameter order with detailed analysis
- `!scan BTC ETH SOL` - Scan BTC, ETH, SOL and show best setup for each (Bybit)
- `!scan BTC,ETH ema20 ema50 binance` - Scan with custom EMA periods using Binance
- `!scan BTC ETH bitget` - Scan BTC and ETH using Bitget Futures
- `!scan BTC ETH gateio` - Scan BTC and ETH using Gate.io Futures
- `!scalp BTC ETH SOL` - Scalp BTC, ETH, SOL on short timeframes (15m/30m)
- `!scalp BTC ETH ema20 ema50 gateio` - Scalp with custom EMA using Gate.io
- `!coinlist` - Show paginated list of all available coins (Bybit)
- `!coinlist binance` - Show coins from Binance Futures
- `!coinlist bitget` - Show coins from Bitget Futures
- `!coinlist gateio` - Show coins from Gate.io Futures
- `!ping` - Check bot latency and exchange benchmark times
- `$BTC` - Quick check for BTC signals (1h default, Bybit)
- `$ETH 4h long ema20 ema50 gateio detail` - Quick command with all parameters using Gate.io
- `/help` - Show help information in Indonesian

**Supported Parameters:**
- **COIN**: Cryptocurrency symbol (e.g., BTC, ETH, HYPE). USDT is automatically added.
- **TIMEFRAME**: Optional, default 1h. Supported: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 1d, 1w, 1M
- **EXCHANGE**: Optional, default Bybit. Supported: bybit, binance, bitget, gateio
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

### Interactive Features
- **EMA Switch Buttons**: Interactive buttons in signal embeds to switch between EMA periods (13/21 ↔ 25/50)
- **TradingView Links**: Direct links to view charts on TradingView for detailed analysis
- **Coin Thumbnails**: Automatic cryptocurrency logo display in embeds
- **Paginated Coin Lists**: Navigation buttons for browsing available trading pairs

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
- `$BTC 4h ema9 ema21` - Quick command with custom EMAs
- `!scan BTC ETH ema25 ema50` - Scan with custom EMA periods

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

### Docker Issues
- **Issue**: Container fails to start with WARP errors
- **Solution**: Set `USE_WARP=false` in your `.env` file to disable Cloudflare WARP, or ensure privileged mode is enabled in docker-compose.yml
- **Issue**: Health check failures
- **Solution**: Check network connectivity and DNS resolution. The container uses `nslookup` to test connectivity
- **Issue**: Cache not persisting between restarts
- **Solution**: Ensure the `./cache` volume is properly mounted and has write permissions
- **Issue**: High CPU usage
- **Solution**: The bot performs parallel processing for multiple exchanges. This is normal behavior during signal generation

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
- [Gate.io](https://www.gate.io/) for Gate.io Futures data
- [TA Library](https://github.com/bukosabino/ta) for technical analysis
- [pandas](https://pandas.pydata.org/) for data manipulation
- [Docker](https://www.docker.com/) for containerization
- [Cloudflare WARP](https://1.1.1.1/) for DNS over HTTPS functionality

## 📧 Contact

**Repository**: [https://github.com/imamfahrudin/discord-crypto-screening-tool](https://github.com/imamfahrudin/discord-crypto-screening-tool)

**Issues**: [Report a bug or request a feature](https://github.com/imamfahrudin/discord-crypto-screening-tool/issues)

---

Made with ❤️ for the crypto trading community
