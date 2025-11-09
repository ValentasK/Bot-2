import os
import json
import time
import logging
import aiohttp
from datetime import datetime, timezone

import discord
from discord.ext import commands
from dotenv import load_dotenv

from openai_chat import openai_chat

# Load environment variables from .env file
load_dotenv()

# ------------- CONFIG & LOGGING -------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"  # change if you prefer another model

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

# ------------- AGENT: TOOLS -------------
async def tool_get_time(_: dict) -> str:
    """Return current UTC time in ISO-8601."""
    now = datetime.now(timezone.utc).isoformat()
    return now

async def tool_http_get(args: dict) -> str:
    """HTTP GET a URL and return text (first 10k chars)."""
    url = args.get("url", "")
    if not (url.startswith("http://") or url.startswith("https://")):
        return "ToolError: invalid URL"
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url) as r:
                txt = await r.text()
                return txt[:10000]  # cap to avoid huge payloads
    except Exception as e:
        return f"ToolError: {e}"

# registry
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Return the current UTC time as ISO-8601 string.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "HTTP GET a URL and return text. Use for public pages only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL to fetch (https://…)"}
                },
                "required": ["url"]
            }
        },
    },
]

async def dispatch_tool(name: str, arguments_json: str) -> str:
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except Exception as e:
        return f"ToolError: invalid JSON args: {e}"

    log.info("[Agent] Executing tool: %s args=%s", name, args)
    if name == "get_time":
        return await tool_get_time(args)
    if name == "http_get":
        return await tool_http_get(args)
    return f"ToolError: unknown tool {name}"

# ------------- AGENT LOOP (plan → act → observe) -------------
async def openai_agent(session: aiohttp.ClientSession, user_message: str, max_steps: int = 4) -> str:
    """
    A small agent loop using OpenAI tool calling.
    - Sends messages+tools to the model
    - Executes requested tools
    - Feeds results back
    - Stops when there are no more tool calls or step limit is reached
    """
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    messages = [
        {"role": "system", "content": "You are an efficient assistant. Use tools only when needed. Be brief."},
        {"role": "user", "content": user_message},
    ]

    for step in range(1, max_steps + 1):
        payload = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto"
        }

        log.info("[Agent] STEP %d → OpenAI request", step)
        log.info("[Agent] Payload: %s", json.dumps(payload, ensure_ascii=False))
        t0 = time.time()
        async with session.post(OPENAI_CHAT_URL, headers=headers, json=payload, timeout=180) as resp:
            body = await resp.text()
            log.info("[Agent] OpenAI status: %s %s", resp.status, resp.reason)
            log.info("[Agent] OpenAI response: %s", body)
            if resp.status != 200:
                return f"❌ OpenAI error: {resp.status} {resp.reason}\n{body}"

        try:
            data = json.loads(body)
            msg = data["choices"][0]["message"]
        except Exception as e:
            log.exception("[Agent] Failed to parse OpenAI response")
            return f"⚠️ Failed to parse OpenAI response: {e}\n{body}"

        # Tool calls?
        tool_calls = msg.get("tool_calls")
        assistant_content = msg.get("content")
        messages.append({"role": "assistant", "content": assistant_content, "tool_calls": tool_calls})

        if tool_calls:
            # Execute each tool call and push results as tool messages
            for tc in tool_calls:
                tc_id = tc.get("id")
                name = tc.get("function", {}).get("name")
                args_json = tc.get("function", {}).get("arguments", "{}")
                log.info("[Agent] Tool call id=%s name=%s args=%s", tc_id, name, args_json)
                result = await dispatch_tool(name, args_json)
                messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})
            # continue loop, letting the model observe results
            log.info("[Agent] Step %d completed in %.2fs, continuing…", step, time.time() - t0)
            continue

        # No tool calls → final answer
        final = assistant_content or "(no content)"
        log.info("[Agent] Final answer in %.2fs", time.time() - t0)
        return final

    return "⚠️ Reached step limit without a final answer."

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
