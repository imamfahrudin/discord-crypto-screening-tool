import pandas as pd
import ta
import numpy as np
from ws_prices import PRICES
from exchange_factory import fetch_ohlc, normalize_symbol
from utils import calculate_rr, format_price_dynamic

LOG_PREFIX = "[signal_logic]"

# ------------------------------
# Helper: Divergence Detection
# ------------------------------
def detect_divergence(df: pd.DataFrame, lookback: int = 14):
    """Detect bullish/bearish divergences in RSI and MACD"""
    print(f"{LOG_PREFIX} 🔍 Detecting divergences in last {lookback} candles")
    
    if len(df) < lookback + 5:
        return {'rsi_bull': False, 'rsi_bear': False, 'macd_bull': False, 'macd_bear': False}
    
    recent = df.iloc[-lookback:]
    
    # Find pivots in price
    price_lows = []
    price_highs = []
    
    for i in range(2, len(recent) - 2):
        # Local low
        if (recent.iloc[i]['low'] < recent.iloc[i-1]['low'] and 
            recent.iloc[i]['low'] < recent.iloc[i-2]['low'] and
            recent.iloc[i]['low'] < recent.iloc[i+1]['low'] and 
            recent.iloc[i]['low'] < recent.iloc[i+2]['low']):
            price_lows.append({'idx': i, 'price': recent.iloc[i]['low'], 'rsi': recent.iloc[i]['rsi'], 'macd': recent.iloc[i]['macd_line']})
        
        # Local high
        if (recent.iloc[i]['high'] > recent.iloc[i-1]['high'] and 
            recent.iloc[i]['high'] > recent.iloc[i-2]['high'] and
            recent.iloc[i]['high'] > recent.iloc[i+1]['high'] and 
            recent.iloc[i]['high'] > recent.iloc[i+2]['high']):
            price_highs.append({'idx': i, 'price': recent.iloc[i]['high'], 'rsi': recent.iloc[i]['rsi'], 'macd': recent.iloc[i]['macd_line']})
    
    rsi_bull_div = False
    rsi_bear_div = False
    macd_bull_div = False
    macd_bear_div = False
    
    # Bullish divergence: price lower low, indicator higher low
    if len(price_lows) >= 2:
        last_low = price_lows[-1]
        prev_low = price_lows[-2]
        if last_low['price'] < prev_low['price']:
            if last_low['rsi'] > prev_low['rsi']:
                rsi_bull_div = True
                print(f"{LOG_PREFIX} ✅ Bullish RSI divergence detected")
            if last_low['macd'] > prev_low['macd']:
                macd_bull_div = True
                print(f"{LOG_PREFIX} ✅ Bullish MACD divergence detected")
    
    # Bearish divergence: price higher high, indicator lower high
    if len(price_highs) >= 2:
        last_high = price_highs[-1]
        prev_high = price_highs[-2]
        if last_high['price'] > prev_high['price']:
            if last_high['rsi'] < prev_high['rsi']:
                rsi_bear_div = True
                print(f"{LOG_PREFIX} ✅ Bearish RSI divergence detected")
            if last_high['macd'] < prev_high['macd']:
                macd_bear_div = True
                print(f"{LOG_PREFIX} ✅ Bearish MACD divergence detected")
    
    return {
        'rsi_bull': rsi_bull_div,
        'rsi_bear': rsi_bear_div,
        'macd_bull': macd_bull_div,
        'macd_bear': macd_bear_div
    }

# ------------------------------
# Helper: Find Swing Highs/Lows
# ------------------------------
def find_swing_points(df: pd.DataFrame, direction: str, lookback: int = 20):
    """Find recent swing high/low for better stop loss placement"""
    print(f"{LOG_PREFIX} 🔍 Finding swing points for {direction} direction")
    
    if len(df) < lookback:
        return None
    
    recent = df.iloc[-lookback:]
    
    if direction == 'long':
        # Find lowest low in recent candles
        swing_low = recent['low'].min()
        print(f"{LOG_PREFIX} 📍 Swing low found: {swing_low:.6f}")
        return swing_low
    else:
        # Find highest high in recent candles
        swing_high = recent['high'].max()
        print(f"{LOG_PREFIX} 📍 Swing high found: {swing_high:.6f}")
        return swing_high

