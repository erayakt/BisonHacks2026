import asyncio
import websockets
import json
import atexit
from gpiozero import PWMOutputDevice

# ----------------------------
# GPIO SETUP
# ----------------------------
motor = PWMOutputDevice(18)

def cleanup():
    motor.off()

atexit.register(cleanup)

# ----------------------------
# VIBRATION HANDLER
# ----------------------------
async def vibrate(intensity):
    """
    Pulses the motor at a given intensity (0.0 - 1.0)
    then switches off with a short gap before the next pulse.
    """
    clamped = max(0.0, min(1.0, intensity))
    motor.value = clamped
    await asyncio.sleep(0.6)
    motor.value = 0
    await asyncio.sleep(0.3)

# ----------------------------
# WEBSOCKET HANDLER
# ----------------------------
async def handler(websocket):
    print("Host connected.")
    async for message in websocket:
        try:
            data = json.loads(message)
            print(f"Received {len(data)} regions from host.")

            for region in data:
                intensity = region["normalized"]
                row = region["row"]
                col = region["col"]
                description = region.get("description", "No description")

                print(f"  Region ({row},{col}) → {intensity * 100:.1f}% intensity")
                print(f"  Description: {description}")

                await vibrate(intensity)

            print("All regions processed.\n")

        except Exception as e:
            print(f"Error handling message: {e}")

# ----------------------------
# START WEBSOCKET SERVER
# ----------------------------
async def main():
    print("Starting hardware WebSocket server on port 8765...")
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("Hardware server running. Waiting for host connection...")
        await asyncio.Future()  # run forever

# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
        cleanup()