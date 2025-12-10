import discord
from discord.ext import commands
import json
import os
import traceback
from datetime import datetime, timezone
import re
from dotenv import load_dotenv
from signal_logic import generate_trade_plan
from bybit_data import normalize_symbol, pair_exists, get_all_pairs
from ws_prices import start_ws_in_background, PRICES
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
    start_ws_in_background(url=WS_URL, symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    print(f"{LOG_PREFIX} 📡 WebSocket connections initiated")

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

        # Parse the content: symbol [timeframe] [direction] [ema_short] [ema_long] (flexible order)
        parts = content.split()
        if len(parts) < 1:
            print(f"{LOG_PREFIX} ⚠️ Insufficient parts in $ command: {len(parts)}")
            await send_error(message, "⚠️ Format: `$SYMBOL [TIMEFRAME] [long/short] [ema_short] [ema_long] [detail]`\nCoin harus di depan, timeframe default 1h jika tidak ditentukan.\nContoh: `$BTC` atau `$ETH 4h long ema20 ema50` atau `$BTC detail`")
            return

        symbol = parts[0].upper()
        remaining_parts = parts[1:]
        print(f"{LOG_PREFIX} 📊 Parsed symbol: {symbol}, remaining parts: {remaining_parts}")
        
        # Flexible parsing
        timeframe = None
        direction = None
        emas = []
        show_detail = False
        valid_tfs = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']
        
        for part in remaining_parts:
            part_lower = part.lower()
            
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
                await send_error(message, "⚠️ Short EMA must be less than long EMA.")
                return
            if ema_short < 5 or ema_long > 200:
                print(f"{LOG_PREFIX} ⚠️ EMA values out of range: short({ema_short}), long({ema_long})")
                await send_error(message, "⚠️ EMA periods must be between 5 and 200.")
                return

        print(f"{LOG_PREFIX} 🚀 Generating signal for {symbol} {timeframe} direction={direction} ema_short={ema_short} ema_long={ema_long} detail={show_detail}")
        # Generate the signal
        await generate_signal_response(message, symbol, timeframe, direction, "bybit", ema_short, ema_long, show_detail)

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

def generate_chart_from_data(data: dict, symbol: str, timeframe: str):
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
                ema_long=data.get('ema_long', 21)
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
                ema_long=data.get('ema_long', 21)
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

async def get_available_coins():
    """Fetch and return a sorted list of unique base coins from Bybit pairs."""
    def fetch_coins():
        pairs = get_all_pairs(force_refresh=False)  # Use cache if available
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
        if not pair_exists(symbol_norm):
            print(f"{LOG_PREFIX} ❌ Pair not available: {symbol_norm}")
            return f"❌ Pair `{symbol_norm}` not available on Bybit Futures."
        # Get dict data for chart generation
        result = generate_trade_plan(symbol_norm, timeframe, exchange, forced_direction=forced, return_dict=True, ema_short=ema_short or 13, ema_long=ema_long or 21)
        print(f"{LOG_PREFIX} ✅ Signal generation completed for {symbol_norm}")
        return result

    try:
        print(f"{LOG_PREFIX} ⏳ Running signal generation in thread pool...")
        result = await bot.loop.run_in_executor(None, run_blocking_calls)
        if isinstance(result, str) and result.startswith("❌ Pair"):
            print(f"{LOG_PREFIX} ❌ Pair validation failed: {result}")
            await send_error(ctx_or_message, result)
            return

        symbol_norm = normalize_symbol(symbol)
        print(f"{LOG_PREFIX} 📊 Generating chart for {symbol_norm}...")
        
        # Generate chart
        chart_buf = await bot.loop.run_in_executor(None, generate_chart_from_data, result, symbol_norm, timeframe)
        
        # Create embed
        print(f"{LOG_PREFIX} 📝 Creating embed for signal response")
        embed = create_signal_embed_from_dict(result, symbol_norm, timeframe, show_detail)
        
        # Send with chart attachment
        if chart_buf:
            print(f"{LOG_PREFIX} 📤 Sending response with chart ({len(chart_buf.getvalue())} bytes)")
            file = discord.File(chart_buf, filename=f"chart_{symbol_norm}_{timeframe}.png")
            await send_response(ctx_or_message, embed=embed, file=file)
            print(f"{LOG_PREFIX} ✅ Signal response sent successfully")
        else:
            print(f"{LOG_PREFIX} 📤 Sending response without chart")
            await send_response(ctx_or_message, embed=embed)
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
        await send_error(ctx_or_message, f"⚠️ Error in input/data: `{e}`")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"{LOG_PREFIX} ❌ Unexpected error in signal generation: {e}")
        print(f"{LOG_PREFIX} 📄 Full traceback:\n{tb}")
        await send_error(ctx_or_message, f"⚠️ Error generating signal. Cek log terminal: `{e}`")
        print(tb)

