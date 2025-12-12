"""
Exchange Factory - Abstracts data fetching from different exchanges
Supports: Bybit, Binance
"""

LOG_PREFIX = "[exchange_factory]"

def get_exchange_module(exchange: str):
    """
    Get the appropriate exchange data module based on exchange name.
    
    Args:
        exchange: Exchange name ('bybit' or 'binance')
        
    Returns:
        Exchange data module with fetch_ohlc, normalize_symbol, pair_exists, get_all_pairs functions
    """
    exchange = exchange.lower().strip()
    
    if exchange == 'binance':
        print(f"{LOG_PREFIX} 🟡 Using Binance Futures data source")
        import binance_data
        return binance_data
    elif exchange == 'bybit':
        print(f"{LOG_PREFIX} 🟠 Using Bybit Futures data source")
        import bybit_data
        return bybit_data
    else:
        print(f"{LOG_PREFIX} ⚠️ Unknown exchange '{exchange}', defaulting to Bybit")
        import bybit_data
        return bybit_data

def fetch_ohlc(symbol: str, timeframe: str, exchange: str = 'bybit', limit: int = 500):
    """
    Fetch OHLC data from specified exchange.
    
    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        timeframe: Timeframe (e.g., '1h', '4h', '1d')
        exchange: Exchange name ('bybit' or 'binance'), default 'bybit'
        limit: Number of candles to fetch
        
    Returns:
        pandas.DataFrame with OHLC data
    """
    module = get_exchange_module(exchange)
    return module.fetch_ohlc(symbol, timeframe, limit)

def normalize_symbol(symbol: str, exchange: str = 'bybit') -> str:
    """
    Normalize symbol to exchange format.
    
    Args:
        symbol: Trading pair symbol
        exchange: Exchange name ('bybit' or 'binance'), default 'bybit'
        
    Returns:
        Normalized symbol string
    """
    module = get_exchange_module(exchange)
    return module.normalize_symbol(symbol)

def pair_exists(symbol: str, exchange: str = 'bybit') -> bool:
    """
    Check if trading pair exists on the exchange.
    
    Args:
        symbol: Trading pair symbol
        exchange: Exchange name ('bybit' or 'binance'), default 'bybit'
        
    Returns:
        True if pair exists, False otherwise
    """
    module = get_exchange_module(exchange)
    return module.pair_exists(symbol)

def get_all_pairs(exchange: str = 'bybit', force_refresh: bool = False):
    """
    Get all available trading pairs from exchange.
    
    Args:
        exchange: Exchange name ('bybit' or 'binance'), default 'bybit'
        force_refresh: Force refresh from API instead of using cache
        
    Returns:
        List of trading pair symbols
    """
    module = get_exchange_module(exchange)
    return module.get_all_pairs(force_refresh)

def get_last_price_from_rest(symbol: str, exchange: str = 'bybit'):
    """
    Get last price for a symbol from exchange REST API.
    
    Args:
        symbol: Trading pair symbol
        exchange: Exchange name ('bybit' or 'binance'), default 'bybit'
        
    Returns:
        Float price or None if failed
    """
    module = get_exchange_module(exchange)
    return module.get_last_price_from_rest(symbol)
