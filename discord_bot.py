import discord
from discord.ext import commands
import json
import os
import traceback
from datetime import datetime, timezone
import time
import asyncio
import re
from urllib.parse import quote
from dotenv import load_dotenv
from signal_logic import generate_trade_plan
from exchange_factory import normalize_symbol, pair_exists, get_all_pairs
from utils import calculate_rr, format_price_dynamic
from chart_generator import generate_chart_with_setup, generate_neutral_chart

LOG_PREFIX = "[discord_bot]"

load_dotenv()

# ============================
# Load config
# ============================
TOKEN = os.environ.get("DISCORD_TOKEN")
WS_URL = os.environ.get("BYBIT_WS_URL", "wss://stream.bybit.com/v5/public/linear")
BOT_TITLE_PREFIX = os.environ.get('BOT_TITLE_PREFIX', '💎 CRYPTO SIGNAL —')
BOT_FOOTER_NAME = os.environ.get('BOT_FOOTER_NAME', 'Crypto Bot')

# ============================
# Discord Setup
# ============================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ============================
# Events
# ============================
@bot.event
async def on_ready():
    print(f"{LOG_PREFIX} ✅ Bot connected as {bot.user}")
    print(f"{LOG_PREFIX} ⏳ Loading pair cache from Bybit API...")
    try:
        pairs = get_all_pairs(force_refresh=True)
        if not pairs:
            print(f"{LOG_PREFIX} ⚠️ WARNING: Failed to load any trading pairs from Bybit API.")
        else:
            print(f"{LOG_PREFIX} ✅ Successfully loaded {len(pairs)} trading pairs.")
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ CRITICAL ERROR while fetching pairs: {e}")
        traceback.print_exc()

    print(f"{LOG_PREFIX} 🚀 Starting WebSocket connections for price updates...")
    # WebSocket connections removed - using OHLC data only
    print(f"{LOG_PREFIX} 📡 WebSocket connections skipped (using OHLC data only)")

    print(f"{LOG_PREFIX} 🔄 Syncing slash commands...")
    try:
        synced = await bot.tree.sync()
        print(f"{LOG_PREFIX} ✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Failed to sync slash commands: {e}")
        traceback.print_exc()

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Check if message starts with "$" for quick signal commands
    if message.content.startswith('$'):
        print(f"{LOG_PREFIX} 💬 Processing $ command from {message.author}: '{message.content}'")
        await message.add_reaction('🫡')
        content = message.content[1:].strip()  # Remove the "$" and strip whitespace
        if not content:
            print(f"{LOG_PREFIX} ⚠️ Empty content after $, ignoring")
            return  # Empty after "$", ignore

        # Parse the content: symbol [timeframe] [direction] [ema_short] [ema_long] [exchange] [detail] (flexible order)
        parts = content.split()
        if len(parts) < 1:
            print(f"{LOG_PREFIX} ⚠️ Insufficient parts in $ command: {len(parts)}")
            await send_error(message, "⚠️ Format: `$SYMBOL [TIMEFRAME] [long/short] [ema_short] [ema_long] [binance] [detail]`\nCoin harus di depan, timeframe default 1h jika tidak ditentukan.\nContoh: `$BTC` atau `$ETH 4h long ema20 ema50` atau `$BTC binance` atau `$BTC detail`")
            return

        # Check if this looks like an unsupported command (like $scan)
        first_part = parts[0].lower()
        if first_part in ('scan', 'signal', 'coinlist', 'help'):
            print(f"{LOG_PREFIX} ⚠️ Unsupported $ command: ${first_part}")
            await send_error(message, f"⚠️ Perintah `${first_part}` tidak didukung dengan prefix `$`.\n\nGunakan:\n• `!{first_part}` untuk command biasa\n• `/{first_part}` untuk slash command\n• `$COIN` untuk sinyal cepat (contoh: `$BTC` atau `$ETH 4h long`)")
            return

        symbol = parts[0].upper()
        remaining_parts = parts[1:]
        print(f"{LOG_PREFIX} 📊 Parsed symbol: {symbol}, remaining parts: {remaining_parts}")
        
        # Flexible parsing
        timeframe = None
        direction = None
        emas = []
        show_detail = False
        exchange = "bybit"  # Default exchange
        valid_tfs = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']
        
        for part in remaining_parts:
            part_lower = part.lower()
            
            # Check if it's an exchange
            if part_lower in ('binance', 'bybit', 'bitget', 'gateio', 'gate'):
                # Normalize 'gate' to 'gateio'
                exchange = 'gateio' if part_lower == 'gate' else part_lower
                print(f"{LOG_PREFIX} 🏦 Exchange set to: {exchange}")
                continue
            
            # Check if it's a timeframe
            if part_lower in valid_tfs:
                if timeframe is not None:
                    print(f"{LOG_PREFIX} ⚠️ Multiple timeframes detected: {timeframe} and {part_lower}")
                    await send_error(message, "⚠️ Timeframe hanya boleh satu.")
                    return
                timeframe = part_lower
                continue
            
            # Check if it's a direction
            if part_lower in ('long', 'short'):
                if direction is not None:
                    print(f"{LOG_PREFIX} ⚠️ Multiple directions detected: {direction} and {part_lower}")
                    await send_error(message, "⚠️ Direction hanya boleh satu.")
                    return
                direction = part_lower
                continue
            
            # Check if it's detail flag
            if part_lower == 'detail':
                show_detail = True
                continue
            
            # Try to parse as EMA
            ema_str = part_lower.replace('ema', '') if part_lower.startswith('ema') else part_lower
            try:
                ema_val = int(ema_str)
                emas.append(ema_val)
                print(f"{LOG_PREFIX} 📈 Parsed EMA value: {ema_val}")
            except ValueError:
                print(f"{LOG_PREFIX} ⚠️ Invalid parameter: {part}")
                await send_error(message, f"⚠️ Parameter tidak valid: `{part}`. Harus timeframe, direction, EMA, atau 'detail'.")
                return
        
        print(f"{LOG_PREFIX} ✅ Parsed parameters - Timeframe: {timeframe}, Direction: {direction}, EMAs: {emas}")
        
        # Validate parsed data - set default timeframe to 1h if not specified
        if timeframe is None:
            timeframe = "1h"
            print(f"{LOG_PREFIX} 📊 Using default timeframe: {timeframe}")
        
        if len(emas) == 2:
            ema_short, ema_long = emas
        elif len(emas) == 1:
            print(f"{LOG_PREFIX} ⚠️ Only one EMA provided: {emas}")
            await send_error(message, "⚠️ Jika memberikan EMA, harus berpasangan (short dan long).")
            return
        elif len(emas) > 2:
            print(f"{LOG_PREFIX} ⚠️ Too many EMAs provided: {emas}")
            await send_error(message, "⚠️ EMA maksimal 2 nilai (short dan long).")
            return
        else:
            ema_short = None
            ema_long = None

        # Validate direction if provided
        if direction and direction not in ('long', 'short'):
            print(f"{LOG_PREFIX} ⚠️ Invalid direction: {direction}")
            await send_error(message, "⚠️ Direction harus `long` atau `short` jika ditentukan.")
            return

        # Validation for EMAs
        if ema_short is not None and ema_long is not None:
            if ema_short >= ema_long:
                print(f"{LOG_PREFIX} ⚠️ Invalid EMA values: short({ema_short}) >= long({ema_long})")
                await send_error(message, "⚠️ EMA pendek harus lebih kecil dari EMA panjang.")
                return
            if ema_short < 5 or ema_long > 200:
                print(f"{LOG_PREFIX} ⚠️ EMA values out of range: short({ema_short}), long({ema_long})")
                await send_error(message, "⚠️ Periode EMA harus antara 5 dan 200.")
                return

        print(f"{LOG_PREFIX} 🚀 Generating signal for {symbol} {timeframe} direction={direction} exchange={exchange} ema_short={ema_short} ema_long={ema_long} detail={show_detail}")
        # Generate the signal
        await generate_signal_response(message, symbol, timeframe, direction, exchange, ema_short, ema_long, show_detail)

    # Process other commands (important: this must be called for !signal and other commands to work)
    if message.content.startswith('!'):
        await message.add_reaction('🫡')
        await bot.process_commands(message)

# ============================
# Helper for embed formatting
# ============================
def safe_float(v):
    try:
        return float(v)
    except Exception:
        return None

