from __future__ import annotations

import asyncio
import logging
import os
import time

from config import MOUSE_CONFIG, WS_CONFIG
from inputs.mouse_input import MouseInput
from network.ws_client import WebSocketClient, WebSocketClientConfig


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def run() -> None:
    mouse = MouseInput(MOUSE_CONFIG)
    mouse.start()

    ws = WebSocketClient(
        WebSocketClientConfig(
            server_uri=WS_CONFIG.server_uri,
            reconnect_delay_s=WS_CONFIG.reconnect_delay_s,
        )
    )
    ws.start()

    # Send a "hello" so the server can log/verify connection (optional)
    ws.send_json({"type": "hello", "device": "raspberrypi", "ts": time.time()})

    try:
        last_sent = 0.0
        min_interval_s = 1.0 / 60.0  # cap to 60Hz

        while True:
            now = time.time()
            if mouse.is_moved() and (now - last_sent) >= min_interval_s:
                x, y = mouse.get_absolute_position()
                ws.send_json(
                    {
                        "type": "mouse_pos",
                        "x": x,
                        "y": y,
                        "w": MOUSE_CONFIG.max_x,
                        "h": MOUSE_CONFIG.max_y,
                        "ts": now,
                    }
                )
                last_sent = now

            # keep loop light
            await asyncio.sleep(0.005)

    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        ws.stop()
        mouse.stop()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
