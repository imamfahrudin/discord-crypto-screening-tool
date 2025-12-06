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
  - Dockerfile
  - docker-compose.yml

Instructions:
  1. Install deps: pip install -r requirements.txt
  2. Update config.json with your new Discord token
  3. Run: python discord_bot.py
  4. Use in Discord: !signal BTCUSDT 1h long

Docker Instructions:
  1. Update config.json with your Discord token
  2. (Optional) Create .env file for additional environment variables
  3. Run: docker-compose up -d
  4. Check logs: docker-compose logs -f