def generate_chart_from_data(data: dict, symbol: str, timeframe: str, exchange: str = 'bybit'):
    """Generate chart from trade plan data dict"""
    try:
        direction = data.get('direction', 'neutral').lower()
        print(f"{LOG_PREFIX} 📊 Generating chart for {symbol} {timeframe} direction: {direction}")
        
        if direction == 'neutral':
            print(f"{LOG_PREFIX} 🎨 Creating neutral chart")
            chart_buf = generate_neutral_chart(
                df=data['df'],
                symbol=symbol,
                timeframe=timeframe,
                ema13=data.get('ema13_series'),
                ema21=data.get('ema21_series'),
                current_price=data.get('current_price'),
                ema_short=data.get('ema_short', 13),
                ema_long=data.get('ema_long', 21),
                exchange=exchange
            )
        else:
            print(f"{LOG_PREFIX} 🎨 Creating signal chart with setup")
            chart_buf = generate_chart_with_setup(
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
                current_price=data.get('current_price'),
                ema_short=data.get('ema_short', 13),
                ema_long=data.get('ema_long', 21),
                exchange=exchange
            )
        
        if chart_buf:
            print(f"{LOG_PREFIX} ✅ Chart generated successfully ({len(chart_buf.getvalue())} bytes)")
        else:
            print(f"{LOG_PREFIX} ⚠️ Chart generation returned None")
        return chart_buf
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Chart generation error: {e}")
        traceback.print_exc()
        return None

# Helper functions for sending responses (works for both commands and direct messages)
async def send_response(ctx_or_message, **kwargs):
    if hasattr(ctx_or_message, 'send'):  # It's a commands.Context
        await ctx_or_message.reply(**kwargs)
    else:  # It's a discord.Message
        await ctx_or_message.reply(**kwargs)

async def send_error(ctx_or_message, message: str):
    if hasattr(ctx_or_message, 'send'):  # It's a commands.Context
        await ctx_or_message.reply(message)
    else:  # It's a discord.Message
        await ctx_or_message.reply(message)

    # Add sad face reaction for errors
    message_obj = ctx_or_message.message if hasattr(ctx_or_message, 'message') else ctx_or_message
    try:
        await message_obj.remove_reaction('🫡', message_obj.guild.me)
        await message_obj.add_reaction('😢')
    except Exception:
        pass  # Ignore if can't react

async def get_available_coins(exchange='bybit'):
    """Fetch and return a sorted list of unique base coins from exchange pairs."""
    def fetch_coins():
        pairs = get_all_pairs(exchange=exchange, force_refresh=False)  # Use cache if available
        coins = set()
        for pair in pairs:
            # Assuming pairs are in BASEQUOTE format (e.g., BTCUSDT -> BTC)
            base = pair.replace('USDT', '').replace('USDC', '').replace('BUSD', '')  # Handle common quotes
            if base and base != pair:  # Avoid empty or unchanged pairs
                coins.add(base.upper())
        return sorted(coins)
    
    # Run in executor since get_all_pairs might be blocking
    return await bot.loop.run_in_executor(None, fetch_coins)

class CoinListView(discord.ui.View):
    def __init__(self, chunks, total_coins, timeout=300):
        super().__init__(timeout=timeout)
        self.chunks = chunks
        self.total_coins = total_coins
        self.current_page = 0
        self.total_pages = len(chunks)
        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0  # Previous
        self.children[1].disabled = self.current_page == self.total_pages - 1  # Next

    def get_embed(self):
        chunk = self.chunks[self.current_page]
        start_num = self.current_page * len(self.chunks[0]) + 1
        coin_list = "\n".join(f"{start_num + i}. {coin}" for i, coin in enumerate(chunk))
        
        embed = discord.Embed(
            title=f"🪙 Available Coins for Trading Signals (Page {self.current_page + 1}/{self.total_pages})",
            description=f"Here are the supported coins (base currencies from Bybit pairs):\n\n{coin_list}",
            color=0x00FF88
        )
        embed.set_footer(text=f"{BOT_FOOTER_NAME} • Total coins: {self.total_coins} • Page {self.current_page + 1}/{self.total_pages}")
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, emoji="⬅️")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.get_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.get_embed()
            await interaction.response.edit_message(embed=embed, view=self)

# Shared signal generation logic
async def generate_signal_response(ctx_or_message, symbol: str, timeframe: str, direction: str = None, exchange: str = "bybit", ema_short: int = None, ema_long: int = None, show_detail: bool = False):
    print(f"{LOG_PREFIX} 🚀 Starting signal generation for {symbol} {timeframe} direction={direction} ema_short={ema_short} ema_long={ema_long}")
    
    valid_tfs = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']
    if timeframe.lower() not in [t.lower() for t in valid_tfs]:
        print(f"{LOG_PREFIX} ⚠️ Invalid timeframe: {timeframe}")
        await send_error(ctx_or_message, f"⚠️ Invalid timeframe `{timeframe}`. Pilih dari {valid_tfs}.")
        return

    forced = None
    if direction:
        dir_norm = direction.strip().lower()
        if dir_norm not in ('long','short'):
            print(f"{LOG_PREFIX} ⚠️ Invalid direction: {direction}")
            await send_error(ctx_or_message, "⚠️ Jika menambahkan direction, gunakan `long` atau `short`.")
            return
        forced = dir_norm

    def run_blocking_calls():
        print(f"{LOG_PREFIX} 🔄 Executing blocking signal generation logic")
        symbol_norm = normalize_symbol(symbol)
        if not pair_exists(symbol_norm, exchange):
            print(f"{LOG_PREFIX} ❌ Pair not available: {symbol_norm}")
            return f"❌ Pasangan `{symbol_norm}` tidak tersedia di {exchange.upper()}."
        # Get dict data for chart generation
        result = generate_trade_plan(symbol_norm, timeframe, exchange, forced_direction=forced, return_dict=True, ema_short=ema_short or 13, ema_long=ema_long or 21)
        print(f"{LOG_PREFIX} ✅ Signal generation completed for {symbol_norm}")
        return result

    try:
        print(f"{LOG_PREFIX} ⏳ Running signal generation in thread pool...")
        result = await bot.loop.run_in_executor(None, run_blocking_calls)
        if isinstance(result, str):
            print(f"{LOG_PREFIX} ❌ Signal generation returned error string: {result}")
            await send_error(ctx_or_message, result)
            return

        symbol_norm = normalize_symbol(symbol, exchange)
        print(f"{LOG_PREFIX} 📊 Generating chart for {symbol_norm}...")
        
        # Generate chart
        chart_buf = await bot.loop.run_in_executor(None, generate_chart_from_data, result, symbol_norm, timeframe, exchange)
        
        # Create embed
        print(f"{LOG_PREFIX} 📝 Creating embed for signal response")
        embed, view = create_signal_embed_from_dict(result, symbol_norm, timeframe, show_detail, exchange, ema_short, ema_long, direction)
        
        # Send with chart attachment
        if chart_buf:
            print(f"{LOG_PREFIX} 📤 Sending response with chart ({len(chart_buf.getvalue())} bytes)")
            file = discord.File(chart_buf, filename=f"chart_{symbol_norm}_{timeframe}.png")
            await send_response(ctx_or_message, embed=embed, file=file, view=view)
            print(f"{LOG_PREFIX} ✅ Signal response sent successfully")
        else:
            print(f"{LOG_PREFIX} 📤 Sending response without chart")
            await send_response(ctx_or_message, embed=embed, view=view)
            print(f"{LOG_PREFIX} ✅ Signal response sent successfully (no chart)")
            
        # Add success reaction
        message_obj = ctx_or_message.message if hasattr(ctx_or_message, 'message') else ctx_or_message
        try:
            await message_obj.remove_reaction('🫡', message_obj.guild.me)
            await message_obj.add_reaction('✅')
        except Exception:
            pass
    except ValueError as e:
        print(f"{LOG_PREFIX} ⚠️ ValueError in signal generation: {e}")
        await send_error(ctx_or_message, f"⚠️ Kesalahan dalam input/data: `{e}`")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"{LOG_PREFIX} ❌ Unexpected error in signal generation: {e}")
        print(f"{LOG_PREFIX} 📄 Full traceback:\n{tb}")
        await send_error(ctx_or_message, f"⚠️ Error menghasilkan sinyal. Cek log terminal: `{e}`")
        print(tb)