def create_signal_embed_from_dict(data: dict, symbol: str, timeframe: str, show_detail: bool = False):
    """Create embed from dict data (new format)"""
    current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    direction = data.get('direction', 'NETRAL').upper()
    
    # color & emoji
    if direction == "LONG":
        color = 0x00FF88; emoji = "🟢"
    elif direction == "SHORT":
        color = 0xFF5555; emoji = "🔴"
    else:
        color = 0xFFD700; emoji = "🟡"
    
    interval_map = {
        "1m":"1","3m":"3","5m":"5","15m":"15","30m":"30",
        "1h":"60","2h":"120","4h":"240","6h":"360",
        "1d":"1D","1w":"1W","1M":"1M"
    }
    interval = interval_map.get(timeframe.lower(), "1D")
    tv_url = f"https://www.tradingview.com/chart/?symbol={data.get('exchange','BYBIT')}:{symbol}&interval={interval}"
    
    embed = discord.Embed(color=color)
    
    if direction == "NETRAL":
        embed.title = f"{emoji} {symbol} — {timeframe.upper()} NEUTRAL"
        embed.description = "📊 **Analysis:** Market is consolidating or FVG/Momentum criteria not met."
        
        embed.add_field(name="🕒 Timeframe", value=f"`{timeframe.upper()}`", inline=True)
        embed.add_field(name="🧭 Generated", value=f"`{current_time}`", inline=True)
        # Add EMA periods field for neutral signals too
        ema_short = data.get('ema_short', 13)
        ema_long = data.get('ema_long', 21)
        embed.add_field(name="📈 EMA Periods", value=f"`{ema_short}/{ema_long}`", inline=True)
        embed.add_field(name="🔗 Chart", value=f"[📈 TradingView]({tv_url})", inline=False)
        if show_detail:
            embed.add_field(name="📋 Detailed Analysis", value=data.get('insight', 'No details available.'), inline=False)
    else:
        entry_fmt = format_price_dynamic(data.get('entry'))
        sl_fmt = format_price_dynamic(data.get('stop_loss'))
        tp1_fmt = format_price_dynamic(data.get('tp1'))
        tp2_fmt = format_price_dynamic(data.get('tp2'))
        rr_fmt = f"{data.get('rr'):.2f}R" if data.get('rr') else "N/A"
        confidence = f"{data.get('confidence')}% {data.get('confidence_level', '')}"
        
        embed.title = f"{BOT_TITLE_PREFIX} {direction} {symbol}"
        embed.description = f"{emoji} **{direction} Signal** for {symbol} on {timeframe.upper()} timeframe"
        
        embed.add_field(name="📊 Pair", value=f"`{symbol}`", inline=True)
        embed.add_field(name="🕒 Timeframe", value=f"`{timeframe.upper()}`", inline=True)
        embed.add_field(name="🧭 Generated", value=f"`{current_time}`", inline=True)
        
        # Add EMA periods field
        ema_short = data.get('ema_short', 13)
        ema_long = data.get('ema_long', 21)
        embed.add_field(name="📈 EMA Periods", value=f"`{ema_short}/{ema_long}`", inline=True)
        
        embed.add_field(name="📈 Entry", value=f"`{entry_fmt}`", inline=True)
        embed.add_field(name="🛑 Stop Loss", value=f"`{sl_fmt}`", inline=True)
        embed.add_field(name="💰 Risk/Reward", value=f"`{rr_fmt}`", inline=True)
        
        embed.add_field(name="🎯 Take Profits", value=f"**TP1 (1.5R):** `{tp1_fmt}`\n**TP2 (Final):** `{tp2_fmt}`", inline=False)
        embed.add_field(name="💡 Confidence", value=f"`{confidence}`", inline=True)
        embed.add_field(name="🔗 Chart", value=f"[📈 TradingView]({tv_url})", inline=True)
        if show_detail:
            embed.add_field(name="📋 Detailed Analysis", value=data.get('insight', 'No details available.'), inline=False)
    
    last_price_fmt = format_price_dynamic(data.get('current_price'))
    embed.set_footer(text=f"{BOT_FOOTER_NAME} • Last Price: {last_price_fmt} | Generated: {current_time}")
    
    # Set chart as image (will be attached separately)
    embed.set_image(url=f"attachment://chart_{symbol}_{timeframe}.png")
    
    return embed

