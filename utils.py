import re
import math

LOG_PREFIX = "[utils]"

def calculate_rr(entry, stop, tp):
    """
    Menghitung Risk/Reward Ratio.
    tp (Take Profit) harus berupa string multi-baris (TP1/TP2) atau nilai float/int.
    Kita akan menghitung RR terhadap TP2 (atau TP1 jika TP2 tidak ada).
    """
    print(f"{LOG_PREFIX} 📊 Calculating RR - Entry: {entry}, Stop: {stop}, TP: {tp}")
    
    try:
        entry = float(entry)
        stop = float(stop)
        print(f"{LOG_PREFIX} ✅ Converted entry/stop to float: {entry}/{stop}")
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Failed to convert entry/stop to float: {e}")
        return None
    
    risk = abs(entry - stop)
    if risk < 1e-8: # Jika risiko sangat mendekati nol
        print(f"{LOG_PREFIX} ⚠️ Risk too small: {risk}")
        return None

    tp_val = None
    if isinstance(tp, str):
        print(f"{LOG_PREFIX} 📝 Processing TP as string")
        # Mencari TP2: di belakang 'TP2:'
        match = re.search(r'TP2:\s*([\d\.]+)', tp)
        if match:
            try:
                tp_val = float(match.group(1))
                print(f"{LOG_PREFIX} ✅ Found TP2: {tp_val}")
            except ValueError as e:
                print(f"{LOG_PREFIX} ❌ Failed to parse TP2: {e}")
                pass
        
        # Fallback ke TP1
        if tp_val is None:
            match = re.search(r'TP1:\s*([\d\.]+)', tp)
            if match:
                try:
                    tp_val = float(match.group(1))
                    print(f"{LOG_PREFIX} ✅ Found TP1 (fallback): {tp_val}")
                except ValueError as e:
                    print(f"{LOG_PREFIX} ❌ Failed to parse TP1: {e}")
                    pass
    else:
        try:
            tp_val = float(tp)
            print(f"{LOG_PREFIX} ✅ Converted TP to float: {tp_val}")
        except Exception as e:
            print(f"{LOG_PREFIX} ❌ Failed to convert TP to float: {e}")
            pass
    
    if tp_val is None:
        print(f"{LOG_PREFIX} ⚠️ No valid TP value found")
        return None
    
    reward = abs(tp_val - entry)
    rr = round(reward / risk, 2)
    print(f"{LOG_PREFIX} ✅ RR calculated: {rr} (Risk: {risk:.6f}, Reward: {reward:.6f})")
    
    return rr


def format_price_dynamic(x):
    """
    Format angka dinamis berdasarkan besaran harga.
    """
    if not isinstance(x, (float, int)):
        print(f"{LOG_PREFIX} ⚠️ Invalid input type for format_price_dynamic: {type(x)}")
        return "-"
    
    x = float(x)
    abs_x = abs(x)
    
    # 8 desimal untuk harga < 1
    if abs_x < 1:
        result = f"{x:.8f}".rstrip('0').rstrip('.')
        print(f"{LOG_PREFIX} 💰 Formatted price < 1: {x} -> {result}")
        return result
    # 4 desimal untuk harga 1 - 9.99
    if abs_x < 10:
        result = f"{x:.4f}"
        print(f"{LOG_PREFIX} 💰 Formatted price 1-10: {x} -> {result}")
        return result
    # 3 desimal untuk harga 10 - 999.99
    if abs_x < 1000:
        result = f"{x:.3f}"
        print(f"{LOG_PREFIX} 💰 Formatted price 10-1000: {x} -> {result}")
        return result
    # 2 desimal untuk harga >= 1000
    result = f"{x:.2f}"
    print(f"{LOG_PREFIX} 💰 Formatted price >= 1000: {x} -> {result}")
    return result