def create_signal_embed_from_dict(data: dict, symbol: str, timeframe: str, show_detail: bool = False, exchange: str = 'bybit', original_ema_short: int = 13, original_ema_long: int = 21, direction: str = None):
    """Create embed from dict data (new format)"""
    current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    direction_val = data.get('direction', 'NETRAL').upper()
    
    # color & emoji
    if direction_val == "LONG":
        color = 0x00FF88; emoji = "🟢"
    elif direction_val == "SHORT":
        color = 0xFF5555; emoji = "🔴"
    else:
        color = 0xFFD700; emoji = "🟡"
    
    interval_map = {
        "1m":"1","3m":"3","5m":"5","15m":"15","30m":"30",
        "1h":"60","2h":"120","4h":"240","6h":"360",
        "1d":"1D","1w":"1W","1M":"1M"
    }
    interval = interval_map.get(timeframe.lower(), "1D")
    exchange_upper = exchange.upper()
    # Ensure symbol ends with USDT for proper TradingView pair notation
    if not symbol.endswith('USDT'):
        symbol += 'USDT'
    tv_url = f"https://www.tradingview.com/chart/?symbol={quote(f'{exchange_upper}:{symbol}.P')}&interval={interval}"
    
    embed = discord.Embed(color=color)
    
    if direction_val == "NETRAL":
        embed.title = f"{emoji} {symbol} — {timeframe.upper()} NEUTRAL"
        embed.description = "📊 **Analysis:** Market is consolidating or FVG/Momentum criteria not met."
        
        embed.add_field(name="🕒 Timeframe", value=f"`{timeframe.upper()}`", inline=True)
        embed.add_field(name="🧭 Generated", value=f"`{current_time}`", inline=True)
        # Add EMA periods field for neutral signals too
        ema_short = data.get('ema_short', 13)
        ema_long = data.get('ema_long', 21)
        embed.add_field(name="📈 EMA Periods", value=f"`{ema_short}/{ema_long}`", inline=True)
        embed.add_field(name="🏦 Exchange", value=f"`{exchange_upper}`", inline=True)
        if show_detail:
            embed.add_field(name="📋 Detailed Analysis", value=data.get('insight', 'No details available.'), inline=False)
    else:
        entry_fmt = format_price_dynamic(data.get('entry'))
        sl_fmt = format_price_dynamic(data.get('stop_loss'))
        tp1_fmt = format_price_dynamic(data.get('tp1'))
        tp2_fmt = format_price_dynamic(data.get('tp2'))
        rr_fmt = f"{data.get('rr'):.2f}R" if data.get('rr') else "N/A"
        confidence = f"{data.get('confidence')}% {data.get('confidence_level', '')}"
        
        embed.title = f"{BOT_TITLE_PREFIX} {direction_val} {symbol}"
        embed.description = f"{emoji} **{direction_val} Signal** for {symbol} on {timeframe.upper()} timeframe"
        
        embed.add_field(name="📊 Pair", value=f"`{symbol}`", inline=True)
        embed.add_field(name="🕒 Timeframe", value=f"`{timeframe.upper()}`", inline=True)
        embed.add_field(name="🧭 Generated", value=f"`{current_time}`", inline=True)
        
        # Add EMA periods field
        ema_short = data.get('ema_short', 13)
        ema_long = data.get('ema_long', 21)
        embed.add_field(name="📈 EMA Periods", value=f"`{ema_short}/{ema_long}`", inline=True)
        embed.add_field(name="🏦 Exchange", value=f"`{exchange_upper}`", inline=True)
        
        embed.add_field(name="📈 Entry", value=f"`{entry_fmt}`", inline=True)
        embed.add_field(name="🛑 Stop Loss", value=f"`{sl_fmt}`", inline=True)
        embed.add_field(name="💰 Risk/Reward", value=f"`{rr_fmt}`", inline=True)
        
        embed.add_field(name="🎯 Take Profits", value=f"**TP1 (1.5R):** `{tp1_fmt}`\n**TP2 (Final):** `{tp2_fmt}`", inline=False)
        embed.add_field(name="💡 Confidence", value=f"`{confidence}`", inline=True)
        if show_detail:
            embed.add_field(name="📋 Detailed Analysis", value=data.get('insight', 'No details available.'), inline=False)
    
    last_price_fmt = format_price_dynamic(data.get('current_price'))
    embed.set_footer(text=f"{BOT_FOOTER_NAME} • Last Price: {last_price_fmt} | Generated: {current_time}")
    
    # Set chart as image (will be attached separately)
    embed.set_image(url=f"attachment://chart_{symbol}_{timeframe}.png")
    
    # Create view with TradingView button
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        style=discord.ButtonStyle.link,
        label="📈 View on TradingView",
        url=tv_url,
        emoji="📊"
    ))
    
    # Add EMA switch button
    if ema_short == 25 and ema_long == 50:
        label = "Switch to Original EMA"
        target_short, target_long = original_ema_short, original_ema_long
    else:
        label = "Switch to EMA 25/50"
        target_short, target_long = 25, 50
    
    view.add_item(discord.ui.Button(
        style=discord.ButtonStyle.secondary,
        label=label,
        custom_id=f"ema_switch:{symbol.replace('USDT', '')}:{timeframe}:{direction or 'None'}:{exchange}:{ema_short}:{ema_long}:{target_short}:{target_long}:{show_detail}"
    ))
    
    return embed, view

# ============================
# Commands
# ============================
@bot.command(name="signal")
async def signal_command(ctx, *args):
    """
    Usage: !signal <symbol> [timeframe] [direction] [ema_short] [ema_long] [binance] [detail]
    Order is flexible after symbol. Examples:
      !signal BTC 1h
      !signal BTC 1h long
      !signal BTC short ema20 ema50 1h
      !signal ETH ema9 ema21 4h long
      !signal BTC 1h detail
      !signal BTC binance
      !signal ETH 4h binance long
    """
    if len(args) < 1:
        await send_error(ctx, "⚠️ Format: `!signal SYMBOL [TIMEFRAME] [long/short] [ema_short] [ema_long] [binance] [detail]`\nSymbol wajib, timeframe default 1h jika tidak ditentukan.\nContoh: `!signal BTC` atau `!signal ETH 4h long ema20 ema50` atau `!signal BTC binance` atau `!signal BTC detail`")
        return

    symbol = args[0].upper()
    remaining_parts = list(args[1:])
    
    # Flexible parsing (same as $ command)
    timeframe = None
    direction = None
    emas = []
    show_detail = False
    exchange = "bybit"  # Default exchange
    valid_tfs = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']
    
    for part in remaining_parts:
        part_lower = part.lower()
        
        # Check if it's an exchange
        if part_lower in ('binance', 'bybit', 'bitget', 'gateio', 'gate'):
            # Normalize 'gate' to 'gateio'
            exchange = 'gateio' if part_lower == 'gate' else part_lower
            print(f"{LOG_PREFIX} 🏦 Exchange set to: {exchange}")
            continue
        
        # Check if it's a timeframe
        if part_lower in valid_tfs:
            if timeframe is not None:
                await send_error(ctx, "⚠️ Timeframe hanya boleh satu.")
                return
            timeframe = part_lower
            continue
        
        # Check if it's a direction
        if part_lower in ('long', 'short'):
            if direction is not None:
                await send_error(ctx, "⚠️ Direction hanya boleh satu.")
                return
            direction = part_lower
            continue
        
        # Check if it's detail flag
        if part_lower == 'detail':
            show_detail = True
            continue
        
        # Try to parse as EMA
        ema_str = part_lower.replace('ema', '') if part_lower.startswith('ema') else part_lower
        try:
            ema_val = int(ema_str)
            emas.append(ema_val)
        except ValueError:
            await send_error(ctx, f"⚠️ Parameter tidak valid: `{part}`. Harus timeframe, direction, EMA, atau 'detail'.")
            return
    
    # Validate parsed data - set default timeframe to 1h if not specified
    if timeframe is None:
        timeframe = "1h"
        print(f"{LOG_PREFIX} 📊 Using default timeframe: {timeframe}")
    
    if len(emas) == 2:
        ema_short, ema_long = emas
    elif len(emas) == 1:
        await send_error(ctx, "⚠️ Jika memberikan EMA, harus berpasangan (short dan long).")
        return
    elif len(emas) > 2:
        await send_error(ctx, "⚠️ EMA maksimal 2 nilai (short dan long).")
        return
    else:
        ema_short = None
        ema_long = None

    # Validation for EMAs
    if ema_short is not None and ema_long is not None:
        if ema_short >= ema_long:
            await send_error(ctx, "⚠️ EMA pendek harus lebih kecil dari EMA panjang.")
            return
        if ema_short < 5 or ema_long > 200:
            await send_error(ctx, "⚠️ Periode EMA harus antara 5 dan 200.")
            return
    
    await generate_signal_response(ctx, symbol, timeframe, direction, exchange, ema_short, ema_long, show_detail)

