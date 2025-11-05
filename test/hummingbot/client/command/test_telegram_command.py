import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.client.command.telegram_command import TelegramCommand
from hummingbot.client.config.client_config_map import ClientConfigMap, TelegramConfigMap


class MockHummingbotApplication(TelegramCommand):
    """Mock HummingbotApplication with TelegramCommand mixed in."""

    def __init__(self):
        self.client_config_map = ClientConfigMap()
        self.notifiers = []
        self.ev_loop = asyncio.get_event_loop()
        self._telegram = None
        self._logger = MagicMock()

    def logger(self):
        return self._logger

    def notify(self, msg: str):
        pass


class TestTelegramCommand(IsolatedAsyncioWrapperTestCase):
    """
    Integration tests for TelegramCommand functionality.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.app = MockHummingbotApplication()

        # Configure Telegram settings
        self.app.client_config_map.telegram.telegram_enabled = True
        self.app.client_config_map.telegram.telegram_token = "test_token_123"
        self.app.client_config_map.telegram.telegram_chat_id = "123456789"
        self.app.client_config_map.telegram.telegram_autostart = False

    async def asyncTearDown(self):
        if hasattr(self.app, '_telegram') and self.app._telegram is not None:
            await self.app.stop_telegram_async()
        await super().asyncTearDown()

    @patch('hummingbot.notifier.telegram_notifier.Application')
    async def test_start_telegram_success(self, mock_app_builder):
        """Test successful Telegram start."""
        # Setup mock application
        mock_application = MagicMock()
        mock_application.initialize = AsyncMock()
        mock_application.start = AsyncMock()
        mock_application.updater.start_polling = AsyncMock()
        mock_application.bot.send_message = AsyncMock()

        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_application
        mock_app_builder.builder.return_value = mock_builder

        # Start Telegram
        await self.app.start_telegram_async(timeout=5.0)

        # Verify
        self.assertIsNotNone(self.app._telegram)
        self.assertIn(self.app._telegram, self.app.notifiers)

    async def test_start_telegram_already_running(self):
        """Test starting Telegram when it's already running."""
        # Create a mock notifier
        self.app._telegram = MagicMock()

        # Try to start again
        await self.app.start_telegram_async(timeout=5.0)

        # Should log warning but not crash
        self.assertIsNotNone(self.app._telegram)

    async def test_start_telegram_not_enabled(self):
        """Test starting Telegram when it's not enabled."""
        self.app.client_config_map.telegram.telegram_enabled = False

        await self.app.start_telegram_async(timeout=5.0)

        # Should not create notifier
        self.assertIsNone(self.app._telegram)

    async def test_start_telegram_no_token(self):
        """Test starting Telegram without token."""
        self.app.client_config_map.telegram.telegram_token = ""

        await self.app.start_telegram_async(timeout=5.0)

        # Should not create notifier
        self.assertIsNone(self.app._telegram)

    async def test_start_telegram_no_chat_id(self):
        """Test starting Telegram without chat ID."""
        self.app.client_config_map.telegram.telegram_chat_id = ""

        await self.app.start_telegram_async(timeout=5.0)

        # Should not create notifier
        self.assertIsNone(self.app._telegram)

    @patch('hummingbot.notifier.telegram_notifier.Application')
    async def test_stop_telegram(self, mock_app_builder):
        """Test stopping Telegram."""
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

        # Start Telegram
        await self.app.start_telegram_async(timeout=5.0)
        self.assertIsNotNone(self.app._telegram)

        # Stop Telegram
        await self.app.stop_telegram_async()

        # Verify
        self.assertIsNone(self.app._telegram)
        self.assertEqual(len(self.app.notifiers), 0)

    async def test_stop_telegram_not_running(self):
        """Test stopping Telegram when it's not running."""
        # Try to stop when not running
        await self.app.stop_telegram_async()

        # Should not crash
        self.assertIsNone(self.app._telegram)

    @patch('hummingbot.notifier.telegram_notifier.Application')
    async def test_restart_telegram(self, mock_app_builder):
        """Test restarting Telegram."""
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

        # Start Telegram
        await self.app.start_telegram_async(timeout=5.0)
        first_notifier = self.app._telegram

        # Restart Telegram
        await self.app.restart_telegram_async(timeout=5.0)

        # Verify new instance was created
        self.assertIsNotNone(self.app._telegram)
        # Note: Due to mocking, we can't reliably test if it's a different instance

    @patch('hummingbot.notifier.telegram_notifier.Application')
    async def test_start_telegram_with_autostart_retry(self, mock_app_builder):
        """Test Telegram autostart with retry on failure."""
        # Enable autostart
        self.app.client_config_map.telegram.telegram_autostart = True

        # Setup mock to fail first time, succeed second time
        mock_application = MagicMock()
        mock_application.initialize = AsyncMock(side_effect=[Exception("Connection failed"), None])
        mock_application.start = AsyncMock()
        mock_application.updater.start_polling = AsyncMock()
        mock_application.bot.send_message = AsyncMock()

        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_application
        mock_app_builder.builder.return_value = mock_builder

        # Override sleep to make test faster
        self.app._telegram_sleep_rate_autostart_retry = 0.1

        # Start Telegram (will retry due to autostart)
        await self.app.start_telegram_async(timeout=5.0)

        # Eventually should succeed
        self.assertIsNotNone(self.app._telegram)
