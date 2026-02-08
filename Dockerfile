FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install cloudflared for DNS over HTTPS
RUN apt-get update && apt-get install -y curl dnsutils && \
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb && \
    dpkg -i /tmp/cloudflared.deb && \
    rm /tmp/cloudflared.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "if [ \"$USE_WARP\" = \"true\" ]; then echo 'Starting with Cloudflare DNS proxy...' && cloudflared proxy-dns --upstream https://1.1.1.1/dns-query --port 53 & sleep 2; else echo 'WARP disabled, starting without DNS proxy...'; fi && python -u discord_bot.py"]