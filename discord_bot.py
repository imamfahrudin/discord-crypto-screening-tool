import discord
from discord.ext import commands
import json
import os
import traceback
from datetime import datetime
import re
from dotenv import load_dotenv
from signal_logic import generate_trade_plan
from bybit_data import normalize_symbol, get_all_pairs
from ws_prices import start_ws_in_background, PRICES
from utils import calculate_rr, format_price_dynamic

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
    print(f"✅ Bot connected as {bot.user}")
    print("⏳ Loading pair cache from Bybit API...")
    try:
        if not get_all_pairs(force_refresh=True):
            print("⚠️ WARNING: Failed to load any trading pairs from Bybit API.")
        else:
            print(f"✅ Successfully loaded {len(get_all_pairs())} trading pairs.")
    except Exception as e:
        print(f"❌ CRITICAL ERROR while fetching pairs: {e}")

    start_ws_in_background(url=WS_URL, symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

# ============================
# Helper for embed formatting
# ============================
def safe_float(v):
    try:
        return float(v)
    except Exception:
        return None

# Create embed (insight hidden)
def create_signal_embed(plan_string: str, symbol: str, timeframe: str):
    data = {}
    try:
        lines = plan_string.split('\n')
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                data[key.strip()] = value.strip().replace('**', '')

        insight_match = re.search(r'INSIGHT_START\n(.*?)\nINSIGHT_END', plan_string, re.DOTALL)
        data['INSIGHT'] = insight_match.group(1).strip() if insight_match else ''
    except Exception as e:
        return discord.Embed(title="❌ Parsing Error", description=f"Gagal memproses sinyal: {e}", color=0xFF0000)

    s_upper = data.get('DIRECTION', 'NETRAL')
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

    # color & emoji
    if s_upper == "LONG":
        color = 0x00FF88; emoji = "🟢"
    elif s_upper == "SHORT":
        color = 0xFF5555; emoji = "🔴"
    else:
        color = 0xFFD700; emoji = "🟡"

    interval_map = {
        "1m":"1","3m":"3","5m":"5","15m":"15","30m":"30",
        "1h":"60","2h":"120","4h":"240","6h":"360",
        "1d":"1D","1w":"1W","1M":"1M"
    }
    interval = interval_map.get(timeframe.lower(), "1D")
    tv_url = f"https://www.tradingview.com/chart/?symbol={data.get('EXCHANGE','BYBIT')}:{symbol}&interval={interval}"

    # NETRAL
    if s_upper == "NETRAL":
        title = f"{emoji} {symbol} — {timeframe.upper()} NETRAL"
        description = (
            f"**Analisis:** Pasar konsolidasi atau kriteria FVG/Momentum tidak terpenuhi.\n"
            f"🕒 **Timeframe:** `{timeframe.upper()}`\n"
            f"🧭 **Time:** `{current_time}`\n\n"
            f"🔗 [📈 Open Chart on TradingView]({tv_url})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        # safe format
        tp1_fmt = format_price_dynamic(safe_float(data.get('TP1'))) if safe_float(data.get('TP1')) is not None else 'N/A'
        tp2_fmt = format_price_dynamic(safe_float(data.get('TP2'))) if safe_float(data.get('TP2')) is not None else 'N/A'
        rr_fmt = f"{safe_float(data.get('RR')):.2f}R" if safe_float(data.get('RR')) is not None else "N/A"
        confidence = data.get('CONFIDENCE', '')
        entry_fmt = format_price_dynamic(safe_float(data.get('ENTRY'))) if safe_float(data.get('ENTRY')) is not None else '-'
        sl_fmt = format_price_dynamic(safe_float(data.get('SL'))) if safe_float(data.get('SL')) is not None else '-'

        title = f"{BOT_TITLE_PREFIX} {s_upper} {symbol}"
        description = (
            f"📊 **PAIR:** `{symbol}`\n"
            f"🕒 **TIMEFRAME:** `{timeframe.upper()}`\n"
            f"🧭 **Time:** `{current_time}`\n\n"
            f"📈 **ENTRY:** `{entry_fmt}`\n"
            f"🛑 **STOP LOSS:** `{sl_fmt}`\n"
            f"🎯 **TAKE PROFIT (Target Likuiditas):**\n"
            f"> TP Awal (1.5R) → `{tp1_fmt}`\n"
            f"**🏆 TP Final →** `{tp2_fmt}` **({rr_fmt})**\n\n"
            f"💡 **CONFIDENCE:** {confidence}\n\n"
            # Insight intentionally hidden (for internal use only)
            f"🔗 [📈 Open Chart on TradingView]({tv_url})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

    embed = discord.Embed(title=title, description=description, color=color)
    last_price_fmt = format_price_dynamic(safe_float(data.get('LAST_PRICE'))) if safe_float(data.get('LAST_PRICE')) is not None else '-'
    embed.set_footer(text=f"{BOT_FOOTER_NAME} • Last Price: {last_price_fmt} | Generated: {current_time}")
    return embed

# ============================
# Commands
# ============================
@bot.command(name="signal")
async def signal_command(ctx, symbol: str, timeframe: str, direction: str = None, exchange: str = "bybit"):
    """
    Usage:
      !signal BTC 1h
      !signal BTC 1h long
      !signal BTC 1h short
    direction is optional; if provided must be 'long' or 'short'.
    """
    valid_tfs = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']
    if timeframe.lower() not in [t.lower() for t in valid_tfs]:
        await ctx.send(f"⚠️ Invalid timeframe `{timeframe}`. Pilih dari {valid_tfs}.")
        return

    forced = None
    if direction:
        dir_norm = direction.strip().lower()
        if dir_norm not in ('long','short'):
            await ctx.send("⚠️ Jika menambahkan direction, gunakan `long` atau `short`.")
            return
        forced = dir_norm

    def run_blocking_calls():
        symbol_norm = normalize_symbol(symbol)
        if symbol_norm not in get_all_pairs():
            get_all_pairs(force_refresh=True)
        if symbol_norm not in get_all_pairs():
            return f"❌ Pair `{symbol_norm}` not available on Bybit Futures."
        # pass forced_direction to generate_trade_plan
        return generate_trade_plan(symbol_norm, timeframe, exchange, forced_direction=forced)

    try:
        plan_string = await bot.loop.run_in_executor(None, run_blocking_calls)
        if isinstance(plan_string, str) and plan_string.startswith("❌ Pair"):
            await ctx.send(plan_string)
            return

        embed = create_signal_embed(plan_string, normalize_symbol(symbol), timeframe)
        await ctx.send(embed=embed)
    except ValueError as e:
        await ctx.send(f"⚠️ Error in input/data: `{e}`")
    except Exception as e:
        tb = traceback.format_exc()
        await ctx.send(f"⚠️ Error generating signal. Cek log terminal: `{e}`")
        print(tb)

# ============================
# Slash Commands
# ============================
@tree.command(name="help", description="Tampilkan perintah yang tersedia dan informasi penggunaan")
async def slash_help(interaction: discord.Interaction):
    """Tampilkan perintah yang tersedia dan informasi penggunaan"""
    embed = discord.Embed(
        title="🤖📈 Crypto Signal Bot - Perintah",
        description="Bot sinyal trading cryptocurrency dengan analisis teknikal RSI dan EMA",
        color=0x00ff00
    )

    embed.add_field(
        name="📊 **Perintah Sinyal Trading**",
        value=(
            "**/signal** - Generate sinyal trading (dengan dropdown untuk timeframe & arah)\n"
            "**!signal {coin} {timeframe}** - Cek sinyal umum (long dan short)\n"
            "**!signal {coin} {timeframe} {long/short}** - Cek sinyal spesifik arah"
        ),
        inline=False
    )

    embed.add_field(
        name="⏰ **Timeframe yang Didukung**",
        value="1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 1d, 1w, 1M",
        inline=False
    )

    embed.add_field(
        name="💡 **Contoh Penggunaan**",
        value=(
            "**!signal BTC 1h** - Cek sinyal BTC/USDT 1 jam\n"
            "**!signal ETH 4h long** - Cek sinyal long ETH/USDT 4 jam\n"
            "**!signal SOL 1d short** - Cek sinyal short SOL/USDT harian\n"
            "**/signal** - Gunakan perintah slash interaktif"
        ),
        inline=False
    )

    embed.add_field(
        name="📋 **Parameter yang Didukung**",
        value=(
            "**COIN**: Simbol cryptocurrency (BTC, ETH, SOL, dll.)\n"
            "**TIMEFRAME**: Periode analisis (lihat di atas)\n"
            "**DIRECTION**: long atau short (opsional)"
        ),
        inline=False
    )

    embed.set_footer(text="Data dari Bybit • Menggunakan indikator RSI & EMA • Bot untuk tujuan edukasi")

    try:
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        print(f"Help command failed: {e}")
        # Fallback: send directly to channel
        await interaction.channel.send(embed=embed)

@tree.command(name="signal", description="Generate crypto trading signal")
@discord.app_commands.describe(
    symbol="Trading pair symbol (e.g., BTCUSDT)",
    timeframe="Timeframe for the signal",
    direction="Optional direction: long or short"
)
@discord.app_commands.choices(timeframe=[
    discord.app_commands.Choice(name="1m", value="1m"),
    discord.app_commands.Choice(name="3m", value="3m"),
    discord.app_commands.Choice(name="5m", value="5m"),
    discord.app_commands.Choice(name="15m", value="15m"),
    discord.app_commands.Choice(name="30m", value="30m"),
    discord.app_commands.Choice(name="1h", value="1h"),
    discord.app_commands.Choice(name="2h", value="2h"),
    discord.app_commands.Choice(name="4h", value="4h"),
    discord.app_commands.Choice(name="6h", value="6h"),
    discord.app_commands.Choice(name="1d", value="1d"),
    discord.app_commands.Choice(name="1w", value="1w"),
    discord.app_commands.Choice(name="1M", value="1M")
])
@discord.app_commands.choices(direction=[
    discord.app_commands.Choice(name="Long", value="long"),
    discord.app_commands.Choice(name="Short", value="short")
])
async def slash_signal(interaction: discord.Interaction, symbol: str, timeframe: str, direction: str = None):
    await interaction.response.defer()

    valid_tfs = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','1d','1w','1M']
    if timeframe.lower() not in [t.lower() for t in valid_tfs]:
        await interaction.followup.send(f"⚠️ Invalid timeframe `{timeframe}`. Pilih dari {valid_tfs}.")
        return

    forced = None
    if direction:
        dir_norm = direction.strip().lower()
        if dir_norm not in ('long','short'):
            await interaction.followup.send("⚠️ Jika menambahkan direction, gunakan `long` atau `short`.")
            return
        forced = dir_norm

    def run_blocking_calls():
        symbol_norm = normalize_symbol(symbol)
        if symbol_norm not in get_all_pairs():
            get_all_pairs(force_refresh=True)
        if symbol_norm not in get_all_pairs():
            return f"❌ Pair `{symbol_norm}` not available on Bybit Futures."
        # pass forced_direction to generate_trade_plan
        return generate_trade_plan(symbol_norm, timeframe, "bybit", forced_direction=forced)

    try:
        plan_string = await bot.loop.run_in_executor(None, run_blocking_calls)
        if isinstance(plan_string, str) and plan_string.startswith("❌ Pair"):
            await interaction.followup.send(plan_string)
            return

        embed = create_signal_embed(plan_string, normalize_symbol(symbol), timeframe)
        await interaction.followup.send(embed=embed)
    except ValueError as e:
        await interaction.followup.send(f"⚠️ Error in input/data: `{e}`")
    except Exception as e:
        tb = traceback.format_exc()
        await interaction.followup.send(f"⚠️ Error generating signal. Cek log terminal: `{e}`")
        print(tb)

# ============================
# Start bot
# ============================
if __name__ == "__main__":
    if not TOKEN or TOKEN == "YOUR_NEW_DISCORD_TOKEN":
        print("ERROR: Please set your Discord token in config.json or DISCORD_TOKEN environment variable.")
    else:
        bot.run(TOKEN)