# ------------------------------
# Helper: Calculate Trend Strength
# ------------------------------
def calculate_trend_strength(df: pd.DataFrame, ema_short: int = 13, ema_long: int = 21):
    """Calculate trend strength using EMA slope and ADX-like metric"""
    print(f"{LOG_PREFIX} 📊 Calculating trend strength")
    
    if len(df) < 20:
        return {'strength': 0, 'quality': 'WEAK'}
    
    recent = df.iloc[-20:]
    ema_short_col = f'ema{ema_short}'
    ema_long_col = f'ema{ema_long}'
    
    # Calculate EMA slopes (rate of change)
    ema_short_slope = (recent[ema_short_col].iloc[-1] - recent[ema_short_col].iloc[-5]) / recent[ema_short_col].iloc[-5]
    ema_long_slope = (recent[ema_long_col].iloc[-1] - recent[ema_long_col].iloc[-5]) / recent[ema_long_col].iloc[-5]
    
    # Check if EMAs are aligned and trending
    ema_separation = abs(recent[ema_short_col].iloc[-1] - recent[ema_long_col].iloc[-1]) / recent['close'].iloc[-1]
    
    # Count consecutive candles following trend
    consecutive_trend = 0
    for i in range(len(recent) - 1, 0, -1):
        if recent[ema_short_col].iloc[i] > recent[ema_long_col].iloc[i]:
            if recent['close'].iloc[i] > recent[ema_short_col].iloc[i]:
                consecutive_trend += 1
            else:
                break
        elif recent[ema_short_col].iloc[i] < recent[ema_long_col].iloc[i]:
            if recent['close'].iloc[i] < recent[ema_short_col].iloc[i]:
                consecutive_trend += 1
            else:
                break
        else:
            break
    
    # Combine factors
    strength_score = 0
    strength_score += min(abs(ema_short_slope) * 1000, 30)  # Max 30 points
    strength_score += min(abs(ema_long_slope) * 1000, 20)   # Max 20 points
    strength_score += min(ema_separation * 500, 25)         # Max 25 points
    strength_score += min(consecutive_trend * 2, 25)        # Max 25 points
    
    quality = 'WEAK'
    if strength_score >= 70:
        quality = 'VERY STRONG'
    elif strength_score >= 50:
        quality = 'STRONG'
    elif strength_score >= 30:
        quality = 'MODERATE'
    
    print(f"{LOG_PREFIX} ✅ Trend strength: {strength_score:.1f}% ({quality})")
    return {'strength': strength_score, 'quality': quality}

# ------------------------------
# Helper: FVG / SMC detection
# ------------------------------
def detect_fvg(df: pd.DataFrame):
    print(f"{LOG_PREFIX} 🔍 Detecting FVGs in {len(df)} candles")
    fvg_data = []
    for i in range(2, len(df)):
        c1 = df.iloc[i-2]
        c3 = df.iloc[i]
        # Bullish FVG
        if c3['low'] > c1['high']:
            fvg_level = (c3['low'] + c1['high']) / 2
            fvg_data.append({
                'type': 'Bullish',
                'high': c3['low'],
                'low': c1['high'],
                'level': fvg_level,
                'bar_index': i
            })
        # Bearish FVG
        elif c3['high'] < c1['low']:
            fvg_level = (c1['low'] + c3['high']) / 2
            fvg_data.append({
                'type': 'Bearish',
                'high': c1['low'],
                'low': c3['high'],
                'level': fvg_level,
                'bar_index': i
            })
    print(f"{LOG_PREFIX} ✅ Detected {len(fvg_data)} FVGs")
    return fvg_data