# ============================
# Commands
# ============================
@bot.command(name="signal")
async def signal_command(ctx, *args):
    """
    Usage: !signal <symbol> [timeframe] [direction] [ema_short] [ema_long] [detail]
    Order is flexible after symbol. Examples:
      !signal BTC 1h
      !signal BTC 1h long
      !signal BTC short ema20 ema50 1h
      !signal ETH ema9 ema21 4h long
      !signal BTC 1h detail
    """
    if len(args) < 1:
        await send_error(ctx, "⚠️ Format: `!signal SYMBOL [TIMEFRAME] [long/short] [ema_short] [ema_long] [detail]`\nSymbol wajib, timeframe default 1h jika tidak ditentukan.\nContoh: `!signal BTC` atau `!signal ETH 4h long ema20 ema50` atau `!signal BTC detail`")
        return

    symbol = args[0].upper()
    remaining_parts = list(args[1:])
    
    # Flexible parsing (same as $ command)
    timeframe = None
    direction = None
    emas = []
    show_detail = False
    valid_tfs = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']
    
    for part in remaining_parts:
        part_lower = part.lower()
        
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
            await send_error(ctx, "⚠️ Short EMA must be less than long EMA.")
            return
        if ema_short < 5 or ema_long > 200:
            await send_error(ctx, "⚠️ EMA periods must be between 5 and 200.")
            return
    
    await generate_signal_response(ctx, symbol, timeframe, direction, "bybit", ema_short, ema_long, show_detail)

