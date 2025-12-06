import re
import math

def calculate_rr(entry, stop, tp):
    """
    Menghitung Risk/Reward Ratio.
    tp (Take Profit) harus berupa string multi-baris (TP1/TP2) atau nilai float/int.
    Kita akan menghitung RR terhadap TP2 (atau TP1 jika TP2 tidak ada).
    """
    try:
        entry = float(entry)
        stop = float(stop)
    except Exception:
        return None
    
    risk = abs(entry - stop)
    if risk < 1e-8: # Jika risiko sangat mendekati nol
        return None

    tp_val = None
    if isinstance(tp, str):
        # Mencari TP2: di belakang 'TP2:'
        match = re.search(r'TP2:\s*([\d\.]+)', tp)
        if match:
            try:
                tp_val = float(match.group(1))
            except ValueError:
                pass
        
        # Fallback ke TP1
        if tp_val is None:
            match = re.search(r'TP1:\s*([\d\.]+)', tp)
            if match:
                try:
                    tp_val = float(match.group(1))
                except ValueError:
                    pass
    else:
        try:
            tp_val = float(tp)
        except Exception:
            pass
    
    if tp_val is None:
        return None
    
    reward = abs(tp_val - entry)
    
    return round(reward / risk, 2)


def format_price_dynamic(x):
    """
    Format angka dinamis berdasarkan besaran harga.
    """
    if not isinstance(x, (float, int)):
        return "-"
    
    x = float(x)
    abs_x = abs(x)
    
    # 8 desimal untuk harga < 1
    if abs_x < 1:
        return f"{x:.8f}".rstrip('0').rstrip('.')
    # 4 desimal untuk harga 1 - 9.99
    if abs_x < 10:
        return f"{x:.4f}"
    # 3 desimal untuk harga 10 - 999.99
    if abs_x < 1000:
        return f"{x:.3f}"
    # 2 desimal untuk harga >= 1000
    return f"{x:.2f}"