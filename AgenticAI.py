import os
import logging
import aiohttp

import discord
from discord.ext import commands
from dotenv import load_dotenv

from openai_chat import openai_chat
from agent import openai_agent
import config

# Load environment variables from .env file
load_dotenv()

# ------------- CONFIG & LOGGING -------------
DISCORD_TOKEN = os.getenv(config.ENV_DISCORD_TOKEN)
OPENAI_API_KEY = os.getenv(config.ENV_OPENAI_API_KEY)

logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
)
log = logging.getLogger(config.LOG_NAME)

if not DISCORD_TOKEN:
    log.error(config.MSG_DISCORD_TOKEN_MISSING)
if not OPENAI_API_KEY:
    log.error(config.MSG_OPENAI_KEY_MISSING)

# ------------- DISCORD BOT SETUP -------------
intents = discord.Intents.default()
intents.message_content = True  # IMPORTANT: enable Message Content Intent in the Developer Portal too
bot = commands.Bot(command_prefix=config.COMMAND_PREFIX, intents=intents)

# ------------- DISCORD COMMANDS -------------
@bot.event
async def on_ready():
    log.info(config.MSG_LOGGED_IN, bot.user, bot.user.id)
    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Game(config.BOT_STATUS_MESSAGE)
        )
    except Exception:
        pass

@bot.event
async def on_message(message: discord.Message):
    # Log every message the bot sees
    if message.author == bot.user:
        log.info(config.MSG_BOT_SENT, message.content)
    else:
        log.info(config.MSG_USER_MESSAGE, message.author, message.content)
    
    # If message starts with ! but is not a valid command, provide help
    if message.content.startswith(config.COMMAND_PREFIX) and not message.author.bot:
        command = message.content.split()[0].lower()
        valid_commands = [f"{config.COMMAND_PREFIX}{config.CMD_PING}", f"{config.COMMAND_PREFIX}{config.CMD_AI}", f"{config.COMMAND_PREFIX}{config.CMD_AGENT}"]
        if command not in valid_commands:
            await message.channel.send(config.MSG_UNKNOWN_COMMAND)
            return
    
    # Process commands (important: without this, commands won't work)
    await bot.process_commands(message)

@bot.command(name=config.CMD_PING)
async def ping(ctx: commands.Context):
    await ctx.send(config.MSG_PING_RESPONSE)

@bot.command(name=config.CMD_AI)
async def ai(ctx: commands.Context, *, prompt: str = ""):
    if not prompt:
        await ctx.send(config.MSG_AI_USAGE)
        return
    log.info(config.MSG_USER_ASKED, ctx.author, prompt)
    await ctx.channel.typing()
    async with aiohttp.ClientSession() as session:
        reply = await openai_chat(session, prompt)
    # Respect Discord 2000-char limit
    if len(reply) > config.DISCORD_CHAR_LIMIT:
        reply = reply[:config.DISCORD_CHAR_LIMIT] + "…"
    await ctx.send(reply)

@bot.command(name=config.CMD_AGENT)
async def agent(ctx: commands.Context, *, task: str = ""):
    if not task:
        await ctx.send(config.MSG_AGENT_USAGE)
        return
    log.info(config.MSG_USER_REQUESTED_TASK, ctx.author, task)
    await ctx.channel.typing()
    async with aiohttp.ClientSession() as session:
        reply = await openai_agent(session, task, max_steps=config.MAX_AGENT_STEPS)
    if len(reply) > config.DISCORD_CHAR_LIMIT:
        reply = reply[:config.DISCORD_CHAR_LIMIT] + "…"
    await ctx.send(reply)

# ------------- ENTRY POINT -------------
def main():
    if not DISCORD_TOKEN or not OPENAI_API_KEY:
        log.error(config.MSG_MISSING_ENV_VARS)
        return
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
