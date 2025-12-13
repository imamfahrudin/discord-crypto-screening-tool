# Chart Generation Feature - Implementation Guide

## Overview
The Discord crypto screening bot now generates professional trading charts with position setup visualization for every signal request.

## What's New

### Visual Features
- **Candlestick Chart**: 100 recent candles displayed with TradingView-style dark theme
- **Technical Indicators**: EMA 13 (blue) and EMA 21 (red) overlays
- **Position Setup**: 
  - Entry level (blue dashed line)
  - Stop Loss (red dashed line)
  - TP1 (light green dashed line)
  - TP2 (dark green dashed line)
  - Risk/Reward zones (shaded red for risk, green for reward)
- **FVG Zones**: Fair Value Gaps highlighted with semi-transparent boxes
  - Bullish FVG: Orange
  - Bearish FVG: Purple
- **Order Blocks**: OB High/Low levels shown with dotted lines
- **Current Price**: Yellow horizontal line with label
- **Direction Indicator**: Large arrow at top-left (▲ for LONG, ▼ for SHORT)

### Technical Implementation

#### New Files
1. **chart_generator.py** - Chart generation module
   - `generate_chart_with_setup()` - Full position setup chart
   - `generate_neutral_chart()` - Simple chart for neutral signals

#### Modified Files
1. **requirements.txt** - Added:
   - matplotlib
   - mplfinance
   - Pillow

2. **signal_logic.py** - Enhanced:
   - Added `return_dict` parameter to `generate_trade_plan()`
   - Returns comprehensive dict with all data needed for charts
   - Maintains backward compatibility (still returns string by default)

3. **discord_bot.py** - Updated:
   - Imported chart generation functions
   - Added `generate_chart_from_data()` helper
   - Added `create_signal_embed_from_dict()` for dict-based embeds
   - Modified `signal_command()` and `slash_signal()` to generate and attach charts

## Testing Instructions

### 1. Install Dependencies
```powershell
cd "d:\My Projects\discord-crypto-screening-tool"
pip install -r requirements.txt
```

### 2. Test Locally (Without Discord)
Create a test script `test_chart.py`:

```python
from signal_logic import generate_trade_plan
from chart_generator import generate_chart_from_data
from bybit_data import normalize_symbol

# Test with BTC 1h
symbol = normalize_symbol("BTC")
timeframe = "1h"

# Generate signal data
data = generate_trade_plan(symbol, timeframe, "bybit", return_dict=True)

print(f"Direction: {data.get('direction')}")
print(f"Entry: {data.get('entry')}")
print(f"SL: {data.get('stop_loss')}")
print(f"TP1: {data.get('tp1')}")
print(f"TP2: {data.get('tp2')}")

# Generate chart
def generate_chart_from_data(data, symbol, timeframe):
    from chart_generator import generate_chart_with_setup, generate_neutral_chart
    
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

chart_buf = generate_chart_from_data(data, symbol, timeframe)

# Save to file
with open(f"test_chart_{symbol}_{timeframe}.png", "wb") as f:
    f.write(chart_buf.getvalue())

print(f"Chart saved as test_chart_{symbol}_{timeframe}.png")
```

Run test:
```powershell
python test_chart.py
```

### 3. Test with Discord Bot
```powershell
python discord_bot.py
```

Try these commands in Discord:
- `!signal BTC 1h` - Auto-detect direction
- `!signal BTC 1h long` - Force long signal
- `!signal ETH 4h short` - Force short signal
- `/signal BTCUSDT 1h Auto` - Slash command

### 4. Docker Testing
```powershell
docker-compose build
docker-compose up -d
docker-compose logs -f
```

## Expected Output