@bot.command(name="scan")
async def scan_command(ctx, *, args: str):
    """
    Scan multiple coins for the best trading signal setup.
    Usage: !scan <coin1 coin2 ...> [ema_short] [ema_long]
    Or: !scan <coin1,coin2,...> [ema_short] [ema_long]
    For each coin, checks all setups and selects the one with highest confidence.
    Maximum 5 coins per scan.
    """
    if not args.strip():
        await send_error(ctx, "⚠️ Format: `!scan COIN1 COIN2 ... [ema_short] [ema_long]`\nOr: `!scan COIN1,COIN2,... [ema_short] [ema_long]`\nContoh: `!scan BTC ETH SOL` atau `!scan BTC,ETH ema20 ema50`")
        return

    parts = args.split()
    if len(parts) < 1:
        await send_error(ctx, "⚠️ Format: `!scan COIN1 COIN2 ... [ema_short] [ema_long]`\nOr: `!scan COIN1,COIN2,... [ema_short] [ema_long]`\nContoh: `!scan BTC ETH SOL` atau `!scan BTC,ETH ema20 ema50`")
        return

    # Flexible parsing: collect coins and EMAs
    coins = []
    emas = []

    for part in parts:
        part_lower = part.lower()
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
        await send_error(ctx, "⚠️ No valid coins provided.")
        return
    
    # Limit to 5 coins per scan to prevent abuse
    if len(coins_final) > 5:
        await send_error(ctx, f"⚠️ Too many coins! Maximum 5 coins per scan. You provided {len(coins_final)} coins.")
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
        await send_error(ctx, "⚠️ Short EMA must be less than long EMA.")
        return
    if ema_short < 5 or ema_long > 200:
        await send_error(ctx, "⚠️ EMA periods must be between 5 and 200.")
        return

    print(f"{LOG_PREFIX} 🔍 Scan command triggered by {ctx.author} for coins: {coins_final} with EMA {ema_short}/{ema_long}")

    # Define all setups to check
    setups = [
        ("1h", "long"),    # $coin 1h long
        ("1h", "short"),   # $coin 1h short
        ("4h", "long"),    # $coin 4h long
        ("4h", "short"),   # $coin 4h short
    ]

    for coin in coins_final:
        print(f"{LOG_PREFIX} 📊 Scanning coin: {coin}")
        
        results = []
        for timeframe, direction in setups:
            setup_str = f"${coin} {timeframe}"
            if direction:
                setup_str += f" {direction}"
            
            # Append custom EMA values if not using defaults (13/21)
            if ema_short != 13 or ema_long != 21:
                setup_str += f" ema{ema_short} ema{ema_long}"
            
            def run_scan():
                symbol_norm = normalize_symbol(coin)
                if not pair_exists(symbol_norm):
                    return None
                result = generate_trade_plan(symbol_norm, timeframe, "bybit", forced_direction=direction, return_dict=True, ema_short=ema_short, ema_long=ema_long)
                return result, setup_str
            
            try:
                result_tuple = await bot.loop.run_in_executor(None, run_scan)
                if result_tuple is None:
                    print(f"{LOG_PREFIX} ❌ Pair not available: {coin}")
                    continue
                result, setup_str = result_tuple
                confidence = result.get('confidence', 0)
                results.append((confidence, setup_str, result))
                print(f"{LOG_PREFIX} ✅ Setup {setup_str}: confidence {confidence}%")
            except Exception as e:
                print(f"{LOG_PREFIX} ❌ Error scanning {setup_str}: {e}")
                continue
        
        if not results:
            await send_error(ctx, f"⚠️ No valid results for {coin}. Pair may not exist.")
            continue
        
        # Find the best result (highest confidence)
        best_result = max(results, key=lambda x: x[0])
        best_confidence, best_setup, best_data = best_result
        
        # Extract timeframe from best setup (format: "$ COIN TIMEFRAME [DIRECTION]")
        best_timeframe = best_setup.split()[2]
        
        print(f"{LOG_PREFIX} 🏆 Best setup for {coin}: {best_setup} with {best_confidence}% confidence")
        
        # Generate chart for best result
        chart_buf = await bot.loop.run_in_executor(None, generate_chart_from_data, best_data, normalize_symbol(coin), best_timeframe)
        
        # Create embed with all confidences listed
        embed = create_scan_embed_from_dict(best_data, coin, best_timeframe, results)
        
        # Send response
        if chart_buf:
            file = discord.File(chart_buf, filename=f"scan_chart_{coin}_{best_timeframe}.png")
            await send_response(ctx, embed=embed, file=file)
        else:
            await send_response(ctx, embed=embed)
        
        print(f"{LOG_PREFIX} ✅ Scan result sent for {coin}")

