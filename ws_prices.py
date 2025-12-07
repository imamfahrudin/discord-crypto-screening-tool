import asyncio
import json
import os
import logging
import websockets

LOG_PREFIX = "[ws_prices]"

PRICES = {}
SHOULD_RUN = True

async def _subscribe(ws, symbols):
    # Subscribe format may vary by Bybit region. This attempts a generic tickers subscribe.
    # Adjust 'args' topics if needed (e.g., 'tickers.BTCUSDT' or 'trade.BTCUSDT').
    if not symbols:
        # subscribe to all tickers
        print(f"{LOG_PREFIX} 📡 Subscribing to all tickers")
        await ws.send(json.dumps({"op":"subscribe","args":["tickers"]}))
        return
    args = []
    for s in symbols:
        args.append(f"tickers.{s}")
    print(f"{LOG_PREFIX} 📡 Subscribing to specific symbols: {symbols}")
    await ws.send(json.dumps({"op":"subscribe","args": args}))

async def _listen(url, symbols):
    backoff = 1
    print(f"{LOG_PREFIX} 🚀 Starting WebSocket listener for {url}")
    while SHOULD_RUN:
        try:
            print(f"{LOG_PREFIX} 🔌 Attempting WebSocket connection to {url} (backoff: {backoff}s)")
            async with websockets.connect(url, ping_interval=20) as ws:
                logging.info(f"WS connected to {url}")
                print(f"{LOG_PREFIX} ✅ WebSocket connected successfully")
                await _subscribe(ws, symbols)
                backoff = 1
                message_count = 0
                price_update_count = 0
                async for message in ws:
                    try:
                        data = json.loads(message)
                        message_count += 1
                        if message_count % 100 == 0:  # Log every 100 messages to avoid spam
                            print(f"{LOG_PREFIX} 📊 Processed {message_count} messages")
                    except Exception as e:
                        print(f"{LOG_PREFIX} ❌ Failed to parse message: {e}")
                        continue
                    
                    # Typical Bybit v5 ticker payload:
                    # {'topic':'tickers.BTCUSDT','data':[{'symbol':'BTCUSDT','lastPrice':'...'}]}
                    topic = data.get('topic') or data.get('arg', {}).get('channel')
                    payload = data.get('data') or data.get('params') or data.get('tick')
                    sym = None
                    if isinstance(topic, str):
                        parts = topic.split('.')
                        if len(parts) >= 2 and parts[-1].upper().endswith('USDT'):
                            sym = parts[-1].upper()
                        else:
                            # try to find symbol in topic
                            for p in parts:
                                if p.upper().endswith('USDT'):
                                    sym = p.upper()
                    
                    price = None
                    if isinstance(payload, list) and payload:
                        first = payload[0]
                        if isinstance(first, dict):
                            price = first.get('lastPrice') or first.get('price') or first.get('p')
                    elif isinstance(payload, dict):
                        price = payload.get('lastPrice') or payload.get('price') or payload.get('p')
                    
                    try:
                        if price is not None and sym:
                            old_price = PRICES.get(sym)
                            PRICES[sym] = float(price)
                            if old_price != float(price):
                                price_update_count += 1
                                if price_update_count % 100 == 0:
                                    print(f"{LOG_PREFIX} 💰 Price update #{price_update_count}: {sym} = {price} (was {old_price})")
                        elif price is not None:
                            print(f"{LOG_PREFIX} ⚠️ Received price {price} but no symbol identified from topic: {topic}")
                    except Exception as e:
                        print(f"{LOG_PREFIX} ❌ Error processing price update: {e}")
        except Exception as e:
            print(f"{LOG_PREFIX} ❌ WebSocket error: {e}")
            logging.warning(f"WS error: {e}")
        if SHOULD_RUN:
            print(f"{LOG_PREFIX} ⏳ Reconnecting in {backoff} seconds...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

def start_ws_in_background(url=None, symbols=None):
    url = url or os.environ.get('BYBIT_WS_URL') or 'wss://stream.bybit.com/v5/public/linear'
    symbols = symbols or []
    print(f"{LOG_PREFIX} 🚀 Starting WebSocket in background - URL: {url}, Symbols: {symbols}")
    
    try:
        loop = asyncio.get_event_loop()
        print(f"{LOG_PREFIX} ✅ Using existing event loop")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        print(f"{LOG_PREFIX} 🔄 Created new event loop")
    
    if loop.is_running():
        print(f"{LOG_PREFIX} 📡 Creating task in running loop")
        loop.create_task(_listen(url, symbols))
    else:
        print(f"{LOG_PREFIX} 🧵 Starting WebSocket in background thread")
        import threading
        def runner():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            new_loop.run_until_complete(_listen(url, symbols))
        t = threading.Thread(target=runner, daemon=True)
        t.start()
        print(f"{LOG_PREFIX} ✅ Background thread started")

if __name__ == '__main__':
    print(f"{LOG_PREFIX} 🏃 Running ws_prices.py as standalone script")
    logging.basicConfig(level=logging.INFO)
    print(f"{LOG_PREFIX} 📡 Starting WebSocket with test symbols")
    start_ws_in_background(symbols=['BTCUSDT','ETHUSDT','SOLUSDT'])
    try:
        print(f"{LOG_PREFIX} ⏳ Entering main loop - press Ctrl+C to exit")
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"{LOG_PREFIX} 🛑 Received interrupt signal, shutting down...")
        SHOULD_RUN = False
        print(f"{LOG_PREFIX} ✅ Shutdown complete")