def find_smc_levels(df: pd.DataFrame, fvgs: list, direction: str):
    print(f"{LOG_PREFIX} 🔍 Finding SMC levels for direction: {direction}")
    last_candle = df.iloc[-1]
    relevant_fvg = None
    if fvgs:
        target_type = 'Bullish' if direction == 'long' else 'Bearish'
        filtered = [f for f in fvgs if f['type'] == target_type]
        if filtered:
            relevant_fvg = min(filtered, key=lambda f: abs(f['level'] - last_candle['close']))
            print(f"{LOG_PREFIX} ✅ Found relevant FVG: {relevant_fvg['type']} at level {relevant_fvg['level']:.6f}")
        else:
            print(f"{LOG_PREFIX} ⚠️ No {target_type} FVGs found")
    else:
        print(f"{LOG_PREFIX} ⚠️ No FVGs available for SMC analysis")
    
    ob_high, ob_low = None, None
    if relevant_fvg:
        ob_idx = relevant_fvg['bar_index'] - 2
        if ob_idx >= 0:
            ob_candle = df.iloc[ob_idx]
            ob_high = ob_candle['high']
            ob_low = ob_candle['low']
            print(f"{LOG_PREFIX} 📊 Order Block: high={ob_high:.6f}, low={ob_low:.6f}")
        else:
            print(f"{LOG_PREFIX} ⚠️ Order Block index out of range: {ob_idx}")
    
    print(f"{LOG_PREFIX} ✅ SMC analysis complete")
    return ob_high, ob_low, relevant_fvg

