import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import time
import os
import json

LOG_PREFIX = "[gate_data]"

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
CACHE_FILE = os.path.join(os.path.dirname(__file__), 'gate_pairs_cache.json')
CACHE_EXPIRY = 3600  # 1 hour in seconds

GATE_BASE_URL = 'https://api.gateio.ws/api/v4'  # Gate.io API v4

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
    
    print(f"{LOG_PREFIX} 🌐 Fetching pairs from Gate.io Futures API")
    pairs = []
    
    try:
        # Gate.io API endpoint for USDT perpetual futures contracts
        url = f"{GATE_BASE_URL}/futures/usdt/contracts"
        resp = _SESSION.get(url, timeout=(10, 30))
        resp.raise_for_status()
        data = resp.json()
        
        # Gate.io returns array of contract objects
        for contract in data:
            if isinstance(contract, dict):
                # Gate.io uses format like "BTC_USDT" for perpetual contracts
                name = contract.get('name', '')
                # Only get USDT perpetual contracts (exclude dated futures)
                if name.endswith('_USDT') and contract.get('type') == 'direct':
                    # Convert BTC_USDT to BTCUSDT for consistency
                    symbol = name.replace('_', '')
                    if symbol not in pairs:
                        pairs.append(symbol)
        
        print(f"{LOG_PREFIX} 📊 Fetched {len(pairs)} trading pairs from Gate.io Futures")
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Error fetching pairs from Gate.io: {e}")
    
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
    """Normalize symbol to Gate.io format (BTC_USDT)"""
    s = (symbol or '').strip().upper().replace('-', '').replace('/', '').replace('_', '')
    if not s.endswith('USDT'):
        s = s + 'USDT'
    # Gate.io uses underscore format for API calls
    # Convert BTCUSDT to BTC_USDT
    if s.endswith('USDT') and '_' not in s:
        base = s[:-4]  # Remove USDT
        s = f"{base}_USDT"
    return s

def pair_exists(symbol: str) -> bool:
    symbol_normalized = normalize_symbol(symbol)
    # For comparison with cache, remove underscore
    symbol_no_underscore = symbol_normalized.replace('_', '')
    print(f"{LOG_PREFIX} 🔍 Checking if {symbol_normalized} exists in cache")
    pairs = get_all_pairs()
    if symbol_no_underscore in pairs:
        print(f"{LOG_PREFIX} ✅ {symbol_normalized} found in cache")
        return True
    # Not found in cache, force refresh from API with retry
    print(f"{LOG_PREFIX} 🔄 Refreshing pairs cache for {symbol_normalized}...")
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            pairs = get_all_pairs(force_refresh=True)
            found = symbol_no_underscore in pairs
            print(f"{LOG_PREFIX} ✅ Cache refreshed. {symbol_normalized} found: {found}")
            return found
        except Exception as e:
            if attempt < max_attempts - 1:
                wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                print(f"{LOG_PREFIX} ⚠️ Refresh attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"{LOG_PREFIX} ❌ All refresh attempts failed for {symbol_normalized}")
                return False

def fetch_ohlc(symbol: str, timeframe: str, limit: int = 500):
    """Fetch OHLC data from Gate.io Futures"""
    symbol_normalized = normalize_symbol(symbol)
    print(f"{LOG_PREFIX} 📈 Fetching OHLC for {symbol_normalized} {timeframe}")
    
    # Gate.io interval mapping
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
        '12h': '12h',
        '1d': '1d',
        '1w': '1w'
    }
    
    interval = tf_map.get(timeframe.lower())
    if not interval:
        print(f"{LOG_PREFIX} ❌ Invalid timeframe: {timeframe}")
        raise ValueError(f"Invalid timeframe {timeframe}")
    
    # Adjust limit for longer timeframes
    if timeframe.lower() == '1d':
        limit = min(limit, 365)  # Max 1 year for daily candles
        print(f"{LOG_PREFIX} ⚙️ Adjusted limit to {limit} for {timeframe} timeframe")
    elif timeframe.lower() in ['1w']:
        limit = min(limit, 200)  # Max 200 candles for weekly
        print(f"{LOG_PREFIX} ⚙️ Adjusted limit to {limit} for {timeframe} timeframe")
    
    # Gate.io API endpoint for candlesticks
    url = f"{GATE_BASE_URL}/futures/usdt/candlesticks"
    params = {
        'contract': symbol_normalized,
        'interval': interval,
        'limit': limit
    }
    
    print(f"{LOG_PREFIX} 🔍 DEBUG - Request parameters:")
    print(f"{LOG_PREFIX}   - contract: {symbol_normalized}")
    print(f"{LOG_PREFIX}   - interval: {interval}")
    print(f"{LOG_PREFIX}   - limit: {limit}")
    
    try:
        resp = _SESSION.get(url, params=params, timeout=(10, 30))
        
        # Print response before raising error
        print(f"{LOG_PREFIX} 📥 Response status: {resp.status_code}")
        print(f"{LOG_PREFIX} 📥 Response body: {resp.text[:500]}")  # First 500 chars
        
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            print(f"{LOG_PREFIX} ⚠️ No candle data returned for {symbol_normalized}")
            raise Exception(f"No candle data for {symbol_normalized}")
        
        # Gate.io returns: {"t": timestamp, "v": volume, "c": close, "h": high, "l": low, "o": open}
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Rename columns to standard format
        df = df.rename(columns={
            't': 'timestamp',
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume'
        })
        
        # Convert data types
        df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df['open'] = pd.to_numeric(df['open'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        
        # Convert timestamp from seconds to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # Sort by timestamp ascending (oldest first)
        df = df.sort_values('timestamp', ascending=True).reset_index(drop=True)
        
        print(f"{LOG_PREFIX} ✅ Fetched {len(df)} candles for {symbol_normalized} {timeframe}")
        return df
        
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Error fetching OHLC data: {e}")
        raise

def get_last_price_from_rest(symbol: str):
    """Get last price for a symbol from Gate.io REST API"""
    symbol_normalized = normalize_symbol(symbol)
    
    print(f"{LOG_PREFIX} 💰 Fetching last price for {symbol_normalized}")
    
    try:
        # Gate.io API endpoint for ticker
        url = f"{GATE_BASE_URL}/futures/usdt/contracts/{symbol_normalized}"
        resp = _SESSION.get(url, timeout=(10, 30))
        resp.raise_for_status()
        data = resp.json()
        
        # Gate.io returns contract info with last price
        last_price = float(data.get('last_price', 0))
        print(f"{LOG_PREFIX} ✅ Last price for {symbol_normalized}: {last_price}")
        return last_price
            
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Error fetching last price: {e}")
        return None
