import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional, Dict, Any
from collections import deque

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError, RetryAfter, TimedOut

from hummingbot.notifier.notifier_base import NotifierBase
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

# Rate limiting configuration
MAX_MESSAGES_PER_MINUTE = 20
MAX_MESSAGES_PER_SECOND = 3

# Sensitive commands that should not be executed via Telegram
BLOCKED_COMMANDS = {
    "connect", "create", "import", "export", "exit", "kill_switch",
    "config", "gateway", "paper_trade", "balance_limit"
}


class TelegramNotifier(NotifierBase):
    """
    Telegram integration for Hummingbot.

    Features:
    - Real-time notifications for bot events
    - Command execution via Telegram
    - Secure authentication
    - Rate limiting and message queue management
    - Markdown formatting and inline buttons
    """

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, hb_app: "HummingbotApplication", token: str, chat_id: str):
        super().__init__()
        self._hb_app = hb_app
        self._token = token
        self._chat_id = chat_id
        self._application: Optional[Application] = None
        self._is_running = False

        # Rate limiting
        self._message_times: deque = deque(maxlen=MAX_MESSAGES_PER_MINUTE)
        self._last_message_time = 0

        # Command cooldown to prevent spam
        self._last_command_time: Dict[str, float] = {}
        self._command_cooldown = 2.0  # seconds

        # Configure pandas for Telegram display limits
        self._configure_pandas_display()

        self.logger().info("TelegramNotifier initialized")

    def _configure_pandas_display(self):
        """Configure pandas display options for Telegram's character limits."""
        try:
            import pandas as pd
            pd.set_option('display.max_rows', 50)
            pd.set_option('display.max_columns', 10)
            pd.set_option('display.width', 100)
            pd.set_option('display.max_colwidth', 30)
        except Exception as e:
            self.logger().warning(f"Failed to configure pandas display: {str(e)}")

    async def _initialize_application(self):
        """Initialize the Telegram bot application."""
        try:
            # Create application
            self._application = Application.builder().token(self._token).build()

            # Register command handlers
            self._application.add_handler(CommandHandler("start", self._handle_start))
            self._application.add_handler(CommandHandler("help", self._handle_help))
            self._application.add_handler(CommandHandler("status", self._handle_status))
            self._application.add_handler(CommandHandler("history", self._handle_history))
            self._application.add_handler(CommandHandler("config", self._handle_config))
            self._application.add_handler(CommandHandler("balance", self._handle_balance))
            self._application.add_handler(CommandHandler("pnl", self._handle_pnl))
            self._application.add_handler(CommandHandler("startbot", self._handle_start_bot))
            self._application.add_handler(CommandHandler("stopbot", self._handle_stop_bot))

            # Register callback query handler for inline buttons
            self._application.add_handler(CallbackQueryHandler(self._handle_button))

            # Register message handler for unknown commands
            self._application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

            # Initialize and start polling
            await self._application.initialize()
            await self._application.start()
            await self._application.updater.start_polling(drop_pending_updates=True)

            self.logger().info("Telegram bot application started successfully")
            return True

        except Exception as e:
            self.logger().error(f"Failed to initialize Telegram application: {str(e)}")
            return False

    def start(self):
        """Start the Telegram notifier."""
        super().start()
        self._is_running = True
        # Schedule the initialization in the event loop
        asyncio.create_task(self._start_application())

    async def _start_application(self):
        """Start the Telegram application."""
        success = await self._initialize_application()
        if success:
            # Send startup message
            await self._send_message_direct(
                "🤖 *Hummingbot Connected*\n\n"
                "Your bot is now connected to Telegram.\n"
                "Use /help to see available commands.",
                parse_mode=ParseMode.MARKDOWN
            )

    def stop(self):
        """Stop the Telegram notifier."""
        super().stop()
        self._is_running = False
        if self._application:
            asyncio.create_task(self._stop_application())

    async def _stop_application(self):
        """Stop the Telegram application."""
        try:
            await self._send_message_direct("🛑 *Hummingbot Disconnected*", parse_mode=ParseMode.MARKDOWN)
            if self._application:
                await self._application.updater.stop()
                await self._application.stop()
                await self._application.shutdown()
            self.logger().info("Telegram bot application stopped successfully")
        except Exception as e:
            self.logger().error(f"Error stopping Telegram application: {str(e)}")

    async def _send_message(self, message: str):
        """
        Send a message to Telegram with rate limiting.
        This is called by the base class queue processor.
        """
        await self._send_message_direct(message, parse_mode=ParseMode.MARKDOWN)

    async def _send_message_direct(self, message: str, parse_mode: Optional[str] = None, reply_markup=None):
        """
        Send a message directly to Telegram with rate limiting and retry logic.
        """
        if not self._application or not self._is_running:
            return

        # Rate limiting check
        if not self._check_rate_limit():
            self.logger().warning("Rate limit exceeded, queueing message")
            await asyncio.sleep(1.0)
            return await self._send_message_direct(message, parse_mode, reply_markup)

        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Telegram has a 4096 character limit per message
                if len(message) > 4096:
                    # Split message into chunks
                    chunks = [message[i:i+4096] for i in range(0, len(message), 4096)]
                    for chunk in chunks:
                        await self._application.bot.send_message(
                            chat_id=self._chat_id,
                            text=chunk,
                            parse_mode=parse_mode,
                            reply_markup=reply_markup
                        )
                        await asyncio.sleep(0.5)  # Small delay between chunks
                else:
                    await self._application.bot.send_message(
                        chat_id=self._chat_id,
                        text=message,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup
                    )

                self._record_message_time()
                return

            except RetryAfter as e:
                # Telegram rate limiting
                wait_time = e.retry_after
                self.logger().warning(f"Telegram rate limit hit, waiting {wait_time} seconds")
                await asyncio.sleep(wait_time)
                retry_count += 1

            except TimedOut:
                self.logger().warning(f"Telegram request timed out, retrying ({retry_count + 1}/{max_retries})")
                await asyncio.sleep(2)
                retry_count += 1

            except TelegramError as e:
                self.logger().error(f"Telegram error: {str(e)}")
                if retry_count < max_retries - 1:
                    await asyncio.sleep(1)
                    retry_count += 1
                else:
                    break

            except Exception as e:
                self.logger().error(f"Unexpected error sending Telegram message: {str(e)}")
                break

    def _is_command_allowed(self, command: str) -> bool:
        """Check if a command is allowed to be executed via Telegram."""
        # Extract base command (without arguments)
        base_command = command.split()[0] if command else ""
        return base_command.lower() not in BLOCKED_COMMANDS

    async def _execute_command_safe(self, command: str) -> str:
        """
        Execute a command safely within the application's event loop.
        This ensures commands are executed in the correct async context.
        """
        try:
            # Check if command is allowed
            if not self._is_command_allowed(command):
                return f"⚠️ Command '{command}' is not allowed via Telegram for security reasons."

            # Schedule command execution in the app's event loop
            if hasattr(self._hb_app, 'ev_loop'):
                # Execute in the main event loop
                future = asyncio.run_coroutine_threadsafe(
                    self._execute_command_async(command),
                    self._hb_app.ev_loop
                )
                return future.result(timeout=10.0)
            else:
                # Fallback to direct execution
                return await self._execute_command_async(command)

        except asyncio.TimeoutError:
            return "⏱️ Command execution timed out."
        except Exception as e:
            self.logger().error(f"Error executing command '{command}': {str(e)}")
            return f"❌ Error executing command: {str(e)}"

    async def _execute_command_async(self, command: str) -> str:
        """Execute the command and capture output."""
        try:
            # Execute command through HummingbotApplication
            self._hb_app._handle_command(command)
            return f"✅ Command '{command}' executed successfully."
        except Exception as e:
            raise Exception(f"Command execution failed: {str(e)}")

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        current_time = time.time()

        # Check messages per second
        if current_time - self._last_message_time < (1.0 / MAX_MESSAGES_PER_SECOND):
            return False

        # Check messages per minute
        minute_ago = current_time - 60
        while self._message_times and self._message_times[0] < minute_ago:
            self._message_times.popleft()

        return len(self._message_times) < MAX_MESSAGES_PER_MINUTE

    def _record_message_time(self):
        """Record the time of a sent message for rate limiting."""
        current_time = time.time()
        self._message_times.append(current_time)
        self._last_message_time = current_time

    def _check_command_cooldown(self, command: str) -> bool:
        """Check if command is on cooldown."""
        current_time = time.time()
        last_time = self._last_command_time.get(command, 0)

        if current_time - last_time < self._command_cooldown:
            return False

        self._last_command_time[command] = current_time
        return True

    def _verify_chat_id(self, update: Update) -> bool:
        """Verify that the message comes from the authorized chat."""
        if str(update.effective_chat.id) != self._chat_id:
            self.logger().warning(f"Unauthorized access attempt from chat_id: {update.effective_chat.id}")
            return False
        return True

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self._verify_chat_id(update):
            return

        keyboard = [
            [
                InlineKeyboardButton("📊 Status", callback_data="status"),
                InlineKeyboardButton("💰 Balance", callback_data="balance"),
            ],
            [
                InlineKeyboardButton("📈 PnL", callback_data="pnl"),
                InlineKeyboardButton("📜 History", callback_data="history"),
            ],
            [
                InlineKeyboardButton("▶️ Start Bot", callback_data="startbot"),
                InlineKeyboardButton("⏹️ Stop Bot", callback_data="stopbot"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = (
            "🤖 *Welcome to Hummingbot!*\n\n"
            "Use the buttons below or these commands:\n\n"
            "📊 /status - Bot status\n"
            "💰 /balance - Account balances\n"
            "📈 /pnl - Profit & Loss\n"
            "📜 /history - Trade history\n"
            "⚙️ /config - Show configuration\n"
            "▶️ /startbot - Start trading\n"
            "⏹️ /stopbot - Stop trading\n"
            "❓ /help - Show this help"
        )

        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not self._verify_chat_id(update):
            return
        await self._handle_start(update, context)

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        if not self._verify_chat_id(update):
            return

        if not self._check_command_cooldown("status"):
            await update.message.reply_text("⏳ Please wait before using this command again.")
            return

        try:
            result = await self._execute_command_safe("status")
            await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            self.logger().error(f"Error getting status: {str(e)}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _handle_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command."""
        if not self._verify_chat_id(update):
            return

        if not self._check_command_cooldown("history"):
            await update.message.reply_text("⏳ Please wait before using this command again.")
            return

        try:
            result = await self._execute_command_safe("history")
            await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            self.logger().error(f"Error getting history: {str(e)}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _handle_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /config command."""
        if not self._verify_chat_id(update):
            return

        if not self._check_command_cooldown("config"):
            await update.message.reply_text("⏳ Please wait before using this command again.")
            return

        try:
            # Get current config info
            if self._hb_app.strategy_name:
                config_msg = f"📋 *Current Configuration*\n\n"
                config_msg += f"Strategy: `{self._hb_app.strategy_name}`\n"
                await update.message.reply_text(config_msg, parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text("No strategy loaded")
        except Exception as e:
            self.logger().error(f"Error getting config: {str(e)}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _handle_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command."""
        if not self._verify_chat_id(update):
            return

        if not self._check_command_cooldown("balance"):
            await update.message.reply_text("⏳ Please wait before using this command again.")
            return

        try:
            result = await self._execute_command_safe("balance")
            await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            self.logger().error(f"Error getting balance: {str(e)}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _handle_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pnl command."""
        if not self._verify_chat_id(update):
            return

        if not self._check_command_cooldown("pnl"):
            await update.message.reply_text("⏳ Please wait before using this command again.")
            return

        try:
            result = await self._execute_command_safe("pnl")
            await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            self.logger().error(f"Error getting pnl: {str(e)}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _handle_start_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /startbot command."""
        if not self._verify_chat_id(update):
            return

        if not self._check_command_cooldown("startbot"):
            await update.message.reply_text("⏳ Please wait before using this command again.")
            return

        try:
            result = await self._execute_command_safe("start")
            await update.message.reply_text(f"▶️ *Starting bot...*\n{result}", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            self.logger().error(f"Error starting bot: {str(e)}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _handle_stop_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stopbot command."""
        if not self._verify_chat_id(update):
            return

        if not self._check_command_cooldown("stopbot"):
            await update.message.reply_text("⏳ Please wait before using this command again.")
            return

        try:
            result = await self._execute_command_safe("stop")
            await update.message.reply_text(f"⏹️ *Stopping bot...*\n{result}", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            self.logger().error(f"Error stopping bot: {str(e)}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks."""
        query = update.callback_query

        if not self._verify_chat_id(update):
            await query.answer("Unauthorized")
            return

        await query.answer()

        # Map button callbacks to command handlers
        command_map = {
            "status": self._handle_status,
            "balance": self._handle_balance,
            "pnl": self._handle_pnl,
            "history": self._handle_history,
            "startbot": self._handle_start_bot,
            "stopbot": self._handle_stop_bot,
        }

        # Create a fake update with a message for the handler
        # This is necessary because button callbacks don't have a message by default
        if query.data in command_map:
            # Create a minimal update object with message
            fake_update = Update(
                update_id=update.update_id,
                message=query.message,
            )
            await command_map[query.data](fake_update, context)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages (not commands)."""
        if not self._verify_chat_id(update):
            return

        # Log the message but don't respond
        self.logger().info(f"Received message from Telegram: {update.message.text}")
        await update.message.reply_text(
            "ℹ️ Use /help to see available commands.",
            parse_mode=ParseMode.MARKDOWN
        )
