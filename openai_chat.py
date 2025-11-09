import os
import json
import logging
import aiohttp
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

log = logging.getLogger("bot")

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"  # change if you prefer another model
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


async def openai_chat(session: aiohttp.ClientSession, user_message: str) -> str:
    """
    Minimal call to OpenAI Chat Completions with strong logging.
    """
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Be concise."},
            {"role": "user", "content": user_message}
        ]
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    log.info("[OpenAI] Request: %s", json.dumps(payload, ensure_ascii=False))
    async with session.post(OPENAI_CHAT_URL, headers=headers, json=payload, timeout=120) as resp:
        text = await resp.text()
        log.info("[OpenAI] Status: %s %s", resp.status, resp.reason)
        log.info("[OpenAI] Raw response: %s", text)
        if resp.status != 200:
            return f"❌ OpenAI error: {resp.status} {resp.reason}\n{text}"
        data = json.loads(text)
        try:
            return data["choices"][0]["message"]["content"] or "(no content)"
        except Exception as e:
            log.exception("Failed to parse OpenAI response")
            return f"⚠️ Failed to parse OpenAI response: {e}\n{text}"
