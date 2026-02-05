FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install cloudflared for DNS over HTTPS (bypasses ISP DNS blocking)
RUN apt-get update && apt-get install -y curl wget && \
    wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -O /tmp/cloudflared.deb && \
    dpkg -i /tmp/cloudflared.deb || apt-get install -f -y && \
    rm /tmp/cloudflared.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create startup script for better DNS-over-HTTPS reliability
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Starting cloudflared DNS proxy..."\n\
cloudflared proxy-dns \\\n\
  --address 0.0.0.0 \\\n\
  --port 5053 \\\n\
  --upstream https://1.1.1.1/dns-query \\\n\
  --upstream https://1.0.0.1/dns-query \\\n\
  --upstream https://8.8.8.8/dns-query \\\n\
  --upstream https://8.8.4.4/dns-query \\\n\
  --max-upstream-conns 10 \\\n\
  > /var/log/cloudflared.log 2>&1 &\n\
\n\
CLOUDFLARED_PID=$!\n\
echo "Cloudflared started with PID $CLOUDFLARED_PID"\n\
\n\
# Wait for cloudflared to be ready\n\
echo "Waiting for DNS proxy to be ready..."\n\
sleep 3\n\
\n\
# Configure system to use cloudflared\n\
echo "nameserver 127.0.0.1" > /etc/resolv.conf\n\
echo "nameserver 8.8.8.8" >> /etc/resolv.conf\n\
echo "nameserver 1.1.1.1" >> /etc/resolv.conf\n\
echo "options timeout:5 attempts:3" >> /etc/resolv.conf\n\
\n\
echo "DNS configuration complete. Starting bot..."\n\
exec python -u discord_bot.py\n\
' > /app/start.sh && chmod +x /app/start.sh

COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["/app/start.sh"]