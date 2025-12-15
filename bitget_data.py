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
        url = f"{BITGET_BASE_URL}/api/mix/v1/market/contracts"
        params = {'productType': 'umcbl'}  # USDT-M futures
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
                    if quote_coin == 'USDT' and symbol.endswith('_UMCBL'):
                        # Convert from Bitget format (BTCUSDT_UMCBL) to standard (BTCUSDT)
                        standard_symbol = symbol.replace('_UMCBL', '')
                        if standard_symbol not in pairs:
                            pairs.append(standard_symbol)
            
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
    
    # Bitget interval mapping
    tf_map = {
        '1m': '1m',
        '3m': '3m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1H',
        '2h': '2H',
        '4h': '4H',
        '6h': '6H',
        '12h': '12H',
        '1d': '1D',
        '1w': '1W',
        '1M': '1M'
    }
    
    interval = tf_map.get(timeframe.lower())
    if not interval:
        print(f"{LOG_PREFIX} ❌ Invalid timeframe: {timeframe}")
        raise ValueError(f"Invalid timeframe {timeframe}")
    
    # Bitget uses symbol format with _UMCBL suffix for API calls
    bitget_symbol = f"{symbol}_UMCBL"
    
    # Calculate end time (current time) and limit
    end_time = int(time.time() * 1000)
    
    url = f"{BITGET_BASE_URL}/api/mix/v1/market/candles"
    params = {
        'symbol': bitget_symbol,
        'granularity': interval,
        'limit': min(limit, 1000),  # Bitget max is 1000
        'endTime': end_time
    }
    
    try:
        resp = _SESSION.get(url, params=params, timeout=(10, 30))
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('code') != '00000':
            print(f"{LOG_PREFIX} ❌ API error: {data.get('msg', 'Unknown error')}")
            raise Exception(f"Bitget API error: {data.get('msg', 'Unknown error')}")
        
        candles = data.get('data', [])
        if not candles:
            print(f"{LOG_PREFIX} ⚠️ No candle data returned for {symbol}")
            raise Exception(f"No candle data for {symbol}")
        
        # Bitget returns: [timestamp, open, high, low, close, volume, usdtVol]
        # Convert to DataFrame
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'usdtVol'])
        
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
        
        # Drop the usdtVol column as it's not needed
        df = df.drop('usdtVol', axis=1)
        
        print(f"{LOG_PREFIX} ✅ Fetched {len(df)} candles for {symbol} {timeframe}")
        return df
        
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Error fetching OHLC data: {e}")
        raise

def get_last_price_from_rest(symbol: str):
    """Get last price for a symbol from Bitget REST API"""
    symbol = normalize_symbol(symbol)
    bitget_symbol = f"{symbol}_UMCBL"
    
    print(f"{LOG_PREFIX} 💰 Fetching last price for {symbol}")
    
    try:
        url = f"{BITGET_BASE_URL}/api/mix/v1/market/ticker"
        params = {'symbol': bitget_symbol}
        resp = _SESSION.get(url, params=params, timeout=(10, 30))
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('code') != '00000':
            print(f"{LOG_PREFIX} ❌ API error: {data.get('msg', 'Unknown error')}")
            return None
        
        ticker_data = data.get('data', {})
        if ticker_data:
            last_price = float(ticker_data.get('last', 0))
            print(f"{LOG_PREFIX} ✅ Last price for {symbol}: {last_price}")
            return last_price
        else:
            print(f"{LOG_PREFIX} ⚠️ No ticker data for {symbol}")
            return None
            
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Error fetching last price: {e}")
        return None
