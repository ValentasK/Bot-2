"""Configuration constants for the bot."""

# OpenAI Configuration
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

# Environment Variable Names
ENV_DISCORD_TOKEN = "DISCORD_TOKEN"
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_NAME = "bot"

# Discord Bot Configuration
COMMAND_PREFIX = "!"
BOT_STATUS_MESSAGE = "type !ai or !agent"

# Command Names
CMD_PING = "ping"
CMD_AI = "ai"
CMD_AGENT = "agent"

# Messages
MSG_DISCORD_TOKEN_MISSING = "DISCORD_TOKEN env var is missing."
MSG_OPENAI_KEY_MISSING = "OPENAI_API_KEY env var is missing."
MSG_LOGGED_IN = "✅ Logged in as %s (%s)"
MSG_BOT_SENT = "[Message] Bot sent: %s"
MSG_USER_MESSAGE = "[Message] %s: %s"
MSG_UNKNOWN_COMMAND = (
    "❓ Unknown command. Available commands:\n"
    "• `!ping` - Check if bot is alive\n"
    "• `!ai <question>` - Ask OpenAI a question\n"
    "• `!agent <task>` - Use AI agent with tools"
)
MSG_PING_RESPONSE = "pong"
MSG_AI_USAGE = "Usage: `!ai <your question>`"
MSG_AGENT_USAGE = "Usage: `!agent <do something>`"
MSG_USER_ASKED = "User %s asked: %s"
MSG_USER_REQUESTED_TASK = "User %s requested task: %s"
MSG_MISSING_ENV_VARS = "Missing required env vars. Set DISCORD_TOKEN and OPENAI_API_KEY."

# Bot Configuration
DISCORD_CHAR_LIMIT = 1900
MAX_AGENT_STEPS = 4

# OpenAI Chat Configuration
OPENAI_SYSTEM_MESSAGE = "You are a helpful assistant. Be concise."
OPENAI_TIMEOUT = 120
OPENAI_LOG_REQUEST = "[OpenAI] Request: %s"
OPENAI_LOG_STATUS = "[OpenAI] Status: %s %s"
OPENAI_LOG_RESPONSE = "[OpenAI] Raw response: %s"
OPENAI_ERROR_MESSAGE = "❌ OpenAI error: %s %s\n%s"
OPENAI_NO_CONTENT = "(no content)"
OPENAI_PARSE_ERROR = "⚠️ Failed to parse OpenAI response: %s\n%s"
OPENAI_PARSE_EXCEPTION_LOG = "Failed to parse OpenAI response"


