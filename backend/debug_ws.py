import asyncio
import websockets
import json

async def debug_handler(websocket, path):
    print(f"\n[NEW CONNECTION] Path: {path}")
    try:
        async for message in websocket:
            print(f"[RECEIVED RAW]: {message}")
            try:
                data = json.loads(message)
                print(f"[PARSED JSON]: Event = {data.get('event')}")
            except:
                print("[ERROR]: Message was not valid JSON")
    except Exception as e:
        print(f"[DISCONNECTED]: {e}")

async def main():
    print("=== ESP32 WebSocket Debugger ===")
    print("Listening on: ws://0.0.0.0:8001")
    # Using port 8001 so it doesn't conflict with your main backend
    async with websockets.serve(debug_handler, "0.0.0.0", 8001):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())