#!/bin/sh

# Create data directory if it doesn't exist
mkdir -p /app/data

# Create cache files if they don't exist
if [ ! -f /app/data/pairs_cache.json ]; then
    echo '{}' > /app/data/pairs_cache.json
    echo "Created data/pairs_cache.json"
fi

if [ ! -f /app/data/binance_pairs_cache.json ]; then
    echo '{}' > /app/data/binance_pairs_cache.json
    echo "Created data/binance_pairs_cache.json"
fi

# Start cloudflared and the bot
exec cloudflared proxy-dns --upstream https://1.1.1.1/dns-query --port 53 & python -u discord_bot.py