@bot.command(name="scan")
async def scan_command(ctx, *, args: str):
    """
    Scan multiple coins for the best trading signal setup.
    Usage: !scan <coin1 coin2 ...> [ema_short] [ema_long] [binance]
    Or: !scan <coin1,coin2,...> [ema_short] [ema_long] [binance]
    For each coin, checks all setups and selects the one with highest confidence.
    Maximum 5 coins per scan.
    """
    if not args.strip():
        await send_error(ctx, "⚠️ Format: `!scan COIN1 COIN2 ... [ema_short] [ema_long] [binance]`\nOr: `!scan COIN1,COIN2,... [ema_short] [ema_long] [binance]`\nContoh: `!scan BTC ETH SOL` atau `!scan BTC,ETH ema20 ema50` atau `!scan BTC ETH binance`")
        return

    parts = args.split()
    if len(parts) < 1:
        await send_error(ctx, "⚠️ Format: `!scan COIN1 COIN2 ... [ema_short] [ema_long] [binance]`\nOr: `!scan COIN1,COIN2,... [ema_short] [ema_long] [binance]`\nContoh: `!scan BTC ETH SOL` atau `!scan BTC,ETH ema20 ema50` atau `!scan BTC ETH binance`")
        return

    # Flexible parsing: collect coins, EMAs, and exchange
    coins = []
    emas = []
    exchange = "bybit"  # Default exchange
    valid_tfs = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']

    for part in parts:
        part_lower = part.lower()
        
        # Check if it's an exchange
        if part_lower in ('binance', 'bybit', 'bitget', 'gateio', 'gate'):
            # Normalize 'gate' to 'gateio'
            exchange = 'gateio' if part_lower == 'gate' else part_lower
            print(f"{LOG_PREFIX} 🏦 Exchange set to: {exchange}")
            continue
        
        # Try to parse as EMA
        ema_str = part_lower.replace('ema', '') if part_lower.startswith('ema') else part_lower
        try:
            ema_val = int(ema_str)
            emas.append(ema_val)
        except ValueError:
            # Assume it's a coin (possibly comma-separated)
            coins.append(part.strip().upper())

    # Process coins (split by comma if needed)
    coins_list = []
    for coin_part in coins:
        coins_list.extend([c.strip() for c in coin_part.split(',') if c.strip()])
    
    coins_final = [c for c in coins_list if c]
    
    if not coins_final:
        await send_error(ctx, "⚠️ Tidak ada koin yang valid diberikan.")
        return
    
    # Limit to 5 coins per scan to prevent abuse
    if len(coins_final) > 5:
        await send_error(ctx, f"⚠️ Terlalu banyak koin! Maksimal 5 koin per scan. Anda memberikan {len(coins_final)} koin.")
        return

    # Validate EMAs
    ema_short = None
    ema_long = None

    if len(emas) == 2:
        ema_short, ema_long = emas
    elif len(emas) == 1:
        await send_error(ctx, "⚠️ Jika memberikan EMA, harus berpasangan (short dan long).")
        return
    elif len(emas) > 2:
        await send_error(ctx, "⚠️ EMA maksimal 2 nilai (short dan long).")
        return
    else:
        ema_short = 13  # Default
        ema_long = 21   # Default

    # Validation for EMAs
    if ema_short >= ema_long:
        await send_error(ctx, "⚠️ EMA pendek harus lebih kecil dari EMA panjang.")
        return
    if ema_short < 5 or ema_long > 200:
        await send_error(ctx, "⚠️ Periode EMA harus antara 5 dan 200.")
        return

    print(f"{LOG_PREFIX} 🔍 Scan command triggered by {ctx.author} for coins: {coins_final} with EMA {ema_short}/{ema_long} on {exchange.upper()}")

    # Define all setups to check
    setups = [
        ("1h", "long"),    # $coin 1h long
        ("1h", "short"),   # $coin 1h short
        ("4h", "long"),    # $coin 4h long
        ("4h", "short"),   # $coin 4h short
    ]

    # Create all scan tasks for parallel execution
    scan_tasks = []
    for coin in coins_final:
        # Check if coin looks like a timeframe or direction - hint to use $ command
        coin_lower = coin.lower()
        if coin_lower in [t.lower() for t in valid_tfs] or coin_lower in ('long', 'short', 'detail'):
            await send_error(ctx, f"⚠️ '{coin}' terlihat seperti parameter untuk sinyal tunggal. Jika Anda ingin sinyal tunggal, gunakan perintah `$` seperti `$BTC 1d long detail`.")
            continue

        for timeframe, direction in setups:
            setup_str = f"${coin} {timeframe}"
            if direction:
                setup_str += f" {direction}"

            # Append custom EMA values if not using defaults (13/21)
            if ema_short != 13 or ema_long != 21:
                setup_str += f" ema{ema_short} ema{ema_long}"

            scan_tasks.append((coin, timeframe, direction, setup_str))

    print(f"{LOG_PREFIX} 🚀 Starting parallel scan for {len(scan_tasks)} setups across {len(coins_final)} coins")

    # Execute all scans in parallel
    async def run_single_scan(coin, timeframe, direction, setup_str):
        def run_scan():
            symbol_norm = normalize_symbol(coin, exchange)
            if not pair_exists(symbol_norm, exchange):
                return None
            result = generate_trade_plan(symbol_norm, timeframe, exchange, forced_direction=direction, return_dict=True, ema_short=ema_short, ema_long=ema_long)
            return result, setup_str

        try:
            result_tuple = await bot.loop.run_in_executor(None, run_scan)
            if result_tuple is None:
                print(f"{LOG_PREFIX} ❌ Pair not available: {coin}")
                return None
            result, setup_str = result_tuple
            if isinstance(result, str):
                print(f"{LOG_PREFIX} ❌ Signal generation returned error for {setup_str}: {result}")
                return None
            confidence = result.get('confidence', 0)
            print(f"{LOG_PREFIX} ✅ Setup {setup_str}: confidence {confidence}%")
            return (coin, confidence, setup_str, result)
        except Exception as e:
            print(f"{LOG_PREFIX} ❌ Error scanning {setup_str}: {e}")
            return None

    # Create and run all tasks concurrently
    tasks = [run_single_scan(coin, tf, dir, setup) for coin, tf, dir, setup in scan_tasks]
    scan_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Group results by coin
    coin_results = {}
    for result in scan_results:
        if result is None or isinstance(result, Exception):
            continue
        coin, confidence, setup_str, data = result
        if coin not in coin_results:
            coin_results[coin] = []
        coin_results[coin].append((confidence, setup_str, data))

    # Process results for each coin
    for coin in coins_final:
        if coin not in coin_results or not coin_results[coin]:
            await send_error(ctx, f"⚠️ Tidak ada hasil valid untuk {coin}. Pasangan mungkin tidak ada.")
            continue

        results = coin_results[coin]

        # Find the best result (highest confidence)
        best_result = max(results, key=lambda x: x[0])
        best_confidence, best_setup, best_data = best_result

        # Extract timeframe from best setup (format: "$COIN TIMEFRAME DIRECTION")
        # Split: ['$BTC', '1h', 'long'] -> index 1 is timeframe
        best_timeframe = best_setup.split()[1]

        print(f"{LOG_PREFIX} 🏆 Best setup for {coin}: {best_setup} with {best_confidence}% confidence")

        # Generate chart for best result
        chart_buf = await bot.loop.run_in_executor(None, generate_chart_from_data, best_data, normalize_symbol(coin, exchange), best_timeframe, exchange)

        # Create embed with all confidences listed
        symbol_norm = normalize_symbol(coin, exchange)
        embed, view = create_scan_embed_from_dict(best_data, symbol_norm, best_timeframe, results, exchange, ema_short, ema_long, None)

        # Send response
        if chart_buf:
            file = discord.File(chart_buf, filename=f"chart_{symbol_norm}_{best_timeframe}.png")
            await send_response(ctx, embed=embed, file=file, view=view)
        else:
            await send_response(ctx, embed=embed, view=view)

        print(f"{LOG_PREFIX} ✅ Scan result sent for {coin}")

