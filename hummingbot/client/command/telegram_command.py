import asyncio
import threading
import time
from typing import TYPE_CHECKING

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.notifier.telegram_notifier import TelegramNotifier

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


SUBCOMMANDS = ['start', 'stop', 'restart']


class TelegramCommand:
    """
    Commands for managing the Telegram integration.
    """
    _telegram_sleep_rate_connection_check: float = 1.0
    _telegram_sleep_rate_autostart_retry: float = 10.0

    def telegram_start(self,  # type: HummingbotApplication
                       timeout: float = 30.0
                       ):
        """Start the Telegram notifier."""
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.telegram_start, timeout)
            return
        safe_ensure_future(self.start_telegram_async(timeout=timeout),
                           loop=self.ev_loop)

    def telegram_stop(self,  # type: HummingbotApplication
                      ):
        """Stop the Telegram notifier."""
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.telegram_stop)
            return
        safe_ensure_future(self.stop_telegram_async(),
                           loop=self.ev_loop)

    def telegram_restart(self,  # type: HummingbotApplication
                         timeout: float = 30.0
                         ):
        """Restart the Telegram notifier."""
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.telegram_restart, timeout)
            return
        safe_ensure_future(self.restart_telegram_async(timeout=timeout),
                           loop=self.ev_loop)

    async def start_telegram_async(self,  # type: HummingbotApplication
                                   timeout: float = 30.0
                                   ):
        """Start the Telegram notifier asynchronously."""
        # Check if already running
        if hasattr(self, '_telegram') and self._telegram is not None:
            self.logger().warning("Telegram notifier is already running!")
            self.notify('Telegram notifier is already running!')
            return

        # Validate configuration
        config = self.client_config_map.telegram
        if not config.telegram_enabled:
            self.logger().error("Telegram is not enabled. Please enable it in your config.")
            self.notify("Telegram is not enabled. Use 'config telegram_enabled' to enable it.")
            return

        if not config.telegram_token:
            self.logger().error("Telegram token is not set. Please configure it.")
            self.notify("Telegram token is not set. Use 'config telegram_token' to set it.")
            return

        if not config.telegram_chat_id:
            self.logger().error("Telegram chat ID is not set. Please configure it.")
            self.notify("Telegram chat ID is not set. Use 'config telegram_chat_id' to set it.")
            return

        # Start the notifier
        while True:
            try:
                start_t = time.time()
                self.logger().info('Starting Telegram notifier...')

                # Create and initialize the notifier
                self._telegram = TelegramNotifier(
                    hb_app=self,
                    token=config.telegram_token,
                    chat_id=config.telegram_chat_id
                )

                # Add to notifiers list
                self.notifiers.append(self._telegram)

                # Start the notifier
                self._telegram.start()

                # Wait for successful connection (give it some time to initialize)
                await asyncio.sleep(2)

                if time.time() - start_t > timeout:
                    raise Exception(f'Connection timed out after {timeout} seconds')

                self.logger().info('Telegram notifier started successfully.')
                self.notify('Telegram notifier connected successfully! 🤖')
                break

            except Exception as e:
                error_msg = f'Failed to start Telegram notifier: {str(e)}'

                if config.telegram_autostart:
                    s = self._telegram_sleep_rate_autostart_retry
                    self.logger().error(f'{error_msg}. Retrying in {s} seconds.')
                    self.notify(f'Telegram notifier failed to start, retrying in {s} seconds.')
                else:
                    self.logger().error(error_msg)
                    self.notify('Telegram notifier failed to start.')

                # Clean up on failure
                if hasattr(self, '_telegram') and self._telegram:
                    try:
                        self._telegram.stop()
                        if self._telegram in self.notifiers:
                            self.notifiers.remove(self._telegram)
                    except Exception:
                        pass
                    self._telegram = None

                if config.telegram_autostart:
                    await asyncio.sleep(self._telegram_sleep_rate_autostart_retry)
                else:
                    break

    async def stop_telegram_async(self,  # type: HummingbotApplication
                                  ):
        """Stop the Telegram notifier asynchronously."""
        if not hasattr(self, '_telegram') or self._telegram is None:
            self.logger().error("Telegram notifier is not running!")
            self.notify('Telegram notifier is not running!')
            return

        try:
            # Remove from notifiers list
            if self._telegram in self.notifiers:
                self.notifiers.remove(self._telegram)

            # Stop the notifier
            self._telegram.stop()
            self._telegram = None

            self.logger().info("Telegram notifier stopped")
            self.notify('Telegram notifier disconnected')

        except Exception as e:
            self.logger().error(f'Failed to stop Telegram notifier: {str(e)}')
            self.notify(f'Error stopping Telegram notifier: {str(e)}')

    async def restart_telegram_async(self,  # type: HummingbotApplication
                                     timeout: float = 30.0
                                     ):
        """Restart the Telegram notifier asynchronously."""
        await self.stop_telegram_async()
        await asyncio.sleep(1)  # Give it a moment to fully stop
        await self.start_telegram_async(timeout)
