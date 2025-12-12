import pandas as pd
import ta
import numpy as np
from ws_prices import PRICES
from exchange_factory import fetch_ohlc, normalize_symbol
from utils import calculate_rr, format_price_dynamic

LOG_PREFIX = "[signal_logic]"

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
                               ema_short=13, ema_long=21):
    print(f"{LOG_PREFIX} 📊 Calculating confidence score for {direction} direction")
    score = 0
    reasons = []

    # EMA trend strength
    ema_spread_pct = abs(ema13 - ema21) / (current_price if current_price != 0 else 1) * 100
    if direction == 'long' and ema13 > ema21:
        score += 12; reasons.append(f"📈 Trend bullish dikonfirmasi EMA{ema_short} di atas EMA{ema_long} (+12)")
    elif direction == 'short' and ema13 < ema21:
        score += 12; reasons.append(f"📉 Trend bearish dikonfirmasi EMA{ema_short} di bawah EMA{ema_long} (+12)")
    elif direction == 'long' and ema13 <= ema21:
        reasons.append(f"⚠️ EMA{ema_short} masih di bawah EMA{ema_long} - sinyal counter-trend, risiko tinggi (0)")
    elif direction == 'short' and ema13 >= ema21:
        reasons.append(f"⚠️ EMA{ema_short} masih di atas EMA{ema_long} - sinyal counter-trend, risiko tinggi (0)")
    
    if ema_spread_pct > 1:
        score += 8; reasons.append(f"🚀 Momentum trend sangat kuat dengan spread {ema_spread_pct:.2f}% (+8)")
    elif ema_spread_pct > 0.5:
        score += 4; reasons.append(f"⚡ Momentum trend moderat dengan spread {ema_spread_pct:.2f}% (+4)")
    else:
        reasons.append(f"📍 Spread EMA lemah {ema_spread_pct:.2f}% - market consolidation atau trend lemah (0)")

    # MACD
    macd_diff = macd_line - macd_signal
    if direction == 'long' and macd_diff > 0:
        score += 12; reasons.append(f"📊 MACD histogram positif - momentum bullish aktif (+12)")
        if macd_diff > 0.05:
            score += 8; reasons.append(f"💪 MACD divergence kuat ({macd_diff:.4f}) - strong bullish momentum (+8)")
        elif macd_diff > 0.01:
            reasons.append(f"📈 MACD histogram positif tapi lemah ({macd_diff:.4f}) - momentum masih building")
    elif direction == 'short' and macd_diff < 0:
        score += 12; reasons.append(f"📊 MACD histogram negatif - momentum bearish aktif (+12)")
        if macd_diff < -0.05:
            score += 8; reasons.append(f"💪 MACD divergence kuat ({macd_diff:.4f}) - strong bearish momentum (+8)")
        elif macd_diff < -0.01:
            reasons.append(f"📉 MACD histogram negatif tapi lemah ({macd_diff:.4f}) - momentum masih building")
    elif direction == 'long' and macd_diff <= 0:
        reasons.append(f"🔴 MACD masih negatif ({macd_diff:.4f}) - counter-trend signal, tunggu crossover (0)")
    elif direction == 'short' and macd_diff >= 0:
        reasons.append(f"🔴 MACD masih positif ({macd_diff:.4f}) - counter-trend signal, tunggu crossover (0)")

    # RSI
    if 40 <= rsi <= 60:
        score += 15; reasons.append(f"✅ RSI netral di {rsi:.1f} - zona ideal untuk entry dengan ruang gerak (+15)")
    elif 30 <= rsi < 40 or 60 < rsi <= 70:
        score += 8; reasons.append(f"⚠️ RSI di {rsi:.1f} - masih acceptable tapi perlu waspada (+8)")
    else:
        if rsi < 30:
            reasons.append(f"🔴 RSI oversold ekstrem di {rsi:.1f} - risiko reversal tinggi (0)")
        else:
            reasons.append(f"🔴 RSI overbought ekstrem di {rsi:.1f} - risiko reversal tinggi (0)")

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
        raise ValueError(f"Timeframe {timeframe} invalid. Pilih salah satu {VALID_TFS}")

    print(f"{LOG_PREFIX} 📊 Fetching OHLC data for {symbol} from {exchange.upper()}")
    df = fetch_ohlc(symbol, timeframe, exchange)
    if df is None or df.empty or len(df) < 50:
        print(f"{LOG_PREFIX} ❌ Insufficient OHLC data: {len(df) if df is not None else 0} candles")
        raise ValueError("Failed to fetch sufficient OHLC data (need min 50 candles)")

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

    # Auto-side determination (original logic)
    direction = 'neutral'
    if ema13 > ema21 and rsi_val < 70:
        direction = 'long'
    elif ema13 < ema21 and rsi_val > 30:
        direction = 'short'

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

    print(f"{LOG_PREFIX} 📊 Entry/Exit calculated - Entry: {entry_price:.6f}, Stop: {stop:.6f}, TP1: {tp1:.6f}, TP2: {tp2:.6f}, RR: {rr:.2f}")

    # Confidence
    confidence, level, reasons = calculate_confidence_score(
        direction, ema13, ema21, macd_line, macd_signal, rsi_val,
        stoch_k, stoch_d, vol_ratio, relevant_fvg, ob_high, ob_low,
        entry_price, current_price, ema_short, ema_long
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
