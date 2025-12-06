import pandas as pd
import ta
import numpy as np
from ws_prices import PRICES
from bybit_data import fetch_ohlc, normalize_symbol
from utils import calculate_rr, format_price_dynamic

# ------------------------------
# Helper: FVG / SMC detection
# ------------------------------
def detect_fvg(df: pd.DataFrame):
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
    return fvg_data

def find_smc_levels(df: pd.DataFrame, fvgs: list, direction: str):
    last_candle = df.iloc[-1]
    relevant_fvg = None
    if fvgs:
        target_type = 'Bullish' if direction == 'long' else 'Bearish'
        filtered = [f for f in fvgs if f['type'] == target_type]
        if filtered:
            relevant_fvg = min(filtered, key=lambda f: abs(f['level'] - last_candle['close']))
    ob_high, ob_low = None, None
    if relevant_fvg:
        ob_idx = relevant_fvg['bar_index'] - 2
        if ob_idx >= 0:
            ob_candle = df.iloc[ob_idx]
            ob_high = ob_candle['high']
            ob_low = ob_candle['low']
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
                               entry_price, current_price):
    score = 0
    reasons = []

    # EMA trend strength
    ema_spread_pct = abs(ema13 - ema21) / (current_price if current_price != 0 else 1) * 100
    if direction == 'long' and ema13 > ema21:
        score += 12; reasons.append("EMA Bullish (13>21)")
    elif direction == 'short' and ema13 < ema21:
        score += 12; reasons.append("EMA Bearish (13<21)")
    if ema_spread_pct > 1:
        score += 8; reasons.append("Spread EMA kuat (>%1)")
    elif ema_spread_pct > 0.5:
        score += 4; reasons.append("Spread EMA moderat")

    # MACD
    macd_diff = macd_line - macd_signal
    if direction == 'long' and macd_diff > 0:
        score += 12; reasons.append("MACD Bullish")
        if macd_diff > 0.05:
            score += 8; reasons.append("Momentum MACD kuat")
    elif direction == 'short' and macd_diff < 0:
        score += 12; reasons.append("MACD Bearish")
        if macd_diff < -0.05:
            score += 8; reasons.append("Momentum MACD kuat")

    # RSI
    if 40 <= rsi <= 60:
        score += 15; reasons.append("RSI netral (40-60)")
    elif 30 <= rsi < 40 or 60 < rsi <= 70:
        score += 8; reasons.append("RSI acceptable (30-40/60-70)")
    else:
        reasons.append("RSI ekstrem (kurang ideal)")

    # SMC (FVG / OB)
    smc_score = 0
    if relevant_fvg:
        smc_score += 8; reasons.append("FVG valid")
    if ob_high or ob_low:
        smc_score += 7; reasons.append("Order Block valid")
    if relevant_fvg:
        dist = abs(entry_price - relevant_fvg['level']) / (current_price if current_price != 0 else 1) * 100
        if dist <= 0.2:
            smc_score += 5; reasons.append("Entry dekat FVG/OB (<0.2%)")
    score += smc_score

    # Stochastic
    stoch_score = 0
    if stoch_k is not None and stoch_d is not None:
        if direction == 'long' and stoch_k > stoch_d:
            stoch_score += 8; reasons.append("Stoch bullish crossover")
            if stoch_k < 20:
                stoch_score += 4; reasons.append("Stoch oversold (supportive)")
            elif stoch_k > 80:
                stoch_score -= 3; reasons.append("Stoch overbought (peringatan)")
        elif direction == 'short' and stoch_k < stoch_d:
            stoch_score += 8; reasons.append("Stoch bearish crossover")
            if stoch_k > 80:
                stoch_score += 4; reasons.append("Stoch overbought (supportive)")
            elif stoch_k < 20:
                stoch_score -= 3; reasons.append("Stoch oversold (peringatan)")
        else:
            if direction == 'long' and stoch_k < 30:
                stoch_score += 3; reasons.append("Stoch low but belum crossover")
            elif direction == 'short' and stoch_k > 70:
                stoch_score += 3; reasons.append("Stoch high but belum crossover")
    stoch_score = max(min(stoch_score, 12), -5)
    score += stoch_score

    # Volume
    vol_score = 0
    if vol_ratio is not None:
        if vol_ratio >= 1.5:
            vol_score += 13; reasons.append(f"Volume tinggi (x{vol_ratio:.2f})")
        elif vol_ratio >= 1.0:
            vol_score += 8; reasons.append(f"Volume di atas rata-rata (x{vol_ratio:.2f})")
        elif vol_ratio >= 0.7:
            vol_score += 3; reasons.append(f"Volume rata-rata (x{vol_ratio:.2f})")
        else:
            vol_score -= 7; reasons.append(f"Volume rendah (x{vol_ratio:.2f})")
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

    return score, label, reasons

