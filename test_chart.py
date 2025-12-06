"""
Test script for chart generation feature
Run this to test chart generation without starting Discord bot
"""

from signal_logic import generate_trade_plan
from chart_generator import generate_chart_with_setup, generate_neutral_chart
from bybit_data import normalize_symbol
import sys

def generate_chart_from_data(data, symbol, timeframe):
    """Helper to generate chart from data dict"""
    direction = data.get('direction', 'neutral').lower()
    
    if direction == 'neutral':
        return generate_neutral_chart(
            df=data['df'],
            symbol=symbol,
            timeframe=timeframe,
            ema13=data.get('ema13_series'),
            ema21=data.get('ema21_series'),
            current_price=data.get('current_price')
        )
    else:
        return generate_chart_with_setup(
            df=data['df'],
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            entry_price=data.get('entry'),
            stop_loss=data.get('stop_loss'),
            tp1=data.get('tp1'),
            tp2=data.get('tp2'),
            ema13=data.get('ema13_series'),
            ema21=data.get('ema21_series'),
            fvg_zones=data.get('fvg_zones'),
            ob_high=data.get('ob_high'),
            ob_low=data.get('ob_low'),
            current_price=data.get('current_price')
        )

def test_chart_generation(symbol="BTC", timeframe="1h", forced_direction=None):
    """Test chart generation for a given symbol and timeframe"""
    print(f"\n{'='*60}")
    print(f"Testing chart generation for {symbol} {timeframe.upper()}")
    if forced_direction:
        print(f"Forced direction: {forced_direction.upper()}")
    print(f"{'='*60}\n")
    
    try:
        # Normalize symbol
        symbol_norm = normalize_symbol(symbol)
        print(f"Normalized symbol: {symbol_norm}")
        
        # Generate signal data
        print("Generating signal data...")
        data = generate_trade_plan(
            symbol_norm, 
            timeframe, 
            "bybit", 
            forced_direction=forced_direction,
            return_dict=True
        )
        
        # Display signal info
        print(f"\n✓ Signal generated successfully!")
        print(f"Direction: {data.get('direction')}")
        print(f"Entry: {data.get('entry')}")
        print(f"Stop Loss: {data.get('stop_loss')}")
        print(f"TP1: {data.get('tp1')}")
        print(f"TP2: {data.get('tp2')}")
        print(f"Risk/Reward: {data.get('rr')}R")
        print(f"Confidence: {data.get('confidence')}% {data.get('confidence_level')}")
        print(f"Current Price: {data.get('current_price')}")
        
        # Generate chart
        print("\nGenerating chart...")
        chart_buf = generate_chart_from_data(data, symbol_norm, timeframe)
        
        # Save to file
        filename = f"test_chart_{symbol_norm}_{timeframe}"
        if forced_direction:
            filename += f"_{forced_direction}"
        filename += ".png"
        
        with open(filename, "wb") as f:
            f.write(chart_buf.getvalue())
        
        print(f"✓ Chart saved as: {filename}")
        print(f"\n{'='*60}")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("CRYPTO SIGNAL BOT - CHART GENERATION TEST")
    print("="*60)
    
    # Test cases
    test_cases = [
        ("BTC", "1h", None),       # Auto direction
        ("ETH", "4h", "long"),     # Forced long
        ("SOL", "1h", "short"),    # Forced short
        ("BTC", "15m", None),      # Shorter timeframe
    ]
    
    results = []
    for symbol, timeframe, direction in test_cases:
        success = test_chart_generation(symbol, timeframe, direction)
        results.append((symbol, timeframe, direction, success))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for symbol, timeframe, direction, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        dir_text = direction.upper() if direction else "AUTO"
        print(f"{status} - {symbol} {timeframe.upper()} ({dir_text})")
    
    total = len(results)
    passed = sum(1 for r in results if r[3])
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*60 + "\n")
    
    sys.exit(0 if passed == total else 1)
