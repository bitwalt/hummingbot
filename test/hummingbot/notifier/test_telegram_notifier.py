import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from telegram.error import RetryAfter, TimedOut, TelegramError

from hummingbot.notifier.telegram_notifier import TelegramNotifier


class TestTelegramNotifier(IsolatedAsyncioWrapperTestCase):
    """
    Unit tests for hummingbot.notifier.telegram_notifier.TelegramNotifier
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.token = "test_token_123"
        self.chat_id = "123456789"

        # Mock HummingbotApplication
        self.mock_hb_app = MagicMock()
        self.mock_hb_app.strategy_name = "test_strategy"
        self.mock_hb_app._handle_command = MagicMock()

        # Create notifier instance
        self.notifier = TelegramNotifier(
            hb_app=self.mock_hb_app,
            token=self.token,
            chat_id=self.chat_id
        )

    async def asyncTearDown(self):
        if self.notifier._is_running:
            self.notifier.stop()
        await super().asyncTearDown()

    def test_initialization(self):
        """Test that TelegramNotifier initializes correctly."""
        self.assertEqual(self.notifier._token, self.token)
        self.assertEqual(self.notifier._chat_id, self.chat_id)
        self.assertFalse(self.notifier._is_running)
        self.assertIsNone(self.notifier._application)

    @patch('hummingbot.notifier.telegram_notifier.Application')
    async def test_initialize_application(self, mock_app_builder):
        """Test application initialization."""
        # Setup mock application
        mock_application = MagicMock()
        mock_application.initialize = AsyncMock()
        mock_application.start = AsyncMock()
        mock_application.updater.start_polling = AsyncMock()

        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_application
        mock_app_builder.builder.return_value = mock_builder

        # Initialize application
        success = await self.notifier._initialize_application()

        # Verify
        self.assertTrue(success)
        mock_builder.token.assert_called_once_with(self.token)
        mock_application.initialize.assert_called_once()
        mock_application.start.assert_called_once()
        mock_application.updater.start_polling.assert_called_once()

    async def test_rate_limiting_check(self):
        """Test rate limiting checks."""
        # Should allow first message
        self.assertTrue(self.notifier._check_rate_limit())

        # Record a message
        self.notifier._record_message_time()

        # Should still allow since we're under the limit
        self.assertTrue(self.notifier._check_rate_limit())

        # Fill up rate limit
        for _ in range(20):
            self.notifier._record_message_time()

        # Should now be rate limited
        self.assertFalse(self.notifier._check_rate_limit())

    async def test_command_cooldown(self):
        """Test command cooldown mechanism."""
        # First call should succeed
        self.assertTrue(self.notifier._check_command_cooldown("status"))

        # Immediate second call should fail
        self.assertFalse(self.notifier._check_command_cooldown("status"))

        # Wait for cooldown
        await asyncio.sleep(2.1)

        # Should now succeed
        self.assertTrue(self.notifier._check_command_cooldown("status"))

    def test_verify_chat_id(self):
        """Test chat ID verification."""
        # Create mock update with correct chat ID
        mock_update = MagicMock()
        mock_update.effective_chat.id = int(self.chat_id)

        self.assertTrue(self.notifier._verify_chat_id(mock_update))

        # Create mock update with incorrect chat ID
        mock_update.effective_chat.id = 999999999

        self.assertFalse(self.notifier._verify_chat_id(mock_update))

    @patch('hummingbot.notifier.telegram_notifier.Application')
    async def test_send_message_with_retry(self, mock_app_builder):
        """Test message sending with retry logic."""
        # Setup mock application and bot
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        mock_application = MagicMock()
        mock_application.bot = mock_bot

        self.notifier._application = mock_application
        self.notifier._is_running = True

        # Test successful send
        await self.notifier._send_message_direct("Test message")
        mock_bot.send_message.assert_called_once()

    @patch('hummingbot.notifier.telegram_notifier.Application')
    async def test_send_message_rate_limit_error(self, mock_app_builder):
        """Test handling of Telegram rate limit errors."""
        # Setup mock application and bot that raises RetryAfter
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=RetryAfter(2))

        mock_application = MagicMock()
        mock_application.bot = mock_bot

        self.notifier._application = mock_application
        self.notifier._is_running = True

        # This should handle the retry gracefully
        await self.notifier._send_message_direct("Test message")

        # Should have attempted to send
        self.assertTrue(mock_bot.send_message.called)

    @patch('hummingbot.notifier.telegram_notifier.Application')
    async def test_send_message_timeout(self, mock_app_builder):
        """Test handling of timeout errors."""
        # Setup mock application and bot that times out
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(side_effect=TimedOut())

        mock_application = MagicMock()
        mock_application.bot = mock_bot

        self.notifier._application = mock_application
        self.notifier._is_running = True

        # This should handle the timeout gracefully
        await self.notifier._send_message_direct("Test message")

        # Should have attempted multiple times due to retry logic
        self.assertTrue(mock_bot.send_message.called)

    @patch('hummingbot.notifier.telegram_notifier.Application')
    async def test_send_long_message(self, mock_app_builder):
        """Test splitting long messages."""
        # Setup mock application and bot
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        mock_application = MagicMock()
        mock_application.bot = mock_bot

        self.notifier._application = mock_application
        self.notifier._is_running = True

        # Create a message longer than 4096 characters
        long_message = "A" * 5000

        await self.notifier._send_message_direct(long_message)

        # Should have been called twice (split into chunks)
        self.assertEqual(mock_bot.send_message.call_count, 2)

    async def test_handle_start_command(self):
        """Test /start command handler."""
        mock_update = MagicMock()
        mock_update.effective_chat.id = int(self.chat_id)
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()

        await self.notifier._handle_start(mock_update, mock_context)

        # Should have sent a reply
        mock_update.message.reply_text.assert_called_once()

    async def test_handle_status_command(self):
        """Test /status command handler."""
        mock_update = MagicMock()
        mock_update.effective_chat.id = int(self.chat_id)
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()

        # Mock the status method
        self.mock_hb_app.status = MagicMock(return_value="Bot is running")

        await self.notifier._handle_status(mock_update, mock_context)

        # Should have sent a reply
        mock_update.message.reply_text.assert_called_once()

    async def test_handle_unauthorized_access(self):
        """Test handling of unauthorized chat IDs."""
        mock_update = MagicMock()
        mock_update.effective_chat.id = 999999999  # Wrong chat ID
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()

        await self.notifier._handle_start(mock_update, mock_context)

        # Should not have sent any reply
        mock_update.message.reply_text.assert_not_called()

    async def test_add_message_to_queue(self):
        """Test adding messages to queue."""
        self.notifier.add_message_to_queue("Test message")
        self.assertEqual(self.notifier._message_queue.qsize(), 1)

        self.notifier.add_message_to_queue("Test message 2")
        self.assertEqual(self.notifier._message_queue.qsize(), 2)

    @patch('hummingbot.notifier.telegram_notifier.Application')
    async def test_start_and_stop(self, mock_app_builder):
        """Test starting and stopping the notifier."""
        # Setup mock application
        mock_application = MagicMock()
        mock_application.initialize = AsyncMock()
        mock_application.start = AsyncMock()
        mock_application.updater.start_polling = AsyncMock()
        mock_application.updater.stop = AsyncMock()
        mock_application.stop = AsyncMock()
        mock_application.shutdown = AsyncMock()
        mock_application.bot.send_message = AsyncMock()

        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_application
        mock_app_builder.builder.return_value = mock_builder

        # Start notifier
        self.notifier.start()
        await asyncio.sleep(0.1)  # Give it time to initialize

        self.assertTrue(self.notifier._is_running)

        # Stop notifier
        self.notifier.stop()
        await asyncio.sleep(0.1)  # Give it time to stop

        self.assertFalse(self.notifier._is_running)
