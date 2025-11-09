import os
import json
import logging
import aiohttp
from dotenv import load_dotenv

import config

# Load environment variables from .env file
load_dotenv()

log = logging.getLogger(config.LOG_NAME)

OPENAI_API_KEY = os.getenv(config.ENV_OPENAI_API_KEY)


async def openai_chat(session: aiohttp.ClientSession, user_message: str) -> str:
    """Send a chat message to OpenAI and return the response."""
    payload = {
        "model": config.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": config.OPENAI_SYSTEM_MESSAGE},
            {"role": "user", "content": user_message}
        ]
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    log.info(config.OPENAI_LOG_REQUEST, json.dumps(payload, ensure_ascii=False))
    async with session.post(config.OPENAI_CHAT_URL, headers=headers, json=payload, timeout=config.OPENAI_TIMEOUT) as resp:
        text = await resp.text()
        log.info(config.OPENAI_LOG_STATUS, resp.status, resp.reason)
        log.info(config.OPENAI_LOG_RESPONSE, text)
        if resp.status != 200:
            return config.OPENAI_ERROR_MESSAGE % (resp.status, resp.reason, text)
        data = json.loads(text)
        try:
            return data["choices"][0]["message"]["content"] or config.OPENAI_NO_CONTENT
        except Exception as e:
            log.exception(config.OPENAI_PARSE_EXCEPTION_LOG)
            return config.OPENAI_PARSE_ERROR % (e, text)
