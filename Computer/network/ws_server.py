from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

import websockets


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebSocketServerConfig:
    host: str = "0.0.0.0"
    port: int = 8765


class WebSocketPositionServer:
    """
    Simple WebSocket server for receiving position updates from the Raspberry Pi.

    Runs its own asyncio loop in a background thread.
    Calls `on_mouse_pos(x, y, w, h)` on each received mouse_pos message.
    """

    def __init__(
        self,
        cfg: WebSocketServerConfig,
        on_mouse_pos: Callable[[float, float, float, float], None],
        on_client_state: Optional[Callable[[bool], None]] = None,
    ):
        self.cfg = cfg
        self._on_mouse_pos = on_mouse_pos
        self._on_client_state = on_client_state

        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_evt = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=1.0)

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            logger.error("WebSocket server stopped: %s", e)
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _serve(self) -> None:
        async with websockets.serve(self._handler, self.cfg.host, self.cfg.port, max_queue=64):
            logger.info("WebSocket server listening on ws://%s:%s", self.cfg.host, self.cfg.port)
            # run until stop
            while not self._stop_evt.is_set():
                await asyncio.sleep(0.2)

    async def _handler(self, websocket: websockets.WebSocketServerProtocol) -> None:
        peer = getattr(websocket, "remote_address", None)
        logger.info("Client connected: %s", peer)
        if self._on_client_state:
            self._on_client_state(True)
        try:
            async for message in websocket:
                try:
                    obj = json.loads(message)
                except Exception:
                    continue

                msg_type = obj.get("type")
                if msg_type == "mouse_pos":
                    x = float(obj.get("x", 0))
                    y = float(obj.get("y", 0))
                    w = float(obj.get("w", 1))
                    h = float(obj.get("h", 1))
                    self._on_mouse_pos(x, y, w, h)
                elif msg_type == "hello":
                    logger.info("Hello: %s", obj)
                else:
                    # Future: handle commands from Pi
                    pass
        except Exception as e:
            logger.info("Client disconnected: %s (%s)", peer, e)
        finally:
            if self._on_client_state:
                self._on_client_state(False)
