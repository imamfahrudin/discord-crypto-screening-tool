Final fixed trading bot (with RSI + EMA)
=======================================

Files included:
  - config.json (replace with your Discord token)
  - discord_bot.py
  - ws_prices.py
  - bybit_data.py
  - signal_logic.py
  - utils.py
  - pairs_cache.json (example)
  - requirements.txt
  - README.md

Instructions:
  1. Install deps: pip install -r requirements.txt
  2. Update config.json with your new Discord token
  3. Run: python discord_bot.py
  4. Use in Discord: !signal BTCUSDT 1h long
