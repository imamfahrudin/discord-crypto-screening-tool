#!/bin/sh

# Create cache files if they don't exist
if [ ! -f /app/pairs_cache.json ]; then
    echo '{}' > /app/pairs_cache.json
    echo "Created pairs_cache.json"
fi

if [ ! -f /app/binance_pairs_cache.json ]; then
    echo '{}' > /app/binance_pairs_cache.json
    echo "Created binance_pairs_cache.json"
fi

# Start cloudflared and the bot
exec cloudflared proxy-dns --upstream https://1.1.1.1/dns-query --port 53 & python -u discord_bot.py