def create_scan_embed_from_dict(data: dict, symbol: str, timeframe: str, all_results: list, exchange: str = 'bybit', original_ema_short: int = 13, original_ema_long: int = 21, direction: str = None):
    current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    direction_val = data.get('direction', 'NETRAL').upper()
    
    # color & emoji
    if direction_val == "LONG":
        color = 0x00FF88; emoji = "🟢"
    elif direction_val == "SHORT":
        color = 0xFF5555; emoji = "🔴"
    else:
        color = 0xFFD700; emoji = "🟡"
    
    interval_map = {
        "1m":"1","3m":"3","5m":"5","15m":"15","30m":"30",
        "1h":"60","2h":"120","4h":"240","6h":"360",
        "1d":"1D","1w":"1W","1M":"1M"
    }
    interval = interval_map.get(timeframe.lower(), "1D")
    exchange_upper = exchange.upper()
    # Ensure symbol ends with USDT for proper TradingView pair notation
    if not symbol.endswith('USDT'):
        symbol += 'USDT'
    tv_url = f"https://www.tradingview.com/chart/?symbol={quote(f'{exchange_upper}:{symbol}.P')}&interval={interval}"
    
    embed = discord.Embed(color=color)
    
    if direction_val == "NETRAL":
        embed.title = f"{emoji} {symbol} — {timeframe.upper()} NEUTRAL (Scanned)"
        embed.description = "📊 **Analysis:** Market is consolidating or FVG/Momentum criteria not met."
        
        embed.add_field(name="🕒 Timeframe", value=f"`{timeframe.upper()}`", inline=True)
        embed.add_field(name="🧭 Generated", value=f"`{current_time}`", inline=True)
        embed.add_field(name="📈 EMA Periods", value=f"`{data.get('ema_short', 13)}/{data.get('ema_long', 21)}`", inline=True)
        embed.add_field(name="🏦 Exchange", value=f"`{exchange_upper}`", inline=True)
    else:
        entry_fmt = format_price_dynamic(data.get('entry'))
        sl_fmt = format_price_dynamic(data.get('stop_loss'))
        tp1_fmt = format_price_dynamic(data.get('tp1'))
        tp2_fmt = format_price_dynamic(data.get('tp2'))
        rr_fmt = f"{data.get('rr'):.2f}R" if data.get('rr') else "N/A"
        confidence = f"{data.get('confidence')}% {data.get('confidence_level', '')}"
        
        embed.title = f"{BOT_TITLE_PREFIX} {direction_val} {symbol} (Scanned)"
        embed.description = f"{emoji} **{direction_val} Signal** for {symbol} on {timeframe.upper()} timeframe (Best from scan)"
        
        embed.add_field(name="📊 Pair", value=f"`{symbol}`", inline=True)
        embed.add_field(name="🕒 Timeframe", value=f"`{timeframe.upper()}`", inline=True)
        embed.add_field(name="🧭 Generated", value=f"`{current_time}`", inline=True)
        
        embed.add_field(name="📈 EMA Periods", value=f"`{data.get('ema_short', 13)}/{data.get('ema_long', 21)}`", inline=True)
        embed.add_field(name="🏦 Exchange", value=f"`{exchange_upper}`", inline=True)
        
        embed.add_field(name="📈 Entry", value=f"`{entry_fmt}`", inline=True)
        embed.add_field(name="🛑 Stop Loss", value=f"`{sl_fmt}`", inline=True)
        embed.add_field(name="💰 Risk/Reward", value=f"`{rr_fmt}`", inline=True)
        
        embed.add_field(name="🎯 Take Profits", value=f"**TP1 (1.5R):** `{tp1_fmt}`\n**TP2 (Final):** `{tp2_fmt}`", inline=False)
        embed.add_field(name="💡 Confidence", value=f"`{confidence}`", inline=True)
    
    # Add all confidences list
    sorted_results = sorted(all_results, key=lambda x: x[0], reverse=True)
    confidence_items = []
    for i, (conf, setup, _) in enumerate(sorted_results):
        if i == 0:  # First item is the best
            confidence_items.append(f"• {conf}% - `{setup}` ✅")
        else:
            confidence_items.append(f"• {conf}% - `{setup}`")
    confidence_list = "\n".join(confidence_items)
    embed.add_field(name="📋 All Confidences (Scanned Setups)", value=confidence_list, inline=False)
    
    last_price_fmt = format_price_dynamic(data.get('current_price'))
    embed.set_footer(text=f"{BOT_FOOTER_NAME} • Last Price: {last_price_fmt} | Generated: {current_time}")
    
    # Set chart as image
    embed.set_image(url=f"attachment://chart_{symbol}_{timeframe}.png")
    
    # Create view with TradingView button
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        style=discord.ButtonStyle.link,
        label="📈 View on TradingView",
        url=tv_url,
        emoji="📊"
    ))
    
    # Add EMA switch button
    ema_short = data.get('ema_short', 13)
    ema_long = data.get('ema_long', 21)
    if ema_short == 25 and ema_long == 50:
        label = "Switch to Original EMA"
        target_short, target_long = original_ema_short, original_ema_long
    else:
        label = "Switch to EMA 25/50"
        target_short, target_long = 25, 50
    
    view.add_item(discord.ui.Button(
        style=discord.ButtonStyle.secondary,
        label=label,
        custom_id=f"ema_switch:{symbol.replace('USDT', '')}:{timeframe}:{direction or 'None'}:{exchange}:{ema_short}:{ema_long}:{target_short}:{target_long}:False"  # show_detail=False for scan
    ))
    
    return embed, view

@bot.command(name="coinlist")
async def coinlist_command(ctx, *, args: str = ""):
    """
    List all available coins for trading signals.
    Usage: !coinlist [binance|bitget|gateio|gate]
    """
    print(f"{LOG_PREFIX} 📋 Coinlist command triggered by {ctx.author}")
    
    # Parse exchange (default to bybit)
    args_lower = args.lower()
    if 'binance' in args_lower:
        exchange = 'binance'
    elif 'bitget' in args_lower:
        exchange = 'bitget'
    elif 'gateio' in args_lower or 'gate' in args_lower:
        exchange = 'gateio'
    else:
        exchange = 'bybit'
    print(f"{LOG_PREFIX} 🏦 Using exchange: {exchange}")
    
    try:
        coins = await get_available_coins(exchange=exchange)
        if not coins:
            await send_error(ctx, "⚠️ Tidak ada koin yang tersedia saat ini. Coba lagi nanti.")
            return
        
        # Split coins into chunks of 100 for pagination
        chunk_size = 100
        chunks = [coins[i:i + chunk_size] for i in range(0, len(coins), chunk_size)]
        
        view = CoinListView(chunks, len(coins))
        embed = view.get_embed()
        embed.title = f"📋 Available Coins ({exchange.upper()})"
        
        await send_response(ctx, embed=embed, view=view)
        print(f"{LOG_PREFIX} ✅ Coinlist sent successfully ({len(coins)} coins in {len(chunks)} pages)")
    
        # Add success reaction
        message_obj = ctx.message
        try:
            await message_obj.remove_reaction('🫡', message_obj.guild.me)
            await message_obj.add_reaction('✅')
        except Exception:
            pass
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Coinlist command error: {e}")
        await send_error(ctx, f"⚠️ Error mengambil daftar koin: {e}")

@bot.command(name="ping")
async def ping_command(ctx):
    """
    Check bot latency and benchmark exchange response times for $BTC command.
    """
    print(f"{LOG_PREFIX} 🏓 Ping command triggered by {ctx.author}")
    
    # Measure bot latency
    latency = round(bot.latency * 1000)
    
    # Benchmark exchanges in parallel (non-blocking)
    exchanges = ['bybit', 'binance', 'bitget', 'gateio']
    benchmark_results = {}

    async def bench_exchange(exch: str, timeout: int = 20):
        """Run generate_trade_plan in a threadpool for the given exchange and return ms or 'Error' on failure/timeout."""
        loop = bot.loop
        start = time.time()
        try:
            coro = loop.run_in_executor(None, lambda: generate_trade_plan("BTC", "1h", exch, forced_direction=None, return_dict=True, ema_short=13, ema_long=21))
            # enforce timeout for each exchange
            result = await asyncio.wait_for(coro, timeout=timeout)
            if isinstance(result, str):
                return exch, "Error"
            elapsed = round((time.time() - start) * 1000)
            return exch, elapsed
        except asyncio.TimeoutError:
            return exch, "Timeout"
        except Exception:
            return exch, "Error"

    # schedule all benchmarks concurrently
    tasks = [asyncio.create_task(bench_exchange(ex)) for ex in exchanges]
    results = await asyncio.gather(*tasks)
    for exch, value in results:
        benchmark_results[exch] = value
    
    # Create embed
    embed = discord.Embed(
        title="🏓 Bot Ping & Exchange Benchmark",
        description="Measuring bot response time and exchange signal generation speed for $BTC command",
        color=0x00FF88
    )
    embed.add_field(name="🤖 Bot Latency", value=f"`{latency} ms`", inline=False)
    for exchange, time_taken in benchmark_results.items():
        if time_taken == "Error":
            embed.add_field(name=f"🏦 {exchange.upper()}", value="`Error`", inline=True)
        else:
            embed.add_field(name=f"🏦 {exchange.upper()}", value=f"`{time_taken} ms`", inline=True)
    
    embed.set_footer(text=f"{BOT_FOOTER_NAME}")
    
    await ctx.send(embed=embed)
    print(f"{LOG_PREFIX} ✅ Ping command completed")

