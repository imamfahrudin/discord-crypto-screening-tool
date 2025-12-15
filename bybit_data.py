import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import time
import os
import json

LOG_PREFIX = "[bybit_data]"

# Create a session with retry strategy and connection pooling
def _create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,  # Total retry attempts
        backoff_factor=1,  # Wait 1s, 2s, 4s, 8s, 16s between retries
        status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
        allowed_methods=["GET"],  # Only retry GET requests
        raise_on_status=False
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=20,
        pool_block=False
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    # Set reasonable timeouts
    session.timeout = (10, 30)  # (connect timeout, read timeout)
    return session

_SESSION = _create_session()

_PAIRS_CACHE = None
CACHE_FILE = os.path.join(os.path.dirname(__file__), 'bybit_pairs_cache.json')
CACHE_EXPIRY = 3600  # 1 hour in seconds

BYBIT_URLS = [
    'https://api.bybit.com/v5/market/instruments-info?category=linear',
    'https://api.bybitglobal.com/v5/market/instruments-info?category=linear'
]

def _load_pairs_from_disk():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'pairs' in data and 'timestamp' in data:
                    current_time = time.time()
                    if current_time - data['timestamp'] < CACHE_EXPIRY:
                        print(f"{LOG_PREFIX} 📂 Loaded pairs from disk cache")
                        return data['pairs']
        print(f"{LOG_PREFIX} 📂 No valid cache found on disk")
    except Exception as e:
        print(f"{LOG_PREFIX} 📂 Error loading cache from disk: {e}")
    return None

def get_all_pairs(force_refresh=False):
    global _PAIRS_CACHE
    if _PAIRS_CACHE is not None and not force_refresh:
        print(f"{LOG_PREFIX} 💾 Using in-memory pairs cache")
        return _PAIRS_CACHE
    disk = _load_pairs_from_disk()
    if disk and not force_refresh:
        _PAIRS_CACHE = disk
        print(f"{LOG_PREFIX} 💾 Using disk pairs cache")
        return _PAIRS_CACHE
    print(f"{LOG_PREFIX} 🌐 Fetching pairs from Bybit API")
    pairs = []
    for url in BYBIT_URLS:
        print(f"{LOG_PREFIX} 🔗 Trying URL: {url}")
        cursor = ""  # Start with empty cursor for first page
        page_count = 0

        while True:
            page_count += 1
            params = {
                'category': 'linear',
                'status': 'Trading',
                'limit': 1000  # Maximum allowed per page
            }
            if cursor:
                params['cursor'] = cursor

            try:
                resp = _SESSION.get(url, params=params, timeout=(10, 30))  # 10s connect, 30s read
                resp.raise_for_status()  # Raise exception for bad status codes
                data = resp.json()

                if data.get('retCode') != 0:
                    print(f"{LOG_PREFIX} ⚠️ API error from {url}: {data.get('retMsg', 'Unknown error')}")
                    break

                result = data.get('result', {}) or {}
                symbol_list = result.get('list', []) or []

                if not symbol_list:
                    print(f"{LOG_PREFIX} 📄 No more symbols on page {page_count} from {url}")
                    break

                page_pairs = 0
                for s in symbol_list:
                    if isinstance(s, dict):
                        sym = s.get('symbol','')
                        status = s.get('status','')
                        if sym.endswith('USDT') and status.lower() == 'trading':
                            if sym not in pairs:
                                pairs.append(sym)
                                page_pairs += 1

                print(f"{LOG_PREFIX} 📄 Page {page_count}: Added {page_pairs} new USDT pairs from {url}")

                # Check for next page
                next_cursor = result.get('nextPageCursor')
                if not next_cursor:
                    print(f"{LOG_PREFIX} 📄 No more pages from {url}")
                    break

                cursor = next_cursor
                time.sleep(0.1)  # Small delay between pages to be respectful

            except Exception as e:
                print(f"{LOG_PREFIX} ❌ Error fetching page {page_count} from {url}: {e}")
                break
    if pairs:
        _PAIRS_CACHE = pairs
        print(f"{LOG_PREFIX} 📊 Fetched {len(pairs)} trading pairs from Bybit API")
        try:
            cache_data = {
                'pairs': pairs,
                'timestamp': time.time()
            }
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache_data, f)
            print(f"{LOG_PREFIX} 💾 Saved pairs to disk cache")
        except Exception as e:
            print(f"{LOG_PREFIX} ❌ Error saving cache to disk: {e}")
        return _PAIRS_CACHE
    _PAIRS_CACHE = disk or []
    print(f"{LOG_PREFIX} ⚠️ No pairs fetched, using fallback cache")
    return _PAIRS_CACHE

def normalize_symbol(symbol: str) -> str:
    s = (symbol or '').strip().upper().replace('-', '').replace('/', '')
    if not s.endswith('USDT'):
        s = s + 'USDT'
    return s

