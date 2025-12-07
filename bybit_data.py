import requests
import pandas as pd
import time
import os
import json

_PAIRS_CACHE = None
CACHE_FILE = os.path.join(os.path.dirname(__file__), 'pairs_cache.json')
CACHE_EXPIRY = 3600  # 1 hour in seconds

BYBIT_URLS = [
    'https://api.bybit.com/v5/market/instruments-info?category=linear',
    'https://api.bybit.com/v5/market/instruments-info?category=spot',
    'https://api.bybitglobal.com/v5/market/instruments-info?category=linear',
    'https://api.bybitglobal.com/v5/market/instruments-info?category=spot'
]

def _load_pairs_from_disk():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'pairs' in data and 'timestamp' in data:
                    current_time = time.time()
                    if current_time - data['timestamp'] < CACHE_EXPIRY:
                        return data['pairs']
    except Exception:
        pass
    return None

def get_all_pairs(force_refresh=False):
    global _PAIRS_CACHE
    if _PAIRS_CACHE is not None and not force_refresh:
        return _PAIRS_CACHE
    disk = _load_pairs_from_disk()
    if disk and not force_refresh:
        _PAIRS_CACHE = disk
        return _PAIRS_CACHE
    pairs = []
    for url in BYBIT_URLS:
        try:
            resp = requests.get(url, timeout=8)
            data = resp.json()
            result = data.get('result', {}) or {}
            symbol_list = result.get('list', []) or []
            for s in symbol_list:
                if isinstance(s, dict):
                    sym = s.get('symbol','')
                    status = s.get('status','')
                    if sym.endswith('USDT'):
                        if status.lower() == 'trading':
                            if sym not in pairs:
                                pairs.append(sym)
                        else:
                            print(f"⚠️ Skipping {sym} with status: {status}")  # Debug non-trading pairs
        except Exception:
            time.sleep(0.5)
            continue
    if pairs:
        _PAIRS_CACHE = pairs
        print(f"📊 Fetched {len(pairs)} trading pairs from Bybit API")
        try:
            cache_data = {
                'pairs': pairs,
                'timestamp': time.time()
            }
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache_data, f)
        except Exception:
            pass
        return _PAIRS_CACHE
    _PAIRS_CACHE = disk or []
    return _PAIRS_CACHE

def normalize_symbol(symbol: str) -> str:
    s = (symbol or '').strip().upper().replace('-', '').replace('/', '')
    if not s.endswith('USDT'):
        s = s + 'USDT'
    return s

def pair_exists(symbol: str) -> bool:
    symbol = normalize_symbol(symbol)
    pairs = get_all_pairs()
    if symbol in pairs:
        return True
    # Not found in cache, force refresh from API
    print(f"🔄 Refreshing pairs cache for {symbol}...")
    pairs = get_all_pairs(force_refresh=True)
    found = symbol in pairs
    print(f"✅ Cache refreshed. {symbol} found: {found}")
    return found

def fetch_ohlc(symbol: str, timeframe: str, limit: int = 500):
    symbol = normalize_symbol(symbol)
    tf_map = {
        '1m': '1',
        '3m': '3',
        '5m': '5',
        '15m': '15',
        '30m': '30',
        '1h': '60',
        '4h': '240',
        '1d': 'D'
    }
    timeframe = timeframe.lower()
    if timeframe not in tf_map:
        raise ValueError(f"Timeframe {timeframe} invalid. Choose one of {list(tf_map.keys())}")
    interval = tf_map[timeframe]
    if not pair_exists(symbol):
        raise ValueError(f"Pair {symbol} not available in Bybit Futures (linear).") 
    for domain in ['api.bybit.com','api.bybitglobal.com']:
        try:
            url = f"https://{domain}/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
            resp = requests.get(url, timeout=8)
            data = resp.json()
            result = data.get('result', {}) or {}
            ohlc_list = result.get('list', []) or []
            if isinstance(ohlc_list, list) and len(ohlc_list) > 0:
                df = pd.DataFrame(ohlc_list, columns=['open_time','open','high','low','close','volume','turnover'])
                df = df.astype({'open':'float','high':'float','low':'float','close':'float','volume':'float'})
                df = df.iloc[::-1].reset_index(drop=True)
                try:
                    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
                except Exception:
                    pass
                return df
        except Exception:
            time.sleep(0.5)
            continue
    raise ValueError(f"No candle data for {symbol} {timeframe}")

def get_last_price_from_rest(symbol: str):
    symbol = normalize_symbol(symbol)
    for domain in ['api.bybit.com','api.bybitglobal.com']:
        try:
            url = f"https://{domain}/v5/market/tickers?category=linear&symbol={symbol}"
            resp = requests.get(url, timeout=5).json()
            if resp.get('retCode') != 0:
                continue
            result = resp.get('result', {}) or {}
            ticker_list = result.get('list', []) or []
            if ticker_list:
                tick = ticker_list[0]
                last_price = float(tick.get('lastPrice', tick.get('price', 0) or 0))
                mark_price = float(tick.get('markPrice', last_price))
                final = mark_price if abs(mark_price - last_price) < 5 else last_price
                return float(final)
        except Exception:
            time.sleep(0.2)
            continue
    return None