# ============================
# Slash Commands
# ============================
@tree.command(name="help", description="Tampilkan perintah yang tersedia dan informasi penggunaan")
async def slash_help(interaction: discord.Interaction):
    """Tampilkan perintah yang tersedia dan informasi penggunaan"""
    print(f"{LOG_PREFIX} ❓ Help command triggered by {interaction.user}")
    
    embed = discord.Embed(
        title="🤖💎 **CRYPTO SIGNAL BOT** — Panduan Lengkap",
        description="🚀 **Bot Sinyal Trading Cryptocurrency** dengan analisis teknikal canggih menggunakan indikator RSI dan EMA untuk membantu trading Anda!",
        color=0x00ff88
    )

    embed.add_field(
        name="📊 **Perintah Sinyal Trading** (1/2)",
        value=(
            "🔹 **`/signal`** - Generate sinyal trading interaktif dengan dropdown (support custom EMA dan detail)\n"
            "🔹 **`!signal {coin} [timeframe]`** - Cek sinyal (timeframe default 1h)\n"
            "🔹 **`!signal {coin} [timeframe] {long/short}`** - Cek sinyal spesifik arah\n"
            "🔹 **`!signal {coin} [timeframe] {long/short} {ema_short} {ema_long}`** - Custom EMA\n"
            "🔹 **`!signal {coin} {long/short} {ema_short} {ema_long} [timeframe]`** - Urutan bebas setelah coin\n"
            "🔹 **`!signal {coin} [timeframe] detail`** - Tampilkan analisis detail lengkap\n"
            "🔹 **`!scan {coin1,coin2,...}`** - Scan multiple coins (max 5), pilih setup dengan confidence tertinggi\n"
            "🔹 **`!scan {coin1 coin2 ...} ema20 ema50`** - Scan dengan custom EMA (format fleksibel, max 5 coins)"
        ),
        inline=False
    )

    embed.add_field(
        name="📊 **Perintah Sinyal Trading** (2/2)",
        value=(
            "🔹 **`/scan`** - Slash command untuk scan multiple coins dengan custom EMA\n"
            "🔹 **`$ {coin} [timeframe]`** - Perintah cepat (timeframe default 1h)\n"
            "🔹 **`$ {coin} [timeframe] {long/short}`** - Perintah cepat spesifik\n"
            "🔹 **`$ {coin} {long/short} {ema_short} {ema_long} [timeframe]`** - Urutan bebas setelah coin\n"
            "🔹 **`$ {coin} [timeframe] detail`** - Perintah cepat dengan analisis detail\n"
            "🔹 **`!coinlist [binance]`** - Lihat daftar coin yang tersedia\n"
            "🔹 **`/coinlist [exchange]`** - Slash command untuk daftar coin"
        ),
        inline=False
    )

    embed.add_field(
        name="🏓 **Ping & Benchmark**",
        value=(
            "🔹 **`!ping`** - Check bot latency dan benchmark response time untuk semua exchange\n"
            "🔹 **`/ping`** - Slash command untuk ping dan benchmark exchange"
        ),
        inline=False
    )

    embed.add_field(
        name="⏰ **Timeframe yang Didukung**",
        value="`1m` `3m` `5m` `15m` `30m` `1h` `4h` `1d`",
        inline=True
    )

    embed.add_field(
        name="🎯 **Contoh Penggunaan** (1/2)",
        value=(
            "• `!signal BTC` → Sinyal BTC/USDT 1h (default)\n"
            "• `!signal BTC 1h` → Sinyal BTC/USDT 1 jam\n"
            "• `!signal ETH 4h long` → Long ETH/USDT 4 jam\n"
            "• `!signal SOL 1d short` → Short SOL/USDT harian\n"
            "• `!signal BTC 1h short ema20 ema50` → Short dengan EMA20/50\n"
            "• `!signal ETH long ema9 ema21 4h` → Urutan bebas setelah coin\n"
            "• `!signal BTC 1h detail` → Sinyal dengan analisis detail\n"
            "• `!signal BTC binance` → Gunakan data Binance Futures\n"
            "• `!signal BTC bitget` → Gunakan data Bitget Futures\n"
            "• `!signal BTC gateio` → Gunakan data Gate.io Futures\n"
            "• `!scan BTC,ETH,SOL` → Scan BTC, ETH, SOL; pilih setup terbaik per coin\n"
            "• `!scan BTC,ETH ema20 ema50` → Scan dengan EMA 20/50"
        ),
        inline=True
    )

    embed.add_field(
        name="🎯 **Contoh Penggunaan** (2/2)",
        value=(
            "• `!scan BTC ETH SOL ema20 ema50` → Format fleksibel tanpa koma\n"
            "• `!scan BTC ETH binance` → Scan dengan data Binance\n"
            "• `!scan BTC ETH bitget` → Scan dengan data Bitget\n"
            "• `!scan BTC ETH gateio` → Scan dengan data Gate.io\n"
            "• `/scan BTC,ETH,SOL` → Slash scan untuk BTC, ETH, SOL\n"
            "• `$BTC` → Cepat BTC 1h (default)\n"
            "• `$BTC 1h` → Cepat BTC 1 jam\n"
            "• `$ETH 4h long` → Cepat long ETH 4 jam\n"
            "• `$SOL short ema20 ema50 1d` → Urutan bebas setelah coin\n"
            "• `$BTC 1h detail` → Cepat dengan analisis detail\n"
            "• `$BTC gateio` → Cepat dengan data Gate.io\n"
            "• `/signal` → Slash command interaktif (support custom EMA)"
        ),
        inline=True
    )

    embed.add_field(
        name="📋 **Parameter yang Didukung**",
        value=(
            "**🪙 COIN**: BTC, ETH, SOL, dll.\n"
            "**⏱️ TIMEFRAME**: Optional, default 1h. Lihat kolom sebelah kiri untuk pilihan\n"
            "**🏦 EXCHANGE**: Optional, default Bybit. Pilih 'binance', 'bitget', atau 'gateio'\n"
            "**📈 DIRECTION**: Auto (default), Long, Short\n"
            "**📊 EMA**: Optional, default 13/21. Custom EMA untuk scan dan signal\n"
            "**📊 DETAIL**: Tambahkan 'detail' untuk analisis lengkap"
        ),
        inline=False
    )

    embed.add_field(
        name="💡 **Tips Penggunaan**",
        value=(
            "• Gunakan timeframe yang sesuai dengan gaya trading Anda\n"
            "• Signal auto akan memilih arah terbaik berdasarkan analisis\n"
            "• Chart akan dilampirkan otomatis dengan setup lengkap\n"
            "• Bot mendukung data dari Bybit, Binance, dan Bitget Futures\n"
            "• Tambahkan 'detail' untuk melihat analisis teknikal mendalam\n"
            "• Tambahkan 'binance' atau 'bitget' untuk menggunakan exchange lain"
        ),
        inline=False
    )
    
    embed.set_footer(
        text="📊 Data dari Bybit, Binance & Bitget Futures • 🔍 Menggunakan RSI & EMA • 🎓 Untuk tujuan edukasi"
    )
    
    embed.set_author(
        name="Crypto Signal Bot"
    )

    try:
        print(f"{LOG_PREFIX} 📤 Sending help embed")
        await interaction.response.send_message(embed=embed)
        print(f"{LOG_PREFIX} ✅ Help command completed successfully")
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Help command failed: {e}")
        # Fallback: send directly to channel
        await interaction.channel.send(embed=embed)

@tree.command(name="signal", description="Generate crypto trading signal with custom EMAs and optional detail")
@discord.app_commands.describe(
    symbol="Trading pair symbol (e.g., BTCUSDT)",
    timeframe="Timeframe for the signal",
    direction="Direction: Auto, Long, or Short",
    ema_short="Short EMA period (default: 13)",
    ema_long="Long EMA period (default: 21)",
    detail="Show detailed analysis (default: False)",
    exchange="Exchange to use (binance, bybit, bitget, or gateio, default: bybit)"
)
@discord.app_commands.choices(timeframe=[
    discord.app_commands.Choice(name="1m", value="1m"),
    discord.app_commands.Choice(name="3m", value="3m"),
    discord.app_commands.Choice(name="5m", value="5m"),
    discord.app_commands.Choice(name="15m", value="15m"),
    discord.app_commands.Choice(name="30m", value="30m"),
    discord.app_commands.Choice(name="1h", value="1h"),
    discord.app_commands.Choice(name="4h", value="4h"),
    discord.app_commands.Choice(name="1d", value="1d")
])
@discord.app_commands.choices(direction=[
    discord.app_commands.Choice(name="Auto", value="auto"),
    discord.app_commands.Choice(name="Long", value="long"),
    discord.app_commands.Choice(name="Short", value="short")
])
@discord.app_commands.choices(exchange=[
    discord.app_commands.Choice(name="Bybit", value="bybit"),
    discord.app_commands.Choice(name="Binance", value="binance"),
    discord.app_commands.Choice(name="Bitget", value="bitget"),
    discord.app_commands.Choice(name="Gate.io", value="gateio")
])
async def slash_signal(interaction: discord.Interaction, symbol: str, timeframe: str, direction: str, ema_short: int = 13, ema_long: int = 21, detail: bool = False, exchange: str = "bybit"):
    print(f"{LOG_PREFIX} ⚡ Slash signal command triggered by {interaction.user}: symbol={symbol}, timeframe={timeframe}, direction={direction}, ema_short={ema_short}, ema_long={ema_long}, detail={detail}, exchange={exchange}")
    
    await interaction.response.defer()
    print(f"{LOG_PREFIX} ⏳ Deferred slash command response")

    # Validation for EMAs
    if ema_short >= ema_long:
        print(f"{LOG_PREFIX} ⚠️ Invalid EMA values in slash command: short({ema_short}) >= long({ema_long})")
        await interaction.followup.send("⚠️ EMA pendek harus lebih kecil dari EMA panjang.")
        return
    if ema_short < 5 or ema_long > 200:
        print(f"{LOG_PREFIX} ⚠️ EMA values out of range in slash command: short({ema_short}), long({ema_long})")
        await interaction.followup.send("⚠️ Periode EMA harus antara 5 dan 200.")
        return

    forced = None
    if direction and direction.lower() != 'auto':
        dir_norm = direction.strip().lower()
        if dir_norm not in ('long','short'):
            print(f"{LOG_PREFIX} ⚠️ Invalid direction in slash command: {direction}")
            await interaction.followup.send("⚠️ Direction harus 'auto', 'long', atau 'short'.")
            return
        forced = dir_norm

    print(f"{LOG_PREFIX} 🚀 Processing slash signal generation")
    # Create a mock context-like object for the helper function
    class MockInteraction:
        def __init__(self, interaction):
            self.interaction = interaction
        
        async def send(self, **kwargs):
            await self.interaction.followup.send(**kwargs)

    mock_ctx = MockInteraction(interaction)
    await generate_signal_response(mock_ctx, symbol, timeframe, forced, exchange, ema_short, ema_long, detail)
    print(f"{LOG_PREFIX} ✅ Slash signal command completed")