def pair_exists(symbol: str) -> bool:
    symbol = normalize_symbol(symbol)
    print(f"{LOG_PREFIX} 🔍 Checking if {symbol} exists in cache")
    pairs = get_all_pairs()
    if symbol in pairs:
        print(f"{LOG_PREFIX} ✅ {symbol} found in cache")
        return True
    # Not found in cache, force refresh from API with retry
    print(f"{LOG_PREFIX} 🔄 Refreshing pairs cache for {symbol}...")
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            pairs = get_all_pairs(force_refresh=True)
            found = symbol in pairs
            print(f"{LOG_PREFIX} ✅ Cache refreshed. {symbol} found: {found}")
            return found
        except Exception as e:
            if attempt < max_attempts - 1:
                wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                print(f"{LOG_PREFIX} ⚠️ Refresh attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"{LOG_PREFIX} ❌ All refresh attempts failed for {symbol}")
                return False

def fetch_ohlc(symbol: str, timeframe: str, limit: int = 500):
    symbol = normalize_symbol(symbol)
    print(f"{LOG_PREFIX} 📈 Fetching OHLC for {symbol} {timeframe}")
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
        raise ValueError(f"Timeframe {timeframe} tidak valid. Pilih salah satu dari {list(tf_map.keys())}")
    interval = tf_map[timeframe]
    if not pair_exists(symbol):
        raise ValueError(f"Pasangan {symbol} tidak tersedia di Bybit Futures (linear).") 
    for domain in ['api.bybit.com','api.bybitglobal.com']:
        print(f"{LOG_PREFIX} 🔗 Trying domain: {domain}")
        retries = 3
        for attempt in range(retries):
            try:
                url = f"https://{domain}/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
                resp = _SESSION.get(url, timeout=(15, 45))  # Longer timeout for OHLC data
                resp.raise_for_status()
                data = resp.json()
                result = data.get('result', {}) or {}
                ohlc_list = result.get('list', []) or []
                if isinstance(ohlc_list, list) and len(ohlc_list) > 0:
                    df = pd.DataFrame(ohlc_list, columns=['open_time','open','high','low','close','volume','turnover'])
                    df = df.astype({'open':'float','high':'float','low':'float','close':'float','volume':'float'})
                    df = df.iloc[::-1].reset_index(drop=True)
                    try:
                        df['open_time'] = pd.to_datetime(df['open_time'].astype('int64'), unit='ms')
                    except Exception as e:
                        print(f"{LOG_PREFIX} ⚠️ Error converting timestamps: {e}")
                    print(f"{LOG_PREFIX} ✅ Successfully fetched {len(df)} candles for {symbol}")
                    return df
            except requests.exceptions.Timeout as e:
                if attempt < retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"{LOG_PREFIX} ⏱️ Timeout on {domain} (attempt {attempt + 1}/{retries}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"{LOG_PREFIX} ❌ All retry attempts exhausted for {domain}: {e}")
                    break
            except requests.exceptions.RequestException as e:
                print(f"{LOG_PREFIX} ❌ Request error on {domain}: {e}")
                time.sleep(1)
                break
            except Exception as e:
                print(f"{LOG_PREFIX} ❌ Unexpected error on {domain}: {e}")
                time.sleep(0.5)
                break
    raise ValueError(f"Tidak ada data candle untuk {symbol} {timeframe}")

def get_last_price_from_rest(symbol: str):
    symbol = normalize_symbol(symbol)
    print(f"{LOG_PREFIX} 💰 Fetching last price for {symbol}")
    for domain in ['api.bybit.com','api.bybitglobal.com']:
        print(f"{LOG_PREFIX} 🔗 Trying domain: {domain}")
        retries = 3
        for attempt in range(retries):
            try:
                url = f"https://{domain}/v5/market/tickers?category=linear&symbol={symbol}"
                resp = _SESSION.get(url, timeout=(8, 15))  # 8s connect, 15s read
                resp.raise_for_status()
                data = resp.json()
                if data.get('retCode') != 0:
                    print(f"{LOG_PREFIX} ⚠️ Non-zero retCode from {domain}: {data.get('retCode')}")
                    if attempt < retries - 1:
                        time.sleep(1)
                        continue
                    else:
                        break
                result = data.get('result', {}) or {}
                ticker_list = result.get('list', []) or []
                if ticker_list:
                    tick = ticker_list[0]
                    last_price = float(tick.get('lastPrice', tick.get('price', 0) or 0))
                    mark_price = float(tick.get('markPrice', last_price))
                    final = mark_price if abs(mark_price - last_price) < 5 else last_price
                    print(f"{LOG_PREFIX} ✅ Got price: {final} for {symbol}")
                    return float(final)
            except requests.exceptions.Timeout as e:
                if attempt < retries - 1:
                    wait_time = (attempt + 1) * 1.5
                    print(f"{LOG_PREFIX} ⏱️ Timeout on {domain} (attempt {attempt + 1}/{retries}). Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"{LOG_PREFIX} ❌ All retry attempts exhausted for {domain}")
                    break
            except requests.exceptions.RequestException as e:
                print(f"{LOG_PREFIX} ❌ Request error on {domain}: {e}")
                time.sleep(0.5)
                break
            except Exception as e:
                print(f"{LOG_PREFIX} ❌ Unexpected error on {domain}: {e}")
                time.sleep(0.3)
                break
    print(f"{LOG_PREFIX} ❌ Failed to get price for {symbol}")
    return None