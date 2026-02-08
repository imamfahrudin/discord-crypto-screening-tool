FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install warp-cli for DNS over HTTPS
RUN apt-get update && apt-get install -y curl lsb-release gnupg && \
    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --dearmor | tee /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg > /dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/cloudflare-client.list && \
    apt-get update && apt-get install -y cloudflare-warp && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "if [ \"$USE_WARP\" = \"true\" ]; then warp-svc >/dev/null 2>&1 & echo 'Waiting for WARP daemon to start...' && while [ ! -S /run/cloudflare-warp/warp_service ]; do sleep 1; done && echo 'Daemon ready, registering...' && echo 'y' | script -q -c 'warp-cli registration new' /dev/null && warp-cli mode warp+doh && warp-cli connect && echo 'Waiting for WARP connection...' && sleep 5 && for i in 1 2 3 4 5 6 7 8 9 10; do echo \"Connection attempt $i:\" && warp-cli status && if warp-cli status | grep -q 'Status.*Connected\|Connected'; then echo '✅ WARP Connected Successfully!'; break; else echo \"Attempt $i failed, waiting...\"; sleep 3; fi; done && echo 'Final WARP status:' && warp-cli status && echo 'Testing connection to Bybit...' && curl -I https://api.bybit.com --connect-timeout 10 || echo 'Warning: Could not reach Bybit - WARP may not be working'; else echo 'WARP disabled, starting without VPN...'; fi && python -u discord_bot.py"]