def create_scan_embed_from_dict(data: dict, symbol: str, timeframe: str, all_results: list):
    current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    direction = data.get('direction', 'NETRAL').upper()
    
    # color & emoji
    if direction == "LONG":
        color = 0x00FF88; emoji = "🟢"
    elif direction == "SHORT":
        color = 0xFF5555; emoji = "🔴"
    else:
        color = 0xFFD700; emoji = "🟡"
    
    interval_map = {
        "1m":"1","3m":"3","5m":"5","15m":"15","30m":"30",
        "1h":"60","2h":"120","4h":"240","6h":"360",
        "1d":"1D","1w":"1W","1M":"1M"
    }
    interval = interval_map.get(timeframe.lower(), "1D")
    tv_url = f"https://www.tradingview.com/chart/?symbol={data.get('exchange','BYBIT')}:{symbol}&interval={interval}"
    
    embed = discord.Embed(color=color)
    
    if direction == "NETRAL":
        embed.title = f"{emoji} {symbol} — {timeframe.upper()} NEUTRAL (Scanned)"
        embed.description = "📊 **Analysis:** Market is consolidating or FVG/Momentum criteria not met."
        
        embed.add_field(name="🕒 Timeframe", value=f"`{timeframe.upper()}`", inline=True)
        embed.add_field(name="🧭 Generated", value=f"`{current_time}`", inline=True)
        embed.add_field(name="📈 EMA Periods", value=f"`{data.get('ema_short', 13)}/{data.get('ema_long', 21)}`", inline=True)
        embed.add_field(name="🔗 Chart", value=f"[📈 TradingView]({tv_url})", inline=False)
    else:
        entry_fmt = format_price_dynamic(data.get('entry'))
        sl_fmt = format_price_dynamic(data.get('stop_loss'))
        tp1_fmt = format_price_dynamic(data.get('tp1'))
        tp2_fmt = format_price_dynamic(data.get('tp2'))
        rr_fmt = f"{data.get('rr'):.2f}R" if data.get('rr') else "N/A"
        confidence = f"{data.get('confidence')}% {data.get('confidence_level', '')}"
        
        embed.title = f"{BOT_TITLE_PREFIX} {direction} {symbol} (Scanned)"
        embed.description = f"{emoji} **{direction} Signal** for {symbol} on {timeframe.upper()} timeframe (Best from scan)"
        
        embed.add_field(name="📊 Pair", value=f"`{symbol}`", inline=True)
        embed.add_field(name="🕒 Timeframe", value=f"`{timeframe.upper()}`", inline=True)
        embed.add_field(name="🧭 Generated", value=f"`{current_time}`", inline=True)
        
        embed.add_field(name="📈 EMA Periods", value=f"`{data.get('ema_short', 13)}/{data.get('ema_long', 21)}`", inline=True)
        
        embed.add_field(name="📈 Entry", value=f"`{entry_fmt}`", inline=True)
        embed.add_field(name="🛑 Stop Loss", value=f"`{sl_fmt}`", inline=True)
        embed.add_field(name="💰 Risk/Reward", value=f"`{rr_fmt}`", inline=True)
        
        embed.add_field(name="🎯 Take Profits", value=f"**TP1 (1.5R):** `{tp1_fmt}`\n**TP2 (Final):** `{tp2_fmt}`", inline=False)
        embed.add_field(name="💡 Confidence", value=f"`{confidence}`", inline=True)
        embed.add_field(name="🔗 Chart", value=f"[📈 TradingView]({tv_url})", inline=True)
    
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
    embed.set_image(url=f"attachment://scan_chart_{symbol}_{timeframe}.png")
    
    return embed

