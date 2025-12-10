# Discord Crypto Screening Tool - Bot Testing Guide

## Overview
This guide provides comprehensive testing instructions for the Discord Crypto Signal Bot. The bot supports multiple command formats and features for generating trading signals.

## Bot Commands Overview

### 1. Prefix Commands (!)
These commands use the `!` prefix and are processed by the bot's command handler.

#### !signal Command
Generate trading signals with flexible parameter parsing.

**Basic Usage:**
```
!signal BTC
!signal ETH 4h
!signal SOL 1d short
```

**Advanced Usage:**
```
!signal BTC 1h long ema20 ema50
!signal ETH short ema9 ema21 4h
!signal BTC 1h detail
```

**Parameter Order:** Flexible after symbol
- Symbol (required)
- Timeframe (optional, default: 1h)
- Direction (optional: long/short)
- EMA short/long (optional pairs)
- Detail flag (optional)

#### !scan Command
Scan multiple coins for best trading setups.

**Usage:**
```
!scan BTC ETH SOL
!scan BTC,ETH ema20 ema50
!scan BTC ETH SOL ema20 ema50
```

**Features:**
- Maximum 5 coins per scan
- Flexible coin separation (spaces or commas)
- Custom EMA support
- Returns best confidence setup per coin

#### !coinlist Command
Display paginated list of available trading coins.

**Usage:**
```
!coinlist
```

### 2. Dollar Sign Commands ($)
Quick signal generation with simplified syntax.

**Basic Usage:**
```
$BTC
$ETH 4h
$SOL short
```

**Advanced Usage:**
```
$BTC 1h long ema20 ema50
$ETH short ema9 ema21 4h
$BTC 1h detail
```

**Features:**
- Same parsing logic as !signal
- Faster typing for quick signals
- All parameters supported

### 3. Slash Commands (/)
Discord slash commands with interactive interfaces.

#### /help
Display comprehensive help embed with all commands and examples.

**Usage:**
```
/help
```

**Features:**
- Detailed command reference
- Usage examples
- Parameter explanations
- Tips and guidelines

#### /signal
Interactive signal generation with dropdown menus.

**Parameters:**
- symbol: Trading pair symbol (e.g., BTCUSDT)
- timeframe: 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d
- direction: Auto, Long, Short
- ema_short: Short EMA period (default: 13)
- ema_long: Long EMA period (default: 21)
- detail: Show detailed analysis (default: False)

**Usage:**
```
/signal symbol:BTC timeframe:1h direction:Auto ema_short:13 ema_long:21 detail:false
```

#### /scan
Scan multiple coins with custom EMA settings.

**Parameters:**
- coins: Comma or space separated coins (max 5)
- ema_short: Short EMA period (default: 13)
- ema_long: Long EMA period (default: 21)

**Usage:**
```
/scan coins:BTC,ETH,SOL ema_short:20 ema_long:50
```

#### /coinlist
Interactive coin list with pagination.

**Usage:**
```
/coinlist
```

## Supported Parameters

### Timeframes
- 1m, 3m, 5m, 15m, 30m
- 1h, 2h, 4h, 6h
- 1d, 1w, 1M

### Directions
- Auto (default - bot chooses best)
- Long
- Short

### EMA Periods
- Short: 5-200 (default: 13)
- Long: 5-200 (default: 21)
- Must have short < long

### Coins
Any coin available on Bybit Futures (use !coinlist to see all)

## Testing Checklist

### Basic Functionality Tests
- [ ] !signal BTC (basic signal)
- [ ] !signal ETH 4h long (with timeframe and direction)
- [ ] !signal SOL 1h short ema20 ema50 (full parameters)
- [ ] !signal BTC detail (with detail flag)
- [ ] $BTC (dollar command)
- [ ] $ETH 4h long (dollar with parameters)

### Scan Tests
- [ ] !scan BTC ETH SOL (basic scan)
- [ ] !scan BTC,ETH ema20 ema50 (custom EMA)
- [ ] !scan BTC ETH SOL ema20 ema50 (space separated with EMA)

### Slash Command Tests
- [ ] /help (help embed displays correctly)
- [ ] /signal with all parameters
- [ ] /scan with multiple coins
- [ ] /coinlist (pagination works)

### Error Handling Tests
- [ ] Invalid symbol: !signal INVALID
- [ ] Invalid timeframe: !signal BTC invalid
- [ ] Invalid direction: !signal BTC 1h invalid
- [ ] EMA validation: !signal BTC 1h ema50 ema20 (short >= long)
- [ ] Too many coins: !scan coin1 coin2 coin3 coin4 coin5 coin6

### Edge Cases
- [ ] Mixed case symbols: !signal btc
- [ ] Extra spaces: !signal   BTC    1h
- [ ] Parameter order variations: !signal BTC long 1h ema20 ema50
- [ ] Empty parameters: !scan (no coins)

## Expected Outputs

### Signal Response Format
Each signal should include:
- Embed with title, description, color
- Trading pair, timeframe, generation time
- EMA periods used
- Entry price, stop loss, risk/reward
- Take profit levels
- Confidence percentage
- TradingView chart link
- Attached chart image (PNG)

### Scan Response Format
For each coin in scan:
- Best setup embed
- Confidence rankings for all tested setups
- Chart attachment

### Help Embed Structure
- Title and description
- Command categories (split into parts if needed)
- Supported timeframes
- Usage examples (split into parts)
- Parameter explanations
- Tips section

## Performance Expectations

### Response Times
- Basic signals: < 10 seconds
- Detailed signals: < 15 seconds
- Scans (1-3 coins): < 30 seconds
- Scans (4-5 coins): < 60 seconds

### Error Handling
- Invalid inputs should return helpful error messages
- Network/API errors should be gracefully handled
- Chart generation failures should still send text response

## Environment Setup

### Prerequisites
- Python 3.8+
- Discord bot token in environment
- Bybit API access
- Required Python packages (see requirements.txt)

### Running the Bot
```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Run the bot
python discord_bot.py
```

### Testing in Discord
- Invite bot to test server
- Ensure bot has necessary permissions
- Test in dedicated channel to avoid spam

## Troubleshooting

### Common Issues
- **No response**: Check bot is online and has permissions
- **Chart missing**: Chart generation may have failed, but text should still appear
- **Invalid pair**: Use !coinlist to verify available pairs
- **Slow responses**: Check internet connection and Bybit API status

### Debug Information
- Bot logs all operations with [discord_bot] prefix
- Check terminal output for detailed error messages
- Use /help to verify embed formatting works

## Version Information
- Bot Version: Discord Crypto Screening Tool
- Last Updated: December 2025
- Python Version: 3.8+
- Discord.py Version: 2.3.2