# ------------------------------
# Main: generate_trade_plan with optional forced_direction
# ------------------------------
VALID_TFS = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']

def generate_trade_plan(symbol: str, timeframe: str, exchange: str='bybit', forced_direction: str = None, return_dict: bool = False):
    """
    forced_direction: None | 'long' | 'short'
    return_dict: If True, return dict with all data; if False, return formatted string (backward compatible)
    """
    symbol = normalize_symbol(symbol)
    # timeframe validation is expected upstream (discord bot), but keep friendly check
    if timeframe.lower() not in [t.lower() for t in VALID_TFS]:
        raise ValueError(f"Timeframe {timeframe} invalid. Pilih salah satu {VALID_TFS}")

    df = fetch_ohlc(symbol, timeframe)
    if df is None or df.empty or len(df) < 50:
        raise ValueError("Failed to fetch sufficient OHLC data (need min 50 candles)")

    # Indicators
    df['ema13'] = ta.trend.EMAIndicator(df['close'], window=13).ema_indicator()
    df['ema21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
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

    # Auto-side determination (original logic)
    direction = 'neutral'
    if ema13 > ema21 and rsi_val < 70:
        direction = 'long'
    elif ema13 < ema21 and rsi_val > 30:
        direction = 'short'

    # Apply forced direction override if provided and valid
    if forced_direction and forced_direction.lower() in ('long', 'short'):
        direction = forced_direction.lower()

    # FVG/OB detection
    fvgs = detect_fvg(df)
    ob_high, ob_low, relevant_fvg = find_smc_levels(df, fvgs, direction)

    # Prepare entry/stop/tp
    sl_buffer = atr * 0.2

    if direction == 'neutral':
        indicators_insight = (
            f"EMA13: {format_price_dynamic(ema13)} • EMA21: {format_price_dynamic(ema21)}\n"
            f"MACD: {macd_line:.5f} | Signal: {macd_signal:.5f}\n"
            f"RSI: {rsi_val:.2f} | ATR: {atr:.4f}\n"
            f"EMA Crossover tidak jelas atau RSI terlalu ekstrim. Range/Konsolidasi."
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

    if direction == 'long':
        if relevant_fvg and ob_low:
            entry_price = relevant_fvg['low']
            stop = ob_low - sl_buffer
        else:
            entry_price = ema21
            stop = entry_price - atr * 2.0

        risk = abs(entry_price - stop)
        if risk < 1e-8:
            stop = entry_price - atr * 2
            risk = abs(entry_price - stop)

        lookback_high = df.iloc[-50:]['high'].max()
        if lookback_high > (entry_price + risk * 1.5):
            tp2 = lookback_high
        else:
            tp2 = entry_price + risk * 3.0

    else:  # short
        if relevant_fvg and ob_high:
            entry_price = relevant_fvg['high']
            stop = ob_high + sl_buffer
        else:
            entry_price = ema21
            stop = entry_price + atr * 2.0

        risk = abs(entry_price - stop)
        if risk < 1e-8:
            stop = entry_price + atr * 2
            risk = abs(entry_price - stop)

        lookback_low = df.iloc[-50:]['low'].min()
        if lookback_low < (entry_price - risk * 1.5):
            tp2 = lookback_low
        else:
            tp2 = entry_price - risk * 3.0

    tp1 = entry_price + risk * 1.5 if direction == 'long' else entry_price - risk * 1.5
    rr = calculate_rr(entry_price, stop, tp2)

    # Confidence
    confidence, level, reasons = calculate_confidence_score(
        direction, ema13, ema21, macd_line, macd_signal, rsi_val,
        stoch_k, stoch_d, vol_ratio, relevant_fvg, ob_high, ob_low,
        entry_price, current_price
    )

    # Build insight (kept for internal use but may be hidden in embed)
    ob_desc = "Ditemukan" if relevant_fvg else "Tidak ditemukan"
    reason_text = "\n- ".join([""] + reasons)

    indicators_insight = (
        f"EMA13: {format_price_dynamic(ema13)} • EMA21: {format_price_dynamic(ema21)}\n"
        f"MACD: {macd_line:.5f} | Signal: {macd_signal:.5f}\n"
        f"FVG/OB Info: {ob_desc}\n"
        f"STOCH K/D: {format_price_dynamic(stoch_k)}/{format_price_dynamic(stoch_d)} | Vol xEMA20: {format_price_dynamic(vol_ratio) if vol_ratio else '-'}\n"
        f"RSI: {rsi_val:.2f} | ATR: {atr:.4f}\n"
        f"{'EMA Bullish' if direction=='long' else 'EMA Bearish'} • Entry di FVG/OB Retest jika ada.\n"
        f"{reason_text}"
    )

    # Return dict or string based on parameter
    if return_dict:
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