### Chart Elements Checklist
- [ ] Dark theme background (#131722)
- [ ] 100 candlesticks visible
- [ ] EMA 13 (cyan) and EMA 21 (tomato) lines
- [ ] Entry, SL, TP1, TP2 levels with labels
- [ ] Risk zone shaded in red
- [ ] Reward zone shaded in green
- [ ] FVG zones highlighted (last 5)
- [ ] Order Block levels marked
- [ ] Current price yellow line
- [ ] Direction arrow/label at top-left
- [ ] Symbol, timeframe, timestamp in title
- [ ] Legend with all indicators
- [ ] TradingView-style professional appearance

### Discord Embed Features
- [ ] Embed with trade details
- [ ] Chart image attached and displayed
- [ ] TradingView link working
- [ ] All price levels formatted correctly
- [ ] Confidence score displayed

## Troubleshooting

### Issue: Chart not generating
**Solution**: Check logs for matplotlib/mplfinance errors
```powershell
# Reinstall visualization libraries
pip uninstall matplotlib mplfinance -y
pip install matplotlib mplfinance --upgrade
```

### Issue: Chart is blank or corrupted
**Solution**: Ensure OHLC data has proper datetime index
- Check `df.index` is `DatetimeIndex`
- Verify at least 100 candles available

### Issue: Discord "File too large"
**Solution**: Reduce DPI in chart_generator.py
```python
# Change in generate_chart_with_setup()
fig.savefig(buf, format='png', dpi=100, ...)  # Reduced from 150
```

### Issue: Memory leak with many requests
**Solution**: Already handled - `plt.close(fig)` called after each chart

### Issue: Colors not displaying correctly
**Solution**: Verify terminal/Discord supports PNG images
- Test saving locally first
- Check file size > 0 bytes

## Performance Considerations

### Chart Generation Time
- **Expected**: 1-3 seconds per chart
- **Bottleneck**: matplotlib rendering
- **Optimization**: Charts generated in thread pool executor (non-blocking)

### Memory Usage
- **Per Chart**: ~2-5 MB in memory
- **Cleanup**: Automatic via `plt.close()` and BytesIO
- **Concurrent Requests**: Discord bot handles sequentially

## Customization Options

### Change Chart Theme
Edit `chart_generator.py` colors:
```python
# In make_marketcolors()
up='#26a69a'    # Green candles
down='#ef5350'  # Red candles
facecolor='#131722'  # Background
```

### Change Chart Size
```python
# In mpf.plot()
figsize=(14, 8)  # Width x Height in inches
dpi=150          # Resolution
```

### Adjust Visible Candles
```python
# In generate_chart_with_setup()
df_plot = df.tail(100)  # Change 100 to desired number
```

### Modify Position Setup Colors
```python
# Entry level
color='#2962FF'  # Blue

# Stop loss
color='#FF5252'  # Red

# TP levels
color='#00E676'  # Light green (TP1)
color='#00C853'  # Dark green (TP2)
```

## API Reference

### generate_chart_with_setup()
```python
def generate_chart_with_setup(
    df: pd.DataFrame,           # OHLC data
    symbol: str,                # Trading pair
    timeframe: str,             # Chart timeframe
    direction: str,             # 'long', 'short', 'neutral'
    entry_price: float = None,  # Entry level
    stop_loss: float = None,    # Stop loss level
    tp1: float = None,          # First TP
    tp2: float = None,          # Final TP
    ema13: pd.Series = None,    # EMA 13 series
    ema21: pd.Series = None,    # EMA 21 series
    fvg_zones: list = None,     # FVG data
    ob_high: float = None,      # Order block high
    ob_low: float = None,       # Order block low
    current_price: float = None # Current market price
) -> BytesIO
```

### generate_neutral_chart()
```python
def generate_neutral_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    ema13: pd.Series = None,
    ema21: pd.Series = None,
    current_price: float = None
) -> BytesIO
```

## Future Enhancements

Potential improvements:
1. **Volume subplot** - Add volume bars below price chart
2. **RSI indicator** - Show RSI oscillator in separate pane
3. **MACD visualization** - Display MACD histogram
4. **Multiple timeframe analysis** - Show HTF levels on LTF chart
5. **Historical performance** - Mark previous TP/SL hits
6. **User preferences** - Allow users to customize chart style
7. **Animation** - GIF showing entry timing
8. **Comparison charts** - Multiple symbols side-by-side

## Commit Message
```
feat: add chart generation with position setup visualization

- Add chart_generator.py module with mplfinance integration
- Enhance signal_logic.py to return structured data dict
- Update discord_bot.py to generate and attach trading charts
- Add matplotlib, mplfinance, Pillow to requirements.txt
- Display entry, SL, TP levels, FVG zones, EMAs on charts
- Use TradingView-style dark theme for professional appearance
- Implement risk/reward zone shading for visual clarity
- Support both command and slash command chart generation
```

## License
Same as project license (see LICENSE file)

## Support
For issues or questions:
1. Check Discord bot logs: `docker-compose logs -f`
2. Review error traceback in terminal
3. Test chart generation locally first
4. Verify all dependencies installed correctly
