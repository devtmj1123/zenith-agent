"""Zenith-OS Telegram Bot — Connect Zenith agent to Telegram.

Setup:
1. Create a bot via @BotFather on Telegram
2. Get the bot token
3. Set TELEGRAM_BOT_TOKEN in .env file
4. Run: python -m app.telegram_bot

Features:
- Chat with Zenith via Telegram
- Supports text messages
- Streams responses back
- Handles multiple users with session isolation
"""
from __future__ import annotations
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict

# Add parent directory to path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

log = logging.getLogger(__name__)

# Telegram bot token from environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


class TelegramBot:
    """Telegram bot interface for Zenith-OS."""

    def __init__(self, agent):
        self.agent = agent
        self.sessions: Dict[str, str] = {}  # chat_id -> session_id
        self._app = None

    def _get_session(self, chat_id: int) -> str:
        """Get or create session for a chat."""
        chat_str = str(chat_id)
        if chat_str not in self.sessions:
            self.sessions[chat_str] = f"telegram_{chat_str}"
        return self.sessions[chat_str]

    async def start(self, token: str):
        """Start the Telegram bot."""
        try:
            from telegram import Update
            from telegram.ext import (
                Application,
                CommandHandler,
                MessageHandler,
                filters,
                ContextTypes,
            )
        except ImportError:
            log.error("python-telegram-bot not installed. Run: pip install python-telegram-bot")
            print("ERROR: python-telegram-bot not installed.")
            print("Run: pip install python-telegram-bot")
            return

        # Create application
        self._app = Application.builder().token(token).build()

        # Add handlers
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(CommandHandler("clear", self._cmd_clear))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        # Start polling
        log.info("telegram.bot_starting")
        print("\n  Zenith-OS Telegram Bot")
        print("  ======================")
        print(f"  Bot is running. Send /start to your bot on Telegram.")
        print("  Press Ctrl+C to stop.\n")

        await self._app.run_polling(drop_pending_updates=True)

    async def _cmd_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        """Handle /start command."""
        welcome = (
            "🤖 **Zenith-OS** is ready!\n\n"
            "I'm your personal AI agent. You can:\n"
            "• Ask me anything\n"
            "• Give me tasks to complete\n"
            "• Use /help for commands\n"
            "• Use /clear to reset conversation\n"
        )
        await update.message.reply_text(welcome, parse_mode="Markdown")

    async def _cmd_help(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        """Handle /help command."""
        help_text = (
            "📋 **Zenith-OS Commands**\n\n"
            "/start — Welcome message\n"
            "/help — Show this help\n"
            "/clear — Clear conversation history\n"
            "/status — Show agent status\n\n"
            "Just send a message to chat with Zenith!"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def _cmd_clear(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        """Handle /clear command — reset session."""
        chat_id = update.effective_chat.id
        chat_str = str(chat_id)
        if chat_str in self.sessions:
            del self.sessions[chat_str]
        await update.message.reply_text("✅ Conversation cleared.")

    async def _cmd_status(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        """Handle /status command."""
        status = (
            "🟢 **Zenith-OS Status**\n\n"
            f"• Sessions active: {len(self.sessions)}\n"
            f"• Agent: {'ready' if self.agent else 'not initialized'}\n"
        )
        await update.message.reply_text(status, parse_mode="Markdown")

    async def _handle_message(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        """Handle incoming text messages."""
        if not update.message or not update.message.text:
            return

        chat_id = update.effective_chat.id
        user_text = update.message.text
        session_id = self._get_session(chat_id)

        log.info("telegram.message", chat_id=chat_id, text=user_text[:100])

        # Send "typing" action
        await update.message.chat.send_action("typing")

        try:
            # Run agent
            state = await self.agent.run(user_text, session_id=session_id)
            response = state.final_response or "I processed your request but have no response."

            # Split long messages (Telegram limit is 4096 chars)
            for i in range(0, len(response), 4000):
                chunk = response[i:i + 4000]
                await update.message.reply_text(chunk)

        except Exception as e:
            log.error("telegram.message_error", error=str(e))
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


def run_async(coro):
    """Run async function synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def main():
    """Launch Zenith-OS Telegram bot."""
    import argparse

    # Load .env
    env_file = _root / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

    parser = argparse.ArgumentParser(description="Zenith-OS Telegram Bot")
    parser.add_argument("--token", default="", help="Telegram bot token (or set TELEGRAM_BOT_TOKEN env)")
    args = parser.parse_args()

    token = args.token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("ERROR: No Telegram bot token provided.")
        print("Options:")
        print("  1. Set TELEGRAM_BOT_TOKEN in .env file")
        print("  2. Run: python -m app.telegram_bot --token YOUR_TOKEN")
        print("\nTo get a token: message @BotFather on Telegram")
        return 1

    # Build agent
    from config.settings import Settings
    from main import build_agent

    settings = Settings()
    settings.load_from_env()

    print("  Initializing Zenith agent...")
    agent = build_agent(settings, on_event=lambda e: None)
    print("  Agent ready.")

    # Start bot
    bot = TelegramBot(agent)
    run_async(bot.start(token))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
