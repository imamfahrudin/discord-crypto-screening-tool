import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import time
import os
import json

LOG_PREFIX = "[bitget_data]"

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
CACHE_FILE = os.path.join(os.path.dirname(__file__), 'bitget_pairs_cache.json')
CACHE_EXPIRY = 3600  # 1 hour in seconds

BITGET_BASE_URL = 'https://api.bitget.com'  # Bitget API

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
    
    print(f"{LOG_PREFIX} 🌐 Fetching pairs from Bitget Futures API")
    pairs = []
    
    try:
        # Bitget v2 API endpoint for USDT-M futures
        url = f"{BITGET_BASE_URL}/api/v2/mix/market/contracts"
        params = {'productType': 'USDT-FUTURES'}  # Changed from umcbl to USDT-FUTURES
        resp = _SESSION.get(url, params=params, timeout=(10, 30))
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('code') != '00000':
            print(f"{LOG_PREFIX} ⚠️ API error: {data.get('msg', 'Unknown error')}")
        else:
            symbols = data.get('data', [])
            for symbol_info in symbols:
                if isinstance(symbol_info, dict):
                    symbol = symbol_info.get('symbol', '')
                    quote_coin = symbol_info.get('quoteCoin', '')
                    
                    # Only get USDT perpetual futures
                    # Bitget v2 format is just BTCUSDT (no _UMCBL suffix)
                    if quote_coin == 'USDT' and symbol.endswith('USDT'):
                        if symbol not in pairs:
                            pairs.append(symbol)
            
            print(f"{LOG_PREFIX} 📊 Fetched {len(pairs)} trading pairs from Bitget Futures")
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Error fetching pairs from Bitget: {e}")
    
    if pairs:
        _PAIRS_CACHE = pairs
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
    """Normalize symbol to Bitget format (BTCUSDT)"""
    s = (symbol or '').strip().upper().replace('-', '').replace('/', '').replace('_', '')
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
    """Fetch OHLC data from Bitget Futures"""
    symbol = normalize_symbol(symbol)
    print(f"{LOG_PREFIX} 📈 Fetching OHLC for {symbol} {timeframe}")
    
    # Bitget interval mapping for v2 API
    # Bitget API requires specific granularity format (uppercase H and D)
    tf_map = {
        '1m': '1m',
        '3m': '3m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1H',    # Bitget uses uppercase H
        '2h': '2H',
        '4h': '4H',
        '6h': '6H',
        '12h': '12H',
        '1d': '1D',    # Bitget uses uppercase D
        '1w': '1W',    # Bitget uses 1W not 1week
        '1M': '1M'
    }
    
    interval = tf_map.get(timeframe.lower())
    if not interval:
        print(f"{LOG_PREFIX} ❌ Invalid timeframe: {timeframe}")
        raise ValueError(f"Invalid timeframe {timeframe}")
    
    # Bitget v2 API uses symbol without suffix (just BTCUSDT)
    bitget_symbol = symbol
    
    # Calculate time range in milliseconds
    # Bitget uses NORMAL convention: startTime = oldest, endTime = newest
    current_time = int(time.time() * 1000)
    
    # Calculate milliseconds per interval (use Bitget format keys)
    interval_ms = {
        '1m': 60000, '3m': 180000, '5m': 300000, '15m': 900000, '30m': 1800000,
        '1H': 3600000, '2H': 7200000, '4H': 14400000, '6H': 21600000, '12H': 43200000,
        '1D': 86400000, '1W': 604800000, '1M': 2592000000
    }
    
    # Calculate the oldest point we need (current - duration)
    duration_ms = interval_ms.get(interval, 3600000) * limit
    oldest_time = current_time - duration_ms
    
    # Bitget v2 API endpoint - NORMAL convention: startTime = oldest, endTime = newest
    url = f"{BITGET_BASE_URL}/api/v2/mix/market/candles"
    params = {
        'symbol': bitget_symbol,
        'productType': 'USDT-FUTURES',
        'granularity': interval,
        'startTime': str(oldest_time),   # OLDEST timestamp (start of range)
        'endTime': str(current_time)     # NEWEST timestamp (end of range)
    }
    
    print(f"{LOG_PREFIX} 🔍 DEBUG - Request parameters:")
    print(f"{LOG_PREFIX}   - current_time (newest): {current_time}")
    print(f"{LOG_PREFIX}   - oldest_time: {oldest_time}")
    print(f"{LOG_PREFIX}   - duration_ms: {duration_ms}")
    print(f"{LOG_PREFIX}   - interval: {interval}")
    print(f"{LOG_PREFIX}   - limit: {limit}")
    
    try:
        resp = _SESSION.get(url, params=params, timeout=(10, 30))
        
        # Print response before raising error
        print(f"{LOG_PREFIX} 📥 Response status: {resp.status_code}")
        print(f"{LOG_PREFIX} 📥 Response body: {resp.text[:500]}")  # First 500 chars
        
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('code') != '00000':
            print(f"{LOG_PREFIX} ❌ API error code: {data.get('code')}")
            print(f"{LOG_PREFIX} ❌ API error message: {data.get('msg', 'Unknown error')}")
            print(f"{LOG_PREFIX} ❌ Full response: {data}")
            raise Exception(f"Bitget API error: {data.get('msg', 'Unknown error')}")
        
        candles = data.get('data', [])
        if not candles:
            print(f"{LOG_PREFIX} ⚠️ No candle data returned for {symbol}")
            raise Exception(f"No candle data for {symbol}")
        
        # Bitget v2 returns: [timestamp, open, high, low, close, baseVol, quoteVol]
        # Convert to DataFrame
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'quoteVol'])
        
        # Convert data types
        df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df['open'] = pd.to_numeric(df['open'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        
        # Convert timestamp from milliseconds to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Sort by timestamp ascending (oldest first)
        df = df.sort_values('timestamp', ascending=True).reset_index(drop=True)
        
        # Drop the quoteVol column as it's not needed
        df = df.drop('quoteVol', axis=1)
        
        print(f"{LOG_PREFIX} ✅ Fetched {len(df)} candles for {symbol} {timeframe}")
        return df
        
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Error fetching OHLC data: {e}")
        raise

def get_last_price_from_rest(symbol: str):
    """Get last price for a symbol from Bitget REST API"""
    symbol = normalize_symbol(symbol)
    # Bitget v2 API uses symbol without suffix
    bitget_symbol = symbol
    
    print(f"{LOG_PREFIX} 💰 Fetching last price for {symbol}")
    
    try:
        # Bitget v2 API endpoint for ticker
        url = f"{BITGET_BASE_URL}/api/v2/mix/market/ticker"
        params = {
            'symbol': bitget_symbol,
            'productType': 'USDT-FUTURES'
        }
        resp = _SESSION.get(url, params=params, timeout=(10, 30))
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('code') != '00000':
            print(f"{LOG_PREFIX} ❌ API error: {data.get('msg', 'Unknown error')}")
            return None
        
        # v2 API returns array of tickers
        ticker_list = data.get('data', [])
        if ticker_list and len(ticker_list) > 0:
            ticker_data = ticker_list[0]
            last_price = float(ticker_data.get('lastPr', 0))
            print(f"{LOG_PREFIX} ✅ Last price for {symbol}: {last_price}")
            return last_price
        else:
            print(f"{LOG_PREFIX} ⚠️ No ticker data for {symbol}")
            return None
            
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Error fetching last price: {e}")
        return None
