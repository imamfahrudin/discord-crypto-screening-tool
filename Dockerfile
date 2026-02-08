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

# Create startup script
RUN echo '#!/bin/bash\n\
if [ "$USE_WARP" = "true" ]; then\n\
    warp-svc >/dev/null 2>&1 &\n\
    echo "Waiting for WARP daemon to start..."\n\
    while [ ! -S /run/cloudflare-warp/warp_service ]; do\n\
        sleep 1\n\
    done\n\
    echo "Daemon ready, registering..."\n\
    echo "y" | script -q -c "warp-cli registration new" /dev/null\n\
    echo "Setting WARP mode to warp+doh..."\n\
    warp-cli mode warp+doh\n\
    echo "Attempting to connect WARP..."\n\
    warp-cli connect\n\
    echo "Waiting for WARP connection..."\n\
    sleep 5\n\
    for i in {1..10}; do\n\
        echo "Connection attempt $i:"\n\
        warp-cli status\n\
        if warp-cli status | grep -q "Status update: Connected"; then\n\
            echo "✅ WARP Connected Successfully!"\n\
            break\n\
        else\n\
            echo "Attempt $i failed, retrying connection..."\n\
            warp-cli connect >/dev/null 2>&1\n\
            sleep 3\n\
        fi\n\
    done\n\
    echo "Final WARP status:"\n\
    warp-cli status\n\
    echo "Testing connection to Bybit..."\n\
    if curl -I https://api.bybit.com --connect-timeout 10 >/dev/null 2>&1; then\n\
        echo "✅ Bybit is reachable!"\n\
    else\n\
        echo "⚠️  Warning: Could not reach Bybit - WARP may not be working"\n\
    fi\n\
else\n\
    echo "WARP disabled, starting without VPN..."\n\
fi\n\
python -u discord_bot.py' > /app/start.sh && chmod +x /app/start.sh

ENV PYTHONUNBUFFERED=1
CMD ["/app/start.sh"]