# ------------------------------
# Confidence scoring
# ------------------------------
def calculate_confidence_score(direction,
                               ema13, ema21,
                               macd_line, macd_signal,
                               rsi,
                               stoch_k, stoch_d,
                               vol_ratio,
                               relevant_fvg, ob_high, ob_low,
                               entry_price, current_price,
                               divergences=None,
                               trend_strength=None,
                               ema_short=13, ema_long=21):
    print(f"{LOG_PREFIX} 📊 Calculating confidence score for {direction} direction")
    score = 0
    reasons = []
    
    # Initialize defaults
    if divergences is None:
        divergences = {'rsi_bull': False, 'rsi_bear': False, 'macd_bull': False, 'macd_bear': False}
    if trend_strength is None:
        trend_strength = {'strength': 0, 'quality': 'WEAK'}

    # EMA trend strength (ADJUSTED - reduced weight, trend_strength is now primary)
    ema_spread_pct = abs(ema13 - ema21) / (current_price if current_price != 0 else 1) * 100
    if direction == 'long' and ema13 > ema21:
        score += 8; reasons.append(f"📈 Trend bullish dikonfirmasi EMA{ema_short} di atas EMA{ema_long} (+8)")
    elif direction == 'short' and ema13 < ema21:
        score += 8; reasons.append(f"📉 Trend bearish dikonfirmasi EMA{ema_short} di bawah EMA{ema_long} (+8)")
    elif direction == 'long' and ema13 <= ema21:
        score -= 5; reasons.append(f"⚠️ EMA{ema_short} masih di bawah EMA{ema_long} - counter-trend, risiko sangat tinggi (-5)")
    elif direction == 'short' and ema13 >= ema21:
        score -= 5; reasons.append(f"⚠️ EMA{ema_short} masih di atas EMA{ema_long} - counter-trend, risiko sangat tinggi (-5)")
    
    if ema_spread_pct > 1:
        score += 6; reasons.append(f"🚀 Momentum trend sangat kuat dengan spread {ema_spread_pct:.2f}% (+6)")
    elif ema_spread_pct > 0.5:
        score += 3; reasons.append(f"⚡ Momentum trend moderat dengan spread {ema_spread_pct:.2f}% (+3)")
    else:
        reasons.append(f"📍 Spread EMA lemah {ema_spread_pct:.2f}% - market consolidation atau trend lemah (0)")

    # MACD (ENHANCED - with histogram momentum)
    macd_diff = macd_line - macd_signal
    macd_momentum_score = 0
    
    if direction == 'long' and macd_diff > 0:
        macd_momentum_score += 10; reasons.append(f"📊 MACD histogram positif - momentum bullish aktif (+10)")
        if macd_diff > 0.05:
            macd_momentum_score += 7; reasons.append(f"💪 MACD histogram sangat kuat ({macd_diff:.4f}) - explosive momentum (+7)")
        elif macd_diff > 0.01:
            macd_momentum_score += 3; reasons.append(f"📈 MACD histogram moderat ({macd_diff:.4f}) - momentum building (+3)")
    elif direction == 'short' and macd_diff < 0:
        macd_momentum_score += 10; reasons.append(f"📊 MACD histogram negatif - momentum bearish aktif (+10)")
        if macd_diff < -0.05:
            macd_momentum_score += 7; reasons.append(f"💪 MACD histogram sangat kuat ({macd_diff:.4f}) - explosive momentum (+7)")
        elif macd_diff < -0.01:
            macd_momentum_score += 3; reasons.append(f"📉 MACD histogram moderat ({macd_diff:.4f}) - momentum building (+3)")
    elif direction == 'long' and macd_diff <= 0:
        macd_momentum_score -= 8; reasons.append(f"🔴 MACD masih negatif ({macd_diff:.4f}) - counter-trend, tunggu crossover (-8)")
    elif direction == 'short' and macd_diff >= 0:
        macd_momentum_score -= 8; reasons.append(f"🔴 MACD masih positif ({macd_diff:.4f}) - counter-trend, tunggu crossover (-8)")
    
    score += macd_momentum_score

    # RSI (IMPROVED - context-aware scoring)
    rsi_score = 0
    if 40 <= rsi <= 60:
        rsi_score += 12; reasons.append(f"✅ RSI netral di {rsi:.1f} - zona ideal dengan ruang gerak optimal (+12)")
    elif direction == 'long' and 30 <= rsi < 40:
        rsi_score += 10; reasons.append(f"💎 RSI di {rsi:.1f} - zona oversold ringan, good long entry (+10)")
    elif direction == 'short' and 60 < rsi <= 70:
        rsi_score += 10; reasons.append(f"💎 RSI di {rsi:.1f} - zona overbought ringan, good short entry (+10)")
    elif direction == 'long' and rsi > 70:
        rsi_score -= 10; reasons.append(f"🔴 RSI overbought di {rsi:.1f} - risiko pullback sangat tinggi untuk long (-10)")
    elif direction == 'short' and rsi < 30:
        rsi_score -= 10; reasons.append(f"🔴 RSI oversold di {rsi:.1f} - risiko bounce sangat tinggi untuk short (-10)")
    elif 30 <= rsi < 40 or 60 < rsi <= 70:
        rsi_score += 5; reasons.append(f"⚠️ RSI di {rsi:.1f} - masih acceptable tapi ruang terbatas (+5)")
    else:
        if rsi < 30:
            reasons.append(f"⚠️ RSI oversold ekstrem di {rsi:.1f} - wait for bounce confirmation (0)")
        else:
            reasons.append(f"⚠️ RSI overbought ekstrem di {rsi:.1f} - wait for rejection confirmation (0)")
    
    score += rsi_score

    # SMC (FVG / OB)
    smc_score = 0
    if relevant_fvg:
        fvg_type = relevant_fvg.get('type', 'Unknown')
        smc_score += 8; reasons.append(f"🎯 {fvg_type} FVG terdeteksi - area imbalance valid untuk entry (+8)")
    if ob_high or ob_low:
        smc_score += 7; reasons.append(f"🧱 Order Block teridentifikasi - zona institutional support/resistance (+7)")
    if relevant_fvg:
        dist = abs(entry_price - relevant_fvg['level']) / (current_price if current_price != 0 else 1) * 100
        if dist <= 0.2:
            smc_score += 5; reasons.append(f"🎪 Entry sangat dekat dengan FVG level ({dist:.2f}%) - high probability setup (+5)")
        elif dist <= 0.5:
            reasons.append(f"📍 Entry cukup dekat dengan FVG level ({dist:.2f}%) - acceptable entry zone")
        else:
            reasons.append(f"⚠️ Entry jauh dari FVG level ({dist:.2f}%) - tunggu retest untuk entry lebih baik")
    
    if not relevant_fvg and not (ob_high or ob_low):
        reasons.append(f"📭 Tidak ada struktur SMC terdeteksi - trading berdasarkan indikator saja (0)")
    
    score += smc_score

    # Stochastic
    stoch_score = 0
    if stoch_k is not None and stoch_d is not None:
        if direction == 'long' and stoch_k > stoch_d:
            stoch_score += 8; reasons.append(f"🔄 Stochastic bullish crossover terdeteksi (K={stoch_k:.1f} > D={stoch_d:.1f}) (+8)")
            if stoch_k < 20:
                stoch_score += 4; reasons.append(f"💎 Crossover terjadi di zona oversold ({stoch_k:.1f}) - strong buy signal (+4)")
            elif stoch_k > 80:
                stoch_score -= 3; reasons.append(f"⚠️ Crossover di zona overbought ({stoch_k:.1f}) - risiko pullback (-3)")
            elif 20 <= stoch_k <= 80:
                reasons.append(f"✓ Crossover di zona netral ({stoch_k:.1f}) - timing acceptable")
        elif direction == 'short' and stoch_k < stoch_d:
            stoch_score += 8; reasons.append(f"🔄 Stochastic bearish crossover terdeteksi (K={stoch_k:.1f} < D={stoch_d:.1f}) (+8)")
            if stoch_k > 80:
                stoch_score += 4; reasons.append(f"💎 Crossover terjadi di zona overbought ({stoch_k:.1f}) - strong sell signal (+4)")
            elif stoch_k < 20:
                stoch_score -= 3; reasons.append(f"⚠️ Crossover di zona oversold ({stoch_k:.1f}) - risiko bounce (-3)")
            elif 20 <= stoch_k <= 80:
                reasons.append(f"✓ Crossover di zona netral ({stoch_k:.1f}) - timing acceptable")
        else:
            if direction == 'long' and stoch_k < 30:
                stoch_score += 3; reasons.append(f"🔵 Stochastic di zona oversold ({stoch_k:.1f}) menunggu crossover bullish (+3)")
            elif direction == 'short' and stoch_k > 70:
                stoch_score += 3; reasons.append(f"🔵 Stochastic di zona overbought ({stoch_k:.1f}) menunggu crossover bearish (+3)")
            elif direction == 'long' and stoch_k < stoch_d:
                reasons.append(f"⚠️ Stochastic bearish (K={stoch_k:.1f} < D={stoch_d:.1f}) - bertentangan dengan signal long (0)")
            elif direction == 'short' and stoch_k > stoch_d:
                reasons.append(f"⚠️ Stochastic bullish (K={stoch_k:.1f} > D={stoch_d:.1f}) - bertentangan dengan signal short (0)")
            else:
                reasons.append(f"📊 Stochastic di zona netral (K={stoch_k:.1f}) - tidak ada signal kuat (0)")
    else:
        reasons.append(f"❌ Data Stochastic tidak tersedia - analisis momentum terbatas (0)")
    
    stoch_score = max(min(stoch_score, 12), -5)
    score += stoch_score

    # Volume
    vol_score = 0
    if vol_ratio is not None:
        if vol_ratio >= 1.5:
            vol_score += 13; reasons.append(f"📊 Volume sangat tinggi {vol_ratio:.2f}x rata-rata - strong institutional interest (+13)")
        elif vol_ratio >= 1.0:
            vol_score += 8; reasons.append(f"📈 Volume di atas rata-rata {vol_ratio:.2f}x - healthy market participation (+8)")
        elif vol_ratio >= 0.7:
            vol_score += 3; reasons.append(f"📉 Volume normal {vol_ratio:.2f}x - acceptable trading activity (+3)")
        else:
            vol_score -= 7; reasons.append(f"⚠️ Volume rendah {vol_ratio:.2f}x - low liquidity, risiko slippage tinggi (-7)")
    else:
        reasons.append(f"❌ Data volume tidak tersedia - tidak bisa konfirmasi kekuatan move (0)")
    score += vol_score

    # Final clamp & label
    score = int(round(max(0, min(score, 100))))
    if score >= 80:
        label = "HIGH 🔥"
    elif score >= 60:
        label = "MEDIUM ⚡"
    elif score >= 40:
        label = "LOW 🌫️"
    else:
        label = "VERY LOW 🚨"

    print(f"{LOG_PREFIX} ✅ Confidence score calculated: {score}% {label}")
    print(f"{LOG_PREFIX} 📋 Reasons: {', '.join(reasons)}")
    return score, label, reasons

