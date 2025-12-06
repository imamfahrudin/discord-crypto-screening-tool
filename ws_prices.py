import asyncio
import json
import os
import logging
import websockets

PRICES = {}
SHOULD_RUN = True

async def _subscribe(ws, symbols):
    # Subscribe format may vary by Bybit region. This attempts a generic tickers subscribe.
    # Adjust 'args' topics if needed (e.g., 'tickers.BTCUSDT' or 'trade.BTCUSDT').
    if not symbols:
        # subscribe to all tickers
        await ws.send(json.dumps({"op":"subscribe","args":["tickers"]}))
        return
    args = []
    for s in symbols:
        args.append(f"tickers.{s}")
    await ws.send(json.dumps({"op":"subscribe","args": args}))

async def _listen(url, symbols):
    backoff = 1
    while SHOULD_RUN:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                logging.info(f"WS connected to {url}")
                await _subscribe(ws, symbols)
                backoff = 1
                async for message in ws:
                    try:
                        data = json.loads(message)
                    except Exception:
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
                            PRICES[sym] = float(price)
                    except Exception:
                        pass
        except Exception as e:
            logging.warning(f"WS error: {e}")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)

def start_ws_in_background(url=None, symbols=None):
    url = url or os.environ.get('BYBIT_WS_URL') or 'wss://stream.bybit.com/v5/public/linear'
    symbols = symbols or []
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        loop.create_task(_listen(url, symbols))
    else:
        import threading
        def runner():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            new_loop.run_until_complete(_listen(url, symbols))
        t = threading.Thread(target=runner, daemon=True)
        t.start()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    start_ws_in_background(symbols=['BTCUSDT','ETHUSDT','SOLUSDT'])
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        SHOULD_RUN = False