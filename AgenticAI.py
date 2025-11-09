import os
import logging
import aiohttp

import discord
from discord.ext import commands
from dotenv import load_dotenv

from openai_chat import openai_chat
from agent import openai_agent

# Load environment variables from .env file
load_dotenv()

# ------------- CONFIG & LOGGING -------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("bot")

if not DISCORD_TOKEN:
    log.error("DISCORD_TOKEN env var is missing.")
if not OPENAI_API_KEY:
    log.error("OPENAI_API_KEY env var is missing.")

# ------------- DISCORD BOT SETUP -------------
intents = discord.Intents.default()
intents.message_content = True  # IMPORTANT: enable Message Content Intent in the Developer Portal too
bot = commands.Bot(command_prefix="!", intents=intents)

# ------------- DISCORD COMMANDS -------------
@bot.event
async def on_ready():
    log.info("✅ Logged in as %s (%s)", bot.user, bot.user.id)
    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Game("type !ai or !agent")
        )
    except Exception:
        pass

@bot.event
async def on_message(message: discord.Message):
    # Log every message the bot sees
    if message.author == bot.user:
        log.info("[Message] Bot sent: %s", message.content)
    else:
        log.info("[Message] %s: %s", message.author, message.content)
    
    # If message starts with ! but is not a valid command, provide help
    if message.content.startswith("!") and not message.author.bot:
        command = message.content.split()[0].lower()
        valid_commands = ["!ping", "!ai", "!agent"]
        if command not in valid_commands:
            await message.channel.send(
                "❓ Unknown command. Available commands:\n"
                "• `!ping` - Check if bot is alive\n"
                "• `!ai <question>` - Ask OpenAI a question\n"
                "• `!agent <task>` - Use AI agent with tools"
            )
            return
    
    # Process commands (important: without this, commands won't work)
    await bot.process_commands(message)

@bot.command(name="ping")
async def ping(ctx: commands.Context):
    await ctx.send("pong")

@bot.command(name="ai")
async def ai(ctx: commands.Context, *, prompt: str = ""):
    if not prompt:
        await ctx.send("Usage: `!ai <your question>`")
        return
    log.info("User %s asked: %s", ctx.author, prompt)
    await ctx.channel.typing()
    async with aiohttp.ClientSession() as session:
        reply = await openai_chat(session, prompt)
    # Respect Discord 2000-char limit
    if len(reply) > 1900:
        reply = reply[:1900] + "…"
    await ctx.send(reply)

@bot.command(name="agent")
async def agent(ctx: commands.Context, *, task: str = ""):
    if not task:
        await ctx.send("Usage: `!agent <do something>`")
        return
    log.info("User %s requested task: %s", ctx.author, task)
    await ctx.channel.typing()
    async with aiohttp.ClientSession() as session:
        reply = await openai_agent(session, task, max_steps=4)
    if len(reply) > 1900:
        reply = reply[:1900] + "…"
    await ctx.send(reply)

# ------------- ENTRY POINT -------------
def main():
    if not DISCORD_TOKEN or not OPENAI_API_KEY:
        log.error("Missing required env vars. Set DISCORD_TOKEN and OPENAI_API_KEY.")
        return
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
