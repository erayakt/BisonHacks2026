from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import websockets


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebSocketClientConfig:
    server_uri: str = "ws://192.168.137.1:8765"
    reconnect_delay_s: float = 1.0
    ping_interval_s: float = 20.0
    ping_timeout_s: float = 20.0


class WebSocketClient:
    """
    Simple reconnecting WebSocket client.

    - call `start()` to begin background task
    - call `send_json(...)` to enqueue outbound JSON messages
    - later we can add inbound message callbacks for commands from the computer
    """

    def __init__(self, cfg: WebSocketClientConfig):
        self.cfg = cfg
        self._send_q: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=200)
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

        # store last connection state for debugging
        self.is_connected: bool = False

    def stop(self) -> None:
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="ws-client")

    def send_json(self, obj: Dict[str, Any]) -> None:
        """
        Non-blocking enqueue. If queue is full, drop oldest to keep system responsive.
        """
        try:
            self._send_q.put_nowait(obj)
        except asyncio.QueueFull:
            try:
                _ = self._send_q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._send_q.put_nowait(obj)
            except asyncio.QueueFull:
                # give up
                pass

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                logger.info("Connecting to %s", self.cfg.server_uri)
                async with websockets.connect(
                    self.cfg.server_uri,
                    ping_interval=self.cfg.ping_interval_s,
                    ping_timeout=self.cfg.ping_timeout_s,
                    max_queue=64,
                ) as ws:
                    self.is_connected = True
                    logger.info("WebSocket connected.")

                    # Drain send queue and also listen for inbound messages (future use)
                    consumer = asyncio.create_task(self._consume_incoming(ws))
                    producer = asyncio.create_task(self._produce_outgoing(ws))

                    done, pending = await asyncio.wait(
                        {consumer, producer},
                        return_when=asyncio.FIRST_EXCEPTION,
                    )
                    for t in pending:
                        t.cancel()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.is_connected = False
                logger.warning("WebSocket error: %s", e)
                await asyncio.sleep(self.cfg.reconnect_delay_s)
            finally:
                self.is_connected = False

    async def _produce_outgoing(self, ws: websockets.WebSocketClientProtocol) -> None:
        while True:
            msg = await self._send_q.get()
            await ws.send(json.dumps(msg, separators=(",", ":")))

    async def _consume_incoming(self, ws: websockets.WebSocketClientProtocol) -> None:
        async for _ in ws:
            # Future: handle commands from computer
            pass