# ------------------------------
# Main: generate_trade_plan with optional forced_direction
# ------------------------------
VALID_TFS = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']

def generate_trade_plan(symbol: str, timeframe: str, exchange: str='bybit', forced_direction: str = None, return_dict: bool = False, ema_short: int = 13, ema_long: int = 21):
    """
    forced_direction: None | 'long' | 'short'
    return_dict: If True, return dict with all data; if False, return formatted string (backward compatible)
    ema_short: Short EMA period (default 13)
    ema_long: Long EMA period (default 21)
    """
    print(f"{LOG_PREFIX} 🚀 Starting trade plan generation for {symbol} {timeframe} (forced: {forced_direction}, ema: {ema_short}/{ema_long})")
    
    symbol = normalize_symbol(symbol, exchange)
    # timeframe validation is expected upstream (discord bot), but keep friendly check
    if timeframe.lower() not in [t.lower() for t in VALID_TFS]:
        print(f"{LOG_PREFIX} ⚠️ Invalid timeframe: {timeframe}")
        raise ValueError(f"Timeframe {timeframe} tidak valid. Pilih salah satu {VALID_TFS}")

    print(f"{LOG_PREFIX} 📊 Fetching OHLC data for {symbol} from {exchange.upper()}")
    df = fetch_ohlc(symbol, timeframe, exchange)
    if df is None or df.empty or len(df) < 50:
        print(f"{LOG_PREFIX} ❌ Insufficient OHLC data: {len(df) if df is not None else 0} candles")
        raise ValueError("Gagal mengambil data OHLC yang cukup (perlu minimal 50 candle)")

    print(f"{LOG_PREFIX} 📈 Calculating technical indicators with EMA periods: {ema_short}/{ema_long}")
    # Indicators
    df['ema13'] = ta.trend.EMAIndicator(df['close'], window=ema_short).ema_indicator()
    df['ema21'] = ta.trend.EMAIndicator(df['close'], window=ema_long).ema_indicator()
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()

    macd_data = ta.trend.MACD(df['close'])
    df['macd_line'] = macd_data.macd()
    df['macd_signal'] = macd_data.macd_signal()

    # Stochastic (14,3)
    try:
        stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'], window=14, smooth_window=3)
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
    except Exception:
        df['stoch_k'] = np.nan
        df['stoch_d'] = np.nan

    # Volume EMA20
    if 'volume' not in df.columns:
        df['volume'] = 0.0
    df['vol_ema20'] = df['volume'].ewm(span=20, adjust=False).mean()

    last = df.iloc[-1]
    sym = symbol.upper()
    ws_price = PRICES.get(sym)
    current_price = float(ws_price) if ws_price is not None else float(last['close'])
    print(f"{LOG_PREFIX} 💰 Current price: {current_price} (ws: {ws_price is not None})")

    # Values
    ema13 = float(last['ema13'])
    ema21 = float(last['ema21'])
    atr = float(last['atr']) if not pd.isna(last['atr']) and float(last['atr']) > 0 else abs(current_price * 0.002)
    rsi_val = float(last['rsi'])
    macd_line = float(last['macd_line'])
    macd_signal = float(last['macd_signal'])
    stoch_k = float(last['stoch_k']) if not pd.isna(last.get('stoch_k', np.nan)) else None
    stoch_d = float(last['stoch_d']) if not pd.isna(last.get('stoch_d', np.nan)) else None
    vol_ema20 = float(last['vol_ema20']) if not pd.isna(last['vol_ema20']) and last['vol_ema20'] > 0 else None
    current_vol = float(last['volume']) if 'volume' in last and not pd.isna(last['volume']) else None
    vol_ratio = None
    if vol_ema20 and current_vol is not None and vol_ema20 > 0:
        vol_ratio = current_vol / vol_ema20
    
    # Calculate new metrics
    print(f"{LOG_PREFIX} 🔬 Analyzing market structure...")
    divergences = detect_divergence(df, lookback=14)
    trend_strength = calculate_trend_strength(df, ema_short, ema_long)

    # Auto-side determination (IMPROVED - with trend strength filter)
    direction = 'neutral'
    if ema13 > ema21 and rsi_val < 70:
        direction = 'long'
    elif ema13 < ema21 and rsi_val > 30:
        direction = 'short'
    
    # Filter weak trends unless there's divergence
    if direction != 'neutral' and trend_strength['quality'] == 'WEAK':
        has_divergence = (direction == 'long' and (divergences['rsi_bull'] or divergences['macd_bull'])) or \
                        (direction == 'short' and (divergences['rsi_bear'] or divergences['macd_bear']))
        if not has_divergence:
            print(f"{LOG_PREFIX} ⚠️ Trend too weak ({trend_strength['quality']}) and no divergence - setting to neutral")
            direction = 'neutral'

    print(f"{LOG_PREFIX} 📊 Auto-determined direction: {direction} (EMA{ema_short}: {ema13:.6f}, EMA{ema_long}: {ema21:.6f}, RSI: {rsi_val:.2f})")

    # Apply forced direction override if provided and valid
    if forced_direction and forced_direction.lower() in ('long', 'short'):
        direction = forced_direction.lower()
        print(f"{LOG_PREFIX} 🔄 Applied forced direction: {direction}")

    # FVG/OB detection
    fvgs = detect_fvg(df)
    ob_high, ob_low, relevant_fvg = find_smc_levels(df, fvgs, direction)

    # Prepare entry/stop/tp
    sl_buffer = atr * 0.2

    if direction == 'neutral':
        indicators_insight = (
            f"**📊 Indikator Teknis:**\n"
            f"- EMA{ema_short}: {format_price_dynamic(ema13)} | EMA{ema_long}: {format_price_dynamic(ema21)}\n"
            f"- MACD: {macd_line:.2f} | Signal: {macd_signal:.2f}\n"
            f"- RSI: {rsi_val:.2f} | ATR: {atr:.2f}\n\n"
            f"**📝 Kesimpulan:**\n"
            f"- EMA crossover tidak jelas atau RSI terlalu ekstrim.\n"
            f"- Market dalam fase range/konsolidasi."
        )
        
        if return_dict:
            return {
                'direction': 'neutral',
                'df': df,
                'ema13_series': df['ema13'],
                'ema21_series': df['ema21'],
                'current_price': current_price,
                'insight': indicators_insight,
                'exchange': exchange.upper(),
                'rsi': rsi_val,
                'macd_line': macd_line,
                'macd_signal': macd_signal
            }
        
        return (
            f"DIRECTION: **NETRAL**\n"
            f"INSIGHT_START\n{indicators_insight}\nINSIGHT_END"
        )

    # Get swing points for better stop placement
    swing_point = find_swing_points(df, direction, lookback=20)
    
    if direction == 'long':
        # Entry logic: prefer FVG retest, otherwise pullback to EMA21
        if relevant_fvg and ob_low:
            entry_price = relevant_fvg['low']
        else:
            # Enter on pullback to EMA21 for better entry
            entry_price = ema21 if current_price > ema21 * 1.005 else current_price
        
        # Stop loss: use swing low or OB, whichever is lower
        if swing_point:
            stop = swing_point - sl_buffer
        elif ob_low:
            stop = ob_low - sl_buffer
        else:
            stop = entry_price - atr * 2.0
        
        # Ensure stop is below entry
        if stop >= entry_price:
            stop = entry_price - max(atr * 1.5, entry_price * 0.01)

        risk = abs(entry_price - stop)
        if risk < 1e-8:
            stop = entry_price - atr * 2
            risk = abs(entry_price - stop)

        # TP calculation: use recent swing high if available
        lookback_high = df.iloc[-50:]['high'].max()
        if lookback_high > (entry_price + risk * 1.5):
            tp2 = lookback_high * 0.99  # Slightly below swing high
        else:
            # Dynamic R:R based on trend strength
            rr_multiplier = 3.0 if trend_strength['quality'] in ['STRONG', 'VERY STRONG'] else 2.5
            tp2 = entry_price + risk * rr_multiplier

    else:  # short
        # Entry logic: prefer FVG retest, otherwise pullback to EMA21
        if relevant_fvg and ob_high:
            entry_price = relevant_fvg['high']
        else:
            # Enter on pullback to EMA21 for better entry
            entry_price = ema21 if current_price < ema21 * 0.995 else current_price
        
        # Stop loss: use swing high or OB, whichever is higher
        if swing_point:
            stop = swing_point + sl_buffer
        elif ob_high:
            stop = ob_high + sl_buffer
        else:
            stop = entry_price + atr * 2.0
        
        # Ensure stop is above entry
        if stop <= entry_price:
            stop = entry_price + max(atr * 1.5, entry_price * 0.01)

        risk = abs(entry_price - stop)
        if risk < 1e-8:
            stop = entry_price + atr * 2
            risk = abs(entry_price - stop)

        # TP calculation: use recent swing low if available
        lookback_low = df.iloc[-50:]['low'].min()
        if lookback_low < (entry_price - risk * 1.5):
            tp2 = lookback_low * 1.01  # Slightly above swing low
        else:
            # Dynamic R:R based on trend strength
            rr_multiplier = 3.0 if trend_strength['quality'] in ['STRONG', 'VERY STRONG'] else 2.5
            tp2 = entry_price - risk * rr_multiplier

    tp1 = entry_price + risk * 1.5 if direction == 'long' else entry_price - risk * 1.5
    rr = calculate_rr(entry_price, stop, tp2)

    print(f"{LOG_PREFIX} 📊 Entry/Exit calculated - Entry: {entry_price:.6f}, Stop: {stop:.6f}, TP1: {tp1:.6f}, TP2: {tp2:.6f}, RR: {rr:.2f}")

    # Confidence (UPDATED - with new parameters)
    confidence, level, reasons = calculate_confidence_score(
        direction, ema13, ema21, macd_line, macd_signal, rsi_val,
        stoch_k, stoch_d, vol_ratio, relevant_fvg, ob_high, ob_low,
        entry_price, current_price, divergences, trend_strength, ema_short, ema_long
    )

    # Build insight (kept for internal use but may be hidden in embed)
    ob_desc = "Ditemukan" if relevant_fvg else "Tidak ditemukan"
    reason_text = "\n".join(f"- {reason}" for reason in reasons)

    indicators_insight = (
        f"**📊 Indikator Teknis:**\n"
        f"- EMA{ema_short}: {format_price_dynamic(ema13)} | EMA{ema_long}: {format_price_dynamic(ema21)}\n"
        f"- MACD: {macd_line:.2f} | Signal: {macd_signal:.2f}\n"
        f"- RSI: {rsi_val:.2f} | ATR: {atr:.2f}\n"
        f"- Stochastic K/D: {format_price_dynamic(stoch_k)} / {format_price_dynamic(stoch_d)}\n"
        f"- Volume Ratio: {format_price_dynamic(vol_ratio) if vol_ratio else '-'}x\n\n"
        f"**🔍 Analisis FVG/OB:**\n"
        f"- Status: {ob_desc}\n"
        f"- {'Bullish' if direction=='long' else 'Bearish'} setup • Entry di retest FVG/OB jika ada.\n\n"
        f"**💡 Faktor Confidence ({confidence}%):**\n"
        f"{reason_text}"
    )

    # Truncate insight to fit Discord embed field limit (1024 chars max)
    max_length = 1000
    if len(indicators_insight) > max_length:
        indicators_insight = indicators_insight[:max_length] + "\n\n*... (truncated for length)*"

    # Return dict or string based on parameter
    if return_dict:
        print(f"{LOG_PREFIX} ✅ Returning dict format for {direction.upper()} signal")
        return {
            'direction': direction.upper(),
            'entry': entry_price,
            'stop_loss': stop,
            'tp1': tp1,
            'tp2': tp2,
            'rr': rr,
            'confidence': confidence,
            'confidence_level': level,
            'confidence_reasons': reasons,
            'current_price': current_price,
            'exchange': exchange.upper(),
            'df': df,
            'ema_short': ema_short,
            'ema_long': ema_long,
            'ema13_series': df['ema13'],
            'ema21_series': df['ema21'],
            'fvg_zones': fvgs,
            'ob_high': ob_high,
            'ob_low': ob_low,
            'relevant_fvg': relevant_fvg,
            'insight': indicators_insight,
            'rsi': rsi_val,
            'macd_line': macd_line,
            'macd_signal': macd_signal,
            'atr': atr
        }
    
    # Final return string (same format as before - backward compatible)
    print(f"{LOG_PREFIX} ✅ Returning string format for {direction.upper()} signal")
    return (
        f"DIRECTION: **{direction.upper()}**\n"
        f"ENTRY: {entry_price}\n"
        f"SL: {stop}\n"
        f"TP1: {tp1}\n"
        f"TP2: {tp2}\n"
        f"RR: {rr}\n"
        f"CONFIDENCE: {confidence}% {level}\n"
        f"LAST_PRICE: {current_price}\n"
        f"EXCHANGE: {exchange.upper()}\n"
        f"INSIGHT_START\n{indicators_insight}\nINSIGHT_END"
    )