@tree.command(name="scan", description="Scan multiple coins for the best trading signal setup")
@discord.app_commands.describe(
    coins="Coins to scan (comma or space separated, max 5)",
    ema_short="Short EMA period (default: 13)",
    ema_long="Long EMA period (default: 21)",
    exchange="Exchange to use (binance, bybit, bitget, or gateio, default: bybit)"
)
@discord.app_commands.choices(exchange=[
    discord.app_commands.Choice(name="Bybit", value="bybit"),
    discord.app_commands.Choice(name="Binance", value="binance"),
    discord.app_commands.Choice(name="Bitget", value="bitget"),
    discord.app_commands.Choice(name="Gate.io", value="gateio")
])
async def slash_scan(interaction: discord.Interaction, coins: str, ema_short: int = 13, ema_long: int = 21, exchange: str = "bybit"):
    print(f"{LOG_PREFIX} 🔍 Slash scan command triggered by {interaction.user}: coins='{coins}', ema_short={ema_short}, ema_long={ema_long}, exchange={exchange}")
    
    await interaction.response.defer()
    print(f"{LOG_PREFIX} ⏳ Deferred slash scan command response")

    # Validation for EMAs
    if ema_short >= ema_long:
        print(f"{LOG_PREFIX} ⚠️ Invalid EMA values in slash scan: short({ema_short}) >= long({ema_long})")
        await interaction.followup.send("⚠️ EMA pendek harus lebih kecil dari EMA panjang.")
        return
    if ema_short < 5 or ema_long > 200:
        print(f"{LOG_PREFIX} ⚠️ EMA values out of range in slash scan: short({ema_short}), long({ema_long})")
        await interaction.followup.send("⚠️ Periode EMA harus antara 5 dan 200.")
        return

    # Parse coins
    coins_list = []
    for coin_part in coins.split():
        coins_list.extend([c.strip().upper() for c in coin_part.split(',') if c.strip()])
    
    coins_final = [c for c in coins_list if c]
    
    if not coins_final:
        await interaction.followup.send("⚠️ Tidak ada koin yang valid diberikan.")
        return
    
    # Limit to 5 coins per scan to prevent abuse
    if len(coins_final) > 5:
        await interaction.followup.send(f"⚠️ Terlalu banyak koin! Maksimal 5 koin per scan. Anda memberikan {len(coins_final)} koin.")
        return

    print(f"{LOG_PREFIX} 🔍 Processing slash scan for coins: {coins_final} with EMA {ema_short}/{ema_long} on {exchange.upper()}")

    # Define all setups to check
    setups = [
        ("1h", "long"),
        ("1h", "short"),
        ("4h", "long"),
        ("4h", "short"),
    ]

    # Create all scan tasks for parallel execution
    scan_tasks = []
    for coin in coins_final:
        # Check if coin looks like a timeframe or direction - hint to use $ command
        coin_lower = coin.lower()
        if coin_lower in [t.lower() for t in ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']] or coin_lower in ('long', 'short', 'detail'):
            await interaction.followup.send(f"⚠️ '{coin}' terlihat seperti parameter untuk sinyal tunggal. Jika Anda ingin sinyal tunggal, gunakan perintah `$` seperti `$BTC 1d long detail`.")
            continue

        for timeframe, direction in setups:
            setup_str = f"${coin} {timeframe}"
            if direction:
                setup_str += f" {direction}"

            # Append custom EMA values if not using defaults (13/21)
            if ema_short != 13 or ema_long != 21:
                setup_str += f" ema{ema_short} ema{ema_long}"

            scan_tasks.append((coin, timeframe, direction, setup_str))

    print(f"{LOG_PREFIX} 🚀 Starting parallel slash scan for {len(scan_tasks)} setups across {len(coins_final)} coins")

    # Execute all scans in parallel
    async def run_single_scan(coin, timeframe, direction, setup_str):
        def run_scan():
            symbol_norm = normalize_symbol(coin, exchange)
            if not pair_exists(symbol_norm, exchange):
                return None
            result = generate_trade_plan(symbol_norm, timeframe, exchange, forced_direction=direction, return_dict=True, ema_short=ema_short, ema_long=ema_long)
            return result, setup_str

        try:
            result_tuple = await bot.loop.run_in_executor(None, run_scan)
            if result_tuple is None:
                print(f"{LOG_PREFIX} ❌ Pair not available: {coin}")
                return None
            result, setup_str = result_tuple
            if isinstance(result, str):
                print(f"{LOG_PREFIX} ❌ Signal generation returned error for {setup_str}: {result}")
                return None
            confidence = result.get('confidence', 0)
            print(f"{LOG_PREFIX} ✅ Setup {setup_str}: confidence {confidence}%")
            return (coin, confidence, setup_str, result)
        except Exception as e:
            print(f"{LOG_PREFIX} ❌ Error scanning {setup_str}: {e}")
            return None

    # Create and run all tasks concurrently
    tasks = [run_single_scan(coin, tf, dir, setup) for coin, tf, dir, setup in scan_tasks]
    scan_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Group results by coin
    coin_results = {}
    for result in scan_results:
        if result is None or isinstance(result, Exception):
            continue
        coin, confidence, setup_str, data = result
        if coin not in coin_results:
            coin_results[coin] = []
        coin_results[coin].append((confidence, setup_str, data))

    # Process results for each coin
    for coin in coins_final:
        if coin not in coin_results or not coin_results[coin]:
            await interaction.followup.send(f"⚠️ Tidak ada hasil valid untuk {coin}. Pasangan mungkin tidak ada.")
            continue

        results = coin_results[coin]

        # Find the best result (highest confidence)
        best_result = max(results, key=lambda x: x[0])
        best_confidence, best_setup, best_data = best_result

        # Extract timeframe from best setup (format: "$COIN TIMEFRAME DIRECTION")
        # Split: ['$BTC', '1h', 'long'] -> index 1 is timeframe
        best_timeframe = best_setup.split()[1]

        print(f"{LOG_PREFIX} 🏆 Best setup for {coin}: {best_setup} with {best_confidence}% confidence")

        # Generate chart for best result
        chart_buf = await bot.loop.run_in_executor(None, generate_chart_from_data, best_data, normalize_symbol(coin, exchange), best_timeframe, exchange)

        # Create embed with all confidences listed
        embed, view = create_scan_embed_from_dict(best_data, coin, best_timeframe, results, exchange, ema_short, ema_long, None)

        # Send response
        if chart_buf:
            file = discord.File(chart_buf, filename=f"scan_chart_{coin}_{best_timeframe}.png")
            await interaction.followup.send(embed=embed, file=file, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)

        print(f"{LOG_PREFIX} ✅ Scan result sent for {coin}")

    print(f"{LOG_PREFIX} ✅ Slash scan command completed")

@tree.command(name="coinlist", description="List all available coins for trading signals")
@discord.app_commands.describe(exchange="Exchange to list coins from (bybit/binance/bitget/gateio, default: bybit)")
async def slash_coinlist(interaction: discord.Interaction, exchange: str = "bybit"):
    print(f"{LOG_PREFIX} 📋 Slash coinlist command triggered by {interaction.user}")
    
    # Normalize exchange name
    exchange = exchange.lower()
    if exchange == 'gate':
        exchange = 'gateio'
    if exchange not in ['bybit', 'binance', 'bitget', 'gateio']:
        await interaction.response.send_message("⚠️ Exchange tidak valid. Gunakan 'bybit', 'binance', 'bitget', atau 'gateio'.", ephemeral=True)
        return
    
    print(f"{LOG_PREFIX} 🏦 Using exchange: {exchange}")
    await interaction.response.defer()  # Defer for potential delay
    
    try:
        coins = await get_available_coins(exchange=exchange)
        if not coins:
            await interaction.followup.send("⚠️ Tidak ada koin yang tersedia saat ini. Coba lagi nanti.")
            return
        
        # Split coins into chunks of 100 for pagination
        chunk_size = 100
        chunks = [coins[i:i + chunk_size] for i in range(0, len(coins), chunk_size)]
        
        view = CoinListView(chunks, len(coins))
        embed = view.get_embed()
        embed.title = f"📋 Available Coins ({exchange.upper()})"
        
        await interaction.followup.send(embed=embed, view=view)
        print(f"{LOG_PREFIX} ✅ Slash coinlist sent successfully ({len(coins)} coins in {len(chunks)} pages)")
    
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Slash coinlist command error: {e}")
        await interaction.followup.send(f"⚠️ Error mengambil daftar koin: {e}")

@tree.command(name="ping", description="Check bot latency and benchmark exchange response times")
async def slash_ping(interaction: discord.Interaction):
    print(f"{LOG_PREFIX} 🏓 Slash ping command triggered by {interaction.user}")
    
    await interaction.response.defer()
    
    # Measure bot latency
    latency = round(bot.latency * 1000)
    
    # Benchmark exchanges in parallel (non-blocking)
    exchanges = ['bybit', 'binance', 'bitget', 'gateio']
    benchmark_results = {}

    async def bench_exchange(exch: str, timeout: int = 20):
        loop = bot.loop
        start = time.time()
        try:
            coro = loop.run_in_executor(None, lambda: generate_trade_plan("BTC", "1h", exch, forced_direction=None, return_dict=True, ema_short=13, ema_long=21))
            result = await asyncio.wait_for(coro, timeout=timeout)
            if isinstance(result, str):
                return exch, "Error"
            elapsed = round((time.time() - start) * 1000)
            return exch, elapsed
        except asyncio.TimeoutError:
            return exch, "Timeout"
        except Exception:
            return exch, "Error"

    tasks = [asyncio.create_task(bench_exchange(ex)) for ex in exchanges]
    results = await asyncio.gather(*tasks)
    for exch, value in results:
        benchmark_results[exch] = value
    
    # Create embed
    embed = discord.Embed(
        title="🏓 Bot Ping & Exchange Benchmark",
        description="Measuring bot response time and exchange signal generation speed for $BTC command",
        color=0x00FF88
    )
    embed.add_field(name="🤖 Bot Latency", value=f"`{latency} ms`", inline=False)
    for exchange, time_taken in benchmark_results.items():
        if time_taken == "Error":
            embed.add_field(name=f"🏦 {exchange.upper()}", value="`Error`", inline=True)
        else:
            embed.add_field(name=f"🏦 {exchange.upper()}", value=f"`{time_taken} ms`", inline=True)
    
    embed.set_footer(text=f"{BOT_FOOTER_NAME}")
    
    await interaction.followup.send(embed=embed)
    print(f"{LOG_PREFIX} ✅ Slash ping command completed")

# ============================
# Interaction Handlers
# ============================
async def scan_single_coin(coin, ema_short, ema_long, exchange):
    """Scan a single coin with given EMA and return best result, timeframe, and all results"""
    setups = [
        ("1h", "long"),
        ("1h", "short"), 
        ("4h", "long"),
        ("4h", "short"),
    ]
    
    results = []
    for timeframe, direction in setups:
        def run_scan():
            symbol_norm = normalize_symbol(coin, exchange)
            if not pair_exists(symbol_norm, exchange):
                return None
            result = generate_trade_plan(symbol_norm, timeframe, exchange, forced_direction=direction, return_dict=True, ema_short=ema_short, ema_long=ema_long)
            return result
        
        try:
            result = await bot.loop.run_in_executor(None, run_scan)
            if result is None or isinstance(result, str):
                continue
            confidence = result.get('confidence', 0)
            setup_str = f"${coin} {timeframe} {direction}"
            results.append((confidence, setup_str, result))
        except Exception as e:
            print(f"{LOG_PREFIX} ❌ Error scanning {coin} {timeframe} {direction}: {e}")
            continue
    
    if not results:
        return None, None, []
    
    # Find best result
    best_result = max(results, key=lambda x: x[0])
    best_confidence, best_setup, best_data = best_result
    best_timeframe = best_setup.split()[1]  # "$COIN TIMEFRAME DIRECTION"
    
    return best_data, best_timeframe, results

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data['custom_id']
        if custom_id.startswith("ema_switch:"):
            parts = custom_id.split(":")
            if len(parts) != 10:
                await interaction.response.send_message("Invalid button data.", ephemeral=True)
                return
            
            _, symbol, timeframe, direction, exchange, current_ema_short, current_ema_long, target_ema_short, target_ema_long, show_detail = parts
            
            # Convert types
            current_ema_short = int(current_ema_short)
            current_ema_long = int(current_ema_long)
            target_ema_short = int(target_ema_short)
            target_ema_long = int(target_ema_long)
            show_detail = show_detail == "True"
            direction = direction if direction != "None" else None
            
            await interaction.response.defer()
            
            # Get original EMAs from the original message
            original_ema_short, original_ema_long = 13, 21  # defaults
            if interaction.message.reference:
                try:
                    original_msg = await interaction.message.channel.fetch_message(interaction.message.reference.message_id)
                    original_ema_short, original_ema_long = parse_ema_from_message(original_msg.content)
                except Exception as e:
                    print(f"{LOG_PREFIX} ⚠️ Could not parse original message for EMAs: {e}")
            
            # If switching to 25/50, the target is 25/50, and original is stored
            # If switching back, target should be the original
            if target_ema_short == 25 and target_ema_long == 50:
                # Switching to 25/50, so new current is 25/50, target for back is original
                pass  # target is already 25/50
            else:
                # Switching back, target should be the original
                target_ema_short, target_ema_long = original_ema_short, original_ema_long
            
            # Regenerate signal with target EMAs
            def run_blocking_calls():
                symbol_norm = normalize_symbol(symbol)
                if not pair_exists(symbol_norm, exchange):
                    return f"❌ Pasangan `{symbol_norm}` tidak tersedia di {exchange.upper()}."
                result = generate_trade_plan(symbol_norm, timeframe, exchange, forced_direction=direction, return_dict=True, ema_short=target_ema_short, ema_long=target_ema_long)
                return result
            
            try:
                result = await bot.loop.run_in_executor(None, run_blocking_calls)
                if isinstance(result, str):
                    await interaction.followup.send(result, ephemeral=True)
                    return
                
                symbol_norm = normalize_symbol(symbol, exchange)
                chart_buf = await bot.loop.run_in_executor(None, generate_chart_from_data, result, symbol_norm, timeframe, exchange)
                
                # Check if this is a scan result by looking at the current embed title
                is_scan = "(Scanned)" in interaction.message.embeds[0].title if interaction.message.embeds else False
                
                if is_scan:
                    # Re-run scan with new EMA to find best setup
                    best_data, best_timeframe, all_results = await scan_single_coin(symbol, target_ema_short, target_ema_long, exchange)
                    if best_data is None:
                        await interaction.followup.send(f"❌ Could not generate scan result for {symbol} with EMA {target_ema_short}/{target_ema_long}", ephemeral=True)
                        return
                    
                    symbol_norm = normalize_symbol(symbol, exchange)
                    chart_buf = await bot.loop.run_in_executor(None, generate_chart_from_data, best_data, symbol_norm, best_timeframe, exchange)
                    
                    embed, view = create_scan_embed_from_dict(best_data, symbol_norm, best_timeframe, all_results, exchange, original_ema_short, original_ema_long, direction)
                else:
                    embed, view = create_signal_embed_from_dict(result, symbol_norm, timeframe, show_detail, exchange, original_ema_short, original_ema_long, direction)
                
                if chart_buf:
                    file = discord.File(chart_buf, filename=f"chart_{symbol_norm}_{timeframe}.png")
                    await interaction.message.edit(embed=embed, attachments=[file], view=view)
                else:
                    await interaction.message.edit(embed=embed, attachments=[], view=view)
                    
            except Exception as e:
                await interaction.followup.send(f"Error updating signal: {e}", ephemeral=True)

def parse_ema_from_message(content):
    """Parse EMA values from message content"""
    valid_tfs = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']
    
    if content.startswith('$'):
        parts = content[1:].strip().split()
    elif content.startswith('!signal'):
        parts = content[7:].strip().split()  # Remove !signal
    else:
        parts = content.split()
    
    emas = []
    for part in parts:
        part_lower = part.lower()
        
        # Skip known keywords and timeframes
        if (part_lower in ['detail', 'binance', 'bybit', 'bitget', 'gateio', 'gate', 'long', 'short'] or 
            part_lower in valid_tfs):
            continue
        
        # Try to parse as EMA
        ema_str = part_lower.replace('ema', '') if part_lower.startswith('ema') else part_lower
        try:
            ema_val = int(ema_str)
            if 5 <= ema_val <= 200:
                emas.append(ema_val)
        except ValueError:
            pass
    
    if len(emas) >= 2:
        return emas[0], emas[1]
    else:
        return 13, 21  # defaults

# ============================
# Start bot
# ============================
if __name__ == "__main__":
    if not TOKEN or TOKEN == "YOUR_NEW_DISCORD_TOKEN":
        print(f"{LOG_PREFIX} ❌ ERROR: Please set your Discord token in config.json or DISCORD_TOKEN environment variable.")
        exit(1)
    else:
        print(f"{LOG_PREFIX} 🚀 Starting Discord bot...")
        bot.run(TOKEN)
