import asyncio
import websockets
import json
from datetime import datetime

# WebSocket URL
ws_url = "wss://stream.xt.com/public"

# Subscribe to a trade topic (e.g., btc_usdt)
subscribe_message = {
    "method": "subscribe",
    "params": ["trade@btc_usdt"],
    "id": 1
}

# Convert the timestamp to a readable format
def format_timestamp(timestamp):
    return datetime.utcfromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')

# WebSocket connection handler
async def handle_websocket():
    async with websockets.connect(ws_url) as websocket:
        # Send subscription request
        await websocket.send(json.dumps(subscribe_message))
        print("Subscribed to trade@btc_usdt")

        # Listen for messages
        while True:
            try:
                response = await websocket.recv()
                if not response.strip():  # Ignore empty responses
                    continue
                data = json.loads(response)

                # Extract timestamp from data and format it
                if 'data' in data and 't' in data['data']:
                    timestamp = data['data']['t']
                    formatted_time = format_timestamp(timestamp)
                    data['data']['formatted_time'] = formatted_time

                print("Parsed Data:", data)

                
            except json.JSONDecodeError:
                print("Received invalid JSON:", response)
            except Exception as e:
                print("Error:", e)

# Start the WebSocket client
async def main():
    await handle_websocket()

# Run the client
if __name__ == "__main__":
    asyncio.run(main())
