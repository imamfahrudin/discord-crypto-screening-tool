import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from io import BytesIO
from datetime import datetime

def generate_chart_with_setup(df: pd.DataFrame, 
                               symbol: str, 
                               timeframe: str,
                               direction: str,
                               entry_price: float = None,
                               stop_loss: float = None,
                               tp1: float = None,
                               tp2: float = None,
                               ema13: pd.Series = None,
                               ema21: pd.Series = None,
                               fvg_zones: list = None,
                               ob_high: float = None,
                               ob_low: float = None,
                               current_price: float = None) -> BytesIO:
    """
    Generate a candlestick chart with position setup visualization.
    
    Args:
        df: OHLC dataframe with datetime index
        symbol: Trading pair symbol
        timeframe: Chart timeframe
        direction: 'long', 'short', or 'neutral'
        entry_price: Entry level
        stop_loss: Stop loss level
        tp1: First take profit target
        tp2: Second take profit target
        ema13: EMA 13 series (optional)
        ema21: EMA 21 series (optional)
        fvg_zones: List of Fair Value Gap zones
        ob_high: Order block high
        ob_low: Order block low
        current_price: Current market price
        
    Returns:
        BytesIO object containing the chart image
    """
    # Prepare dataframe for mplfinance (requires datetime index)
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'open_time' in df.columns:
            df = df.set_index('open_time')
        else:
            df.index = pd.to_datetime(df.index)
    
    # Limit to last 100 candles for better visibility
    df_plot = df.tail(100).copy()
    
    # Prepare additional plots (EMAs)
    add_plots = []
    
    if ema13 is not None:
        ema13_plot = ema13.tail(100)
        add_plots.append(mpf.make_addplot(ema13_plot, color='#00BFFF', width=1.5, label='EMA 13'))
    
    if ema21 is not None:
        ema21_plot = ema21.tail(100)
        add_plots.append(mpf.make_addplot(ema21_plot, color='#FF6347', width=1.5, label='EMA 21'))
    
    # Custom style with white background
    mc = mpf.make_marketcolors(
        up='#26a69a', down='#ef5350',
        edge='inherit',
        wick={'up':'#26a69a', 'down':'#ef5350'},
        volume={'up':'#26a69a', 'down':'#ef5350'},  # Volume bars match candle colors
        alpha=0.9
    )
    
    s = mpf.make_mpf_style(
        marketcolors=mc,
        gridcolor='#e0e0e0',
        gridstyle='--',
        y_on_right=True,  # Move price axis to the right
        facecolor='#ffffff',
        edgecolor='#e0e0e0',
        figcolor='#ffffff',
        gridaxis='both'
    )
    
    # Create figure
    plot_kwargs = {
        'type': 'candle',
        'style': s,
        'volume': True,  # Enable volume bars
        'volume_panel': 1,  # Volume panel position
        'panel_ratios': (6, 1),  # Main chart:Volume ratio (6:1 keeps chart from shifting up)
        'ylabel': 'Price',
        'ylabel_lower': 'Volume',
        'figsize': (14, 8),
        'returnfig': True,
        'warn_too_much_data': 200
    }
    
    if len(add_plots) > 0:
        plot_kwargs['addplot'] = add_plots
    
    fig, axes = mpf.plot(df_plot, **plot_kwargs)
    
    ax = axes[0]
    
    # Make volume bars semi-transparent if volume subplot exists
    if len(axes) > 1:
        volume_ax = axes[1]
        # Find volume bars and set transparency
        for collection in volume_ax.collections:
            collection.set_alpha(0.6)  # Semi-transparent volume bars
        for patch in volume_ax.patches:
            patch.set_alpha(0.6)  # Semi-transparent volume bars
    
    # Get y-axis limits for proper line drawing
    y_min, y_max = ax.get_ylim()
    x_min, x_max = ax.get_xlim()
    
    # Adjust x-axis to shift candles left and create space for position blocks on right
    x_range = x_max - x_min
    ax.set_xlim(x_min - x_range * 0.05, x_max + x_range * 0.15)  # Extend right side
    x_min, x_max = ax.get_xlim()  # Update after adjustment
    
    # Draw position setup levels
    if direction != 'neutral' and entry_price and stop_loss:
        # Entry level (blue)
        ax.axhline(y=entry_price, color='#2962FF', linestyle='--', linewidth=2, label=f'Entry: {entry_price:.6f}', alpha=0.8)
        
        # Stop loss level (red)
        ax.axhline(y=stop_loss, color='#FF5252', linestyle='--', linewidth=2, label=f'SL: {stop_loss:.6f}', alpha=0.8)
        
        # Take profit levels (green)
        if tp1:
            ax.axhline(y=tp1, color='#00E676', linestyle='--', linewidth=1.5, label=f'TP1: {tp1:.6f}', alpha=0.7)
        
        if tp2:
            ax.axhline(y=tp2, color='#00C853', linestyle='--', linewidth=2, label=f'TP2: {tp2:.6f}', alpha=0.8)
        
        # Draw risk/reward zone blocks (square boxes on the right - limit order placement)
        # Calculate block position (further right to show future limit order)
        block_width = (x_max - x_min) * 0.08
        block_start = x_max - block_width * 1.3
        block_end = x_max - block_width * 0.3
        
        if direction == 'long':
            # Risk zone (red block)
            rect_risk = patches.Rectangle(
                (block_start, stop_loss), 
                block_end - block_start, 
                entry_price - stop_loss,
                linewidth=1, edgecolor='#FF5252', facecolor='red', alpha=0.2
            )
            ax.add_patch(rect_risk)
            
            # Reward zone (green block)
            if tp2:
                rect_reward = patches.Rectangle(
                    (block_start, entry_price), 
                    block_end - block_start, 
                    tp2 - entry_price,
                    linewidth=1, edgecolor='#00E676', facecolor='green', alpha=0.2
                )
                ax.add_patch(rect_reward)
                
                # Add R:R ratio label on the block
                rr_ratio = abs(tp2 - entry_price) / abs(entry_price - stop_loss)
                mid_y = (entry_price + tp2) / 2
                ax.text(block_start + (block_end - block_start) / 2, mid_y, 
                       f'{rr_ratio:.1f}R', 
                       fontsize=10, fontweight='bold', color='white',
                       ha='center', va='center',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='green', alpha=0.7))
        else:  # short
            # Risk zone (red block)
            rect_risk = patches.Rectangle(
                (block_start, entry_price), 
                block_end - block_start, 
                stop_loss - entry_price,
                linewidth=1, edgecolor='#FF5252', facecolor='red', alpha=0.2
            )
            ax.add_patch(rect_risk)
            
            # Reward zone (green block)
            if tp2:
                rect_reward = patches.Rectangle(
                    (block_start, tp2), 
                    block_end - block_start, 
                    entry_price - tp2,
                    linewidth=1, edgecolor='#00E676', facecolor='green', alpha=0.2
                )
                ax.add_patch(rect_reward)
                
                # Add R:R ratio label on the block
                rr_ratio = abs(entry_price - tp2) / abs(stop_loss - entry_price)
                mid_y = (tp2 + entry_price) / 2
                ax.text(block_start + (block_end - block_start) / 2, mid_y, 
                       f'{rr_ratio:.1f}R', 
                       fontsize=10, fontweight='bold', color='white',
                       ha='center', va='center',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='green', alpha=0.7))
    
    # Draw FVG zones (if provided)
    if fvg_zones:
        for fvg in fvg_zones[-5:]:  # Show last 5 FVG zones
            fvg_type = fvg.get('type', '')
            fvg_high = fvg.get('high')
            fvg_low = fvg.get('low')
            
            if fvg_high and fvg_low:
                color = '#FFA726' if fvg_type == 'Bullish' else '#AB47BC'
                ax.fill_between([x_min, x_max], fvg_low, fvg_high, color=color, alpha=0.08)
                # Add FVG label outside the chart
                mid_y = (fvg_high + fvg_low) / 2
                ax.text(x_max + (x_max - x_min) * 0.02, mid_y, f'FVG {fvg_type[:4]}', 
                       fontsize=8, color=color, alpha=0.8,
                       ha='left', va='center',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='#ffffff', edgecolor=color, alpha=0.7))
    
    # Draw Order Block levels
    if ob_high:
        ax.axhline(y=ob_high, color='#FFA726', linestyle=':', linewidth=1.5, label=f'OB High: {ob_high:.6f}', alpha=0.6)
    
    if ob_low:
        ax.axhline(y=ob_low, color='#AB47BC', linestyle=':', linewidth=1.5, label=f'OB Low: {ob_low:.6f}', alpha=0.6)
    
    # Draw current price marker
    if current_price:
        ax.axhline(y=current_price, color='#F57C00', linestyle='-', linewidth=1, alpha=0.5)
        # Shift current price label further to the left to avoid overlap
        ax.text(x_min + (x_max - x_min) * 0.35, current_price, f'Current: {current_price:.6f}', 
               fontsize=9, color='#F57C00', alpha=0.9,
               ha='center', va='bottom',
               bbox=dict(boxstyle='round,pad=0.4', facecolor='#ffffff', edgecolor='#F57C00', alpha=0.8))
    
    # Add centered labels for trade levels
    if direction != 'neutral' and entry_price and stop_loss:
        center_x = x_min + (x_max - x_min) * 0.5
        
        # Entry/Limit price label (blue)
        ax.text(center_x, entry_price, f'Limit: {entry_price:.6f}', 
               fontsize=10, color='#2962FF', alpha=0.9,
               ha='center', va='center',
               bbox=dict(boxstyle='round,pad=0.4', facecolor='#ffffff', edgecolor='#2962FF', alpha=0.9))
        
        # Stop Loss label (red)
        ax.text(center_x, stop_loss, f'SL: {stop_loss:.6f}', 
               fontsize=10, color='#FF5252', alpha=0.9,
               ha='center', va='center',
               bbox=dict(boxstyle='round,pad=0.4', facecolor='#ffffff', edgecolor='#FF5252', alpha=0.9))
        
        # Take Profit labels (green)
        if tp1:
            ax.text(center_x, tp1, f'TP1: {tp1:.6f}', 
                   fontsize=10, color='#00E676', alpha=0.9,
                   ha='center', va='center',
                   bbox=dict(boxstyle='round,pad=0.4', facecolor='#ffffff', edgecolor='#00E676', alpha=0.9))
        
        if tp2:
            ax.text(center_x, tp2, f'TP2: {tp2:.6f}', 
                   fontsize=10, color='#00C853', alpha=0.9,
                   ha='center', va='center',
                   bbox=dict(boxstyle='round,pad=0.4', facecolor='#ffffff', edgecolor='#00C853', alpha=0.9))
    
    # Add direction arrow/label
    if direction != 'neutral':
        arrow_color = '#00E676' if direction == 'long' else '#FF5252'
        arrow_symbol = '▲' if direction == 'long' else '▼'
        direction_text = f'{arrow_symbol} {direction.upper()}'
        
        # Position at top-left (shifted down a bit)
        ax.text(0.02, 0.95, direction_text,
               transform=ax.transAxes,
               fontsize=16, fontweight='bold',
               color=arrow_color,
               ha='left', va='top',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='#ffffff', edgecolor=arrow_color, linewidth=2, alpha=0.9))
    
    # Title and formatting
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    ax.set_title(f'{symbol} • {timeframe.upper()} • {timestamp}', 
                color='#212121', fontsize=14, pad=20, fontweight='bold')
    
    # Legend - positioned at bottom left
    ax.legend(loc='lower left', bbox_to_anchor=(0.0, 0.0), 
             frameon=True, fancybox=True, shadow=True,
             facecolor='#f5f5f5', edgecolor='#bdbdbd',
             fontsize=9, labelcolor='#212121')
    
    # Grid styling
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    ax.set_facecolor('#ffffff')
    
    # Adjust layout
    plt.tight_layout()
    
    # Save to BytesIO
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, facecolor='#ffffff', edgecolor='none', bbox_inches='tight')
    buf.seek(0)
    
    # Close figure to free memory
    plt.close(fig)
    
    return buf


def generate_neutral_chart(df: pd.DataFrame,
                           symbol: str,
                           timeframe: str,
                           ema13: pd.Series = None,
                           ema21: pd.Series = None,
                           current_price: float = None) -> BytesIO:
    """
    Generate a simple chart for neutral signals without trade setup.
    """
    return generate_chart_with_setup(
        df=df,
        symbol=symbol,
        timeframe=timeframe,
        direction='neutral',
        ema13=ema13,
        ema21=ema21,
        current_price=current_price
    )
