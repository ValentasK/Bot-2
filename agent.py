import os
import json
import time
import logging
import aiohttp
from datetime import datetime, timezone
from dotenv import load_dotenv

from config import OPENAI_CHAT_URL, OPENAI_MODEL

# Load environment variables from .env file
load_dotenv()

log = logging.getLogger("bot")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


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
