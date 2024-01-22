import asyncio
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.changelly import changelly_constants as CONSTANTS, changelly_web_utils as web_utils
from hummingbot.connector.exchange.changelly.changelly_auth import ChangellyAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.changelly.changelly_exchange import ChangellyExchange


class ChangellyAPIUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0
    SPOT_STREAM_ID = 21

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: ChangellyAuth,
        trading_pairs: List[str],
        connector: "ChangellyExchange",
        api_factory: WebAssistantsFactory,
    ):
        super().__init__()
        self._auth: ChangellyAuth = auth
        self._current_listen_key = None
        self._api_factory = api_factory
        self._connector = connector
        self._trading_pairs = trading_pairs or []
        self._last_recv_time = 0.0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Connects to the exchange's WebSocket service.
        """
        ws: WSAssistant = await self._get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_TRADING_URL)
        await self._authenticate_connection(ws)
        return ws

    async def _authenticate_connection(self, ws: WSAssistant):
        """
        Authenticates to the WebSocket service using the provided API key and secret.
        """
        auth_message: WSJSONRequest = WSJSONRequest(payload=self._auth.ws_authenticate())
        await ws.send(auth_message)

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue
        :param output: the queue to use to store the received messages
        """
        ws = None
        while True:
            try:
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=CONSTANTS.WSS_TRADING_URL)
                await self._authenticate_connection(ws)
                self._last_ws_message_sent_timestamp = self._time()
                while True:
                    try:
                        seconds_until_next_ping = CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL - (
                            self._time() - self._last_ws_message_sent_timestamp
                        )
                        await asyncio.wait_for(
                            self._process_ws_messages(ws=ws, output=output), timeout=seconds_until_next_ping
                        )
                    except asyncio.TimeoutError:
                        ping_time = self._time()
                        self._last_ws_message_sent_timestamp = ping_time
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
            finally:
                # Make sure no background task is leaked.
                ws and await ws.disconnect()
                await self._sleep(5)

    async def _subscribe_channels(self, ws: WSAssistant):
        for trading_pair in self._trading_pairs:
            subscribe_payload = {"method": CONSTANTS.SPOT_SUBSCRIBE, "params": {}, "id": self.SPOT_STREAM_ID}
            payload: WSJSONRequest = WSJSONRequest(payload=subscribe_payload)
            await ws.send(payload)

    async def _process_ws_messages(self, ws: WSAssistant, output: asyncio.Queue):
        """
        Process incoming WebSocket messages and handle different types of notifications.
        """
        async for ws_response in ws.iter_messages():
            data = ws_response.data
            if "method" in data:
                method = data["method"]
                params = data["params"]
                if method == "spot_order" or method == "spot_orders":
                    # Handle spot order updates or snapshots
                    self._handle_spot_order(params, output)
                elif method == "spot_balance":
                    # Handle spot balance updates
                    self._handle_spot_balance(params, output)

    def _handle_spot_order(self, data, output_queue: asyncio.Queue):
        """
        Process spot order updates or snapshots and put them into the output queue.
        """
        for order in data:
            internal_order_update = self._convert_to_internal_order_format(order)
            output_queue.put_nowait(internal_order_update)

    def _convert_to_internal_order_format(self, order):
        """
        Convert a spot order update or snapshot to the internal order format.
        """
        # TODO: Implement this method
        pass

    def _handle_spot_balance(self, data, output_queue: asyncio.Queue):
        """
        Process spot balance updates and put them into the output queue.
        """
        # TODO: Process the spot balance data and convert it to the appropriate internal format
        # This is an example and needs to be modified according to your internal data structures.
        for balance in data:
            # Example: Convert 'balance' to your internal balance update format and add to output_queue
            internal_balance_update = self._convert_to_internal_balance_format(balance)
            output_queue.put_nowait(internal_balance_update)

    def _convert_to_internal_balance_format(self, balance):
        """
        Convert a spot balance update to the internal balance format.
        """
        # TODO: Implement this method
        pass

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        """
        Handles reconnection on user stream interruption.
        """
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)
        await self._sleep(5)  # Wait for a few seconds before reconnecting

    async def _get_ws_assistant(self) -> WSAssistant:
        """
        Retrieves a websocket assistant.
        """
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def last_recv_time(self) -> float:
        """
        Returns the timestamp of the last received message.
        """
        return self._last_recv_time
