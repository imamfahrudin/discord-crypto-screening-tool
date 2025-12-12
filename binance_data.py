import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import time
import os
import json

LOG_PREFIX = "[binance_data]"

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
CACHE_FILE = os.path.join(os.path.dirname(__file__), 'binance_pairs_cache.json')
CACHE_EXPIRY = 3600  # 1 hour in seconds

BINANCE_BASE_URL = 'https://fapi.binance.com'  # Binance Futures

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
    
    print(f"{LOG_PREFIX} 🌐 Fetching pairs from Binance Futures API")
    pairs = []
    
    try:
        url = f"{BINANCE_BASE_URL}/fapi/v1/exchangeInfo"
        resp = _SESSION.get(url, timeout=(10, 30))
        resp.raise_for_status()
        data = resp.json()
        
        symbols = data.get('symbols', [])
        for symbol_info in symbols:
            if isinstance(symbol_info, dict):
                symbol = symbol_info.get('symbol', '')
                status = symbol_info.get('status', '')
                contract_type = symbol_info.get('contractType', '')
                
                # Only get PERPETUAL contracts with USDT that are TRADING
                if (symbol.endswith('USDT') and 
                    status == 'TRADING' and 
                    contract_type == 'PERPETUAL'):
                    if symbol not in pairs:
                        pairs.append(symbol)
        
        print(f"{LOG_PREFIX} 📊 Fetched {len(pairs)} trading pairs from Binance Futures")
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Error fetching pairs from Binance: {e}")
    
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
    """Normalize symbol to Binance format (BTCUSDT)"""
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
    """Fetch OHLC data from Binance Futures"""
    symbol = normalize_symbol(symbol)
    print(f"{LOG_PREFIX} 📈 Fetching OHLC for {symbol} {timeframe}")
    
    # Binance interval mapping
    tf_map = {
        '1m': '1m',
        '3m': '3m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1h',
        '2h': '2h',
        '4h': '4h',
        '6h': '6h',
        '1d': '1d',
        '1w': '1w',
        '1M': '1M'
    }
    
    timeframe = timeframe.lower()
    if timeframe not in tf_map:
        raise ValueError(f"Timeframe {timeframe} invalid. Choose one of {list(tf_map.keys())}")
    
    interval = tf_map[timeframe]
    
    if not pair_exists(symbol):
        raise ValueError(f"Pair {symbol} not available in Binance Futures.")
    
    retries = 3
    for attempt in range(retries):
        try:
            url = f"{BINANCE_BASE_URL}/fapi/v1/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            resp = _SESSION.get(url, params=params, timeout=(15, 45))
            resp.raise_for_status()
            data = resp.json()
            
            if isinstance(data, list) and len(data) > 0:
                # Binance klines format: [open_time, open, high, low, close, volume, close_time, ...]
                df = pd.DataFrame(data, columns=[
                    'open_time', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                    'taker_buy_quote', 'ignore'
                ])
                
                # Convert to proper types
                df = df.astype({
                    'open': 'float',
                    'high': 'float',
                    'low': 'float',
                    'close': 'float',
                    'volume': 'float'
                })
                
                # Keep only needed columns
                df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']]
                
                try:
                    df['open_time'] = pd.to_datetime(df['open_time'].astype('int64'), unit='ms')
                except Exception as e:
                    print(f"{LOG_PREFIX} ⚠️ Error converting timestamps: {e}")
                
                print(f"{LOG_PREFIX} ✅ Successfully fetched {len(df)} candles for {symbol}")
                return df
                
        except requests.exceptions.Timeout as e:
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"{LOG_PREFIX} ⏱️ Timeout (attempt {attempt + 1}/{retries}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                print(f"{LOG_PREFIX} ❌ All retry attempts exhausted: {e}")
                break
        except requests.exceptions.RequestException as e:
            print(f"{LOG_PREFIX} ❌ Request error: {e}")
            time.sleep(1)
            break
        except Exception as e:
            print(f"{LOG_PREFIX} ❌ Unexpected error: {e}")
            time.sleep(0.5)
            break
    
    raise ValueError(f"No candle data for {symbol} {timeframe} from Binance")

def get_last_price_from_rest(symbol: str):
    """Get last price from Binance Futures"""
    symbol = normalize_symbol(symbol)
    print(f"{LOG_PREFIX} 💰 Fetching last price for {symbol}")
    
    retries = 3
    for attempt in range(retries):
        try:
            url = f"{BINANCE_BASE_URL}/fapi/v1/ticker/price"
            params = {'symbol': symbol}
            
            resp = _SESSION.get(url, params=params, timeout=(8, 15))
            resp.raise_for_status()
            data = resp.json()
            
            if 'price' in data:
                price = float(data['price'])
                print(f"{LOG_PREFIX} ✅ Got price: {price} for {symbol}")
                return price
                
        except requests.exceptions.Timeout as e:
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 1.5
                print(f"{LOG_PREFIX} ⏱️ Timeout (attempt {attempt + 1}/{retries}). Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
                continue
            else:
                print(f"{LOG_PREFIX} ❌ All retry attempts exhausted")
                break
        except requests.exceptions.RequestException as e:
            print(f"{LOG_PREFIX} ❌ Request error: {e}")
            time.sleep(0.5)
            break
        except Exception as e:
            print(f"{LOG_PREFIX} ❌ Unexpected error: {e}")
            time.sleep(0.3)
            break
    
    print(f"{LOG_PREFIX} ❌ Failed to get price for {symbol}")
    return None