@bot.command(name="coinlist")
async def coinlist_command(ctx):
    """
    List all available coins for trading signals.
    Usage: !coinlist
    """
    print(f"{LOG_PREFIX} 📋 Coinlist command triggered by {ctx.author}")
    
    try:
        coins = await get_available_coins()
        if not coins:
            await send_error(ctx, "⚠️ No coins available at the moment. Try again later.")
            return
        
        # Split coins into chunks of 100 for pagination
        chunk_size = 100
        chunks = [coins[i:i + chunk_size] for i in range(0, len(coins), chunk_size)]
        
        view = CoinListView(chunks, len(coins))
        embed = view.get_embed()
        
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
        await send_error(ctx, f"⚠️ Error fetching coin list: {e}")

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
            "🔹 **`!coinlist`** - Lihat daftar coin yang tersedia\n"
            "🔹 **`/coinlist`** - Slash command untuk daftar coin"
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
            "• `!scan BTC,ETH,SOL` → Scan BTC, ETH, SOL; pilih setup terbaik per coin\n"
            "• `!scan BTC,ETH ema20 ema50` → Scan dengan EMA 20/50"
        ),
        inline=True
    )

    embed.add_field(
        name="🎯 **Contoh Penggunaan** (2/2)",
        value=(
            "• `!scan BTC ETH SOL ema20 ema50` → Format fleksibel tanpa koma\n"
            "• `/scan BTC,ETH,SOL` → Slash scan untuk BTC, ETH, SOL\n"
            "• `$BTC` → Cepat BTC 1h (default)\n"
            "• `$BTC 1h` → Cepat BTC 1 jam\n"
            "• `$ETH 4h long` → Cepat long ETH 4 jam\n"
            "• `$SOL short ema20 ema50 1d` → Urutan bebas setelah coin\n"
            "• `$BTC 1h detail` → Cepat dengan analisis detail\n"
            "• `/signal` → Slash command interaktif (support custom EMA)"
        ),
        inline=True
    )

    embed.add_field(
        name="📋 **Parameter yang Didukung**",
        value=(
            "**🪙 COIN**: BTC, ETH, SOL, dll.\n"
            "**⏱️ TIMEFRAME**: Optional, default 1h. Lihat kolom sebelah kiri untuk pilihan\n"
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
            "• Bot menggunakan data real-time dari Bybit\n"
            "• Tambahkan 'detail' untuk melihat analisis teknikal mendalam"
        ),
        inline=False
    )
    
    embed.set_footer(
        text="📊 Data dari Bybit Futures • 🔍 Menggunakan RSI & EMA • 🎓 Untuk tujuan edukasi"
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
    detail="Show detailed analysis (default: False)"
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
async def slash_signal(interaction: discord.Interaction, symbol: str, timeframe: str, direction: str, ema_short: int = 13, ema_long: int = 21, detail: bool = False):
    print(f"{LOG_PREFIX} ⚡ Slash signal command triggered by {interaction.user}: symbol={symbol}, timeframe={timeframe}, direction={direction}, ema_short={ema_short}, ema_long={ema_long}, detail={detail}")
    
    await interaction.response.defer()
    print(f"{LOG_PREFIX} ⏳ Deferred slash command response")

    # Validation for EMAs
    if ema_short >= ema_long:
        print(f"{LOG_PREFIX} ⚠️ Invalid EMA values in slash command: short({ema_short}) >= long({ema_long})")
        await interaction.followup.send("⚠️ Short EMA must be less than long EMA.")
        return
    if ema_short < 5 or ema_long > 200:
        print(f"{LOG_PREFIX} ⚠️ EMA values out of range in slash command: short({ema_short}), long({ema_long})")
        await interaction.followup.send("⚠️ EMA periods must be between 5 and 200.")
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
    await generate_signal_response(mock_ctx, symbol, timeframe, forced, "bybit", ema_short, ema_long, detail)
    print(f"{LOG_PREFIX} ✅ Slash signal command completed")

@tree.command(name="scan", description="Scan multiple coins for the best trading signal setup")
@discord.app_commands.describe(
    coins="Coins to scan (comma or space separated, max 5)",
    ema_short="Short EMA period (default: 13)",
    ema_long="Long EMA period (default: 21)"
)
async def slash_scan(interaction: discord.Interaction, coins: str, ema_short: int = 13, ema_long: int = 21):
    print(f"{LOG_PREFIX} 🔍 Slash scan command triggered by {interaction.user}: coins='{coins}', ema_short={ema_short}, ema_long={ema_long}")
    
    await interaction.response.defer()
    print(f"{LOG_PREFIX} ⏳ Deferred slash scan command response")

    # Validation for EMAs
    if ema_short >= ema_long:
        print(f"{LOG_PREFIX} ⚠️ Invalid EMA values in slash scan: short({ema_short}) >= long({ema_long})")
        await interaction.followup.send("⚠️ Short EMA must be less than long EMA.")
        return
    if ema_short < 5 or ema_long > 200:
        print(f"{LOG_PREFIX} ⚠️ EMA values out of range in slash scan: short({ema_short}), long({ema_long})")
        await interaction.followup.send("⚠️ EMA periods must be between 5 and 200.")
        return

    # Parse coins
    coins_list = []
    for coin_part in coins.split():
        coins_list.extend([c.strip().upper() for c in coin_part.split(',') if c.strip()])
    
    coins_final = [c for c in coins_list if c]
    
    if not coins_final:
        await interaction.followup.send("⚠️ No valid coins provided.")
        return
    
    # Limit to 5 coins per scan to prevent abuse
    if len(coins_final) > 5:
        await interaction.followup.send(f"⚠️ Too many coins! Maximum 5 coins per scan. You provided {len(coins_final)} coins.")
        return

    print(f"{LOG_PREFIX} 🔍 Processing slash scan for coins: {coins_final} with EMA {ema_short}/{ema_long}")

    # Define all setups to check
    setups = [
        ("1h", "long"),
        ("1h", "short"),
        ("4h", "long"),
        ("4h", "short"),
    ]

    for coin in coins_final:
        print(f"{LOG_PREFIX} 📊 Scanning coin: {coin}")
        
        results = []
        for timeframe, direction in setups:
            setup_str = f"${coin} {timeframe}"
            if direction:
                setup_str += f" {direction}"
            
            # Append custom EMA values if not using defaults (13/21)
            if ema_short != 13 or ema_long != 21:
                setup_str += f" ema{ema_short} ema{ema_long}"
            
            def run_scan():
                symbol_norm = normalize_symbol(coin)
                if not pair_exists(symbol_norm):
                    return None
                result = generate_trade_plan(symbol_norm, timeframe, "bybit", forced_direction=direction, return_dict=True, ema_short=ema_short, ema_long=ema_long)
                return result, setup_str
            
            try:
                result_tuple = await bot.loop.run_in_executor(None, run_scan)
                if result_tuple is None:
                    print(f"{LOG_PREFIX} ❌ Pair not available: {coin}")
                    continue
                result, setup_str = result_tuple
                confidence = result.get('confidence', 0)
                results.append((confidence, setup_str, result))
                print(f"{LOG_PREFIX} ✅ Setup {setup_str}: confidence {confidence}%")
            except Exception as e:
                print(f"{LOG_PREFIX} ❌ Error scanning {setup_str}: {e}")
                continue
        
        if not results:
            await interaction.followup.send(f"⚠️ No valid results for {coin}. Pair may not exist.")
            continue
        
        # Find the best result (highest confidence)
        best_result = max(results, key=lambda x: x[0])
        best_confidence, best_setup, best_data = best_result
        
        # Extract timeframe from best setup (format: "$ COIN TIMEFRAME [DIRECTION]")
        best_timeframe = best_setup.split()[2]
        
        print(f"{LOG_PREFIX} 🏆 Best setup for {coin}: {best_setup} with {best_confidence}% confidence")
        
        # Generate chart for best result
        chart_buf = await bot.loop.run_in_executor(None, generate_chart_from_data, best_data, normalize_symbol(coin), best_timeframe)
        
        # Create embed with all confidences listed
        embed = create_scan_embed_from_dict(best_data, coin, best_timeframe, results)
        
        # Send response
        if chart_buf:
            file = discord.File(chart_buf, filename=f"scan_chart_{coin}_{best_timeframe}.png")
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)
        
        print(f"{LOG_PREFIX} ✅ Scan result sent for {coin}")

    print(f"{LOG_PREFIX} ✅ Slash scan command completed")

@tree.command(name="coinlist", description="List all available coins for trading signals")
async def slash_coinlist(interaction: discord.Interaction):
    print(f"{LOG_PREFIX} 📋 Slash coinlist command triggered by {interaction.user}")
    
    await interaction.response.defer()  # Defer for potential delay
    
    try:
        coins = await get_available_coins()
        if not coins:
            await interaction.followup.send("⚠️ No coins available at the moment. Try again later.")
            return
        
        # Split coins into chunks of 100 for pagination
        chunk_size = 100
        chunks = [coins[i:i + chunk_size] for i in range(0, len(coins), chunk_size)]
        
        view = CoinListView(chunks, len(coins))
        embed = view.get_embed()
        
        await interaction.followup.send(embed=embed, view=view)
        print(f"{LOG_PREFIX} ✅ Slash coinlist sent successfully ({len(coins)} coins in {len(chunks)} pages)")
    
    except Exception as e:
        print(f"{LOG_PREFIX} ❌ Slash coinlist command error: {e}")
        await interaction.followup.send(f"⚠️ Error fetching coin list: {e}")

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
