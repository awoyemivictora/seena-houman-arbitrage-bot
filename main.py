from pyxt import XTClient
from kucoin.client import Client
from dotenv import load_dotenv
import os
import asyncio
from pyxt.websocket import XTWebSocket
from kucoin.client import WsToken
from kucoin.ws_client import KucoinWsClient

# Load environment variables from .env file
load_dotenv()

# Fetch API credentials from environment variables
XT_API_KEY = os.getenv("XT_API_KEY")
XT_SECRET_KEY = os.getenv("XT_SECRET_KEY")
KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
KUCOIN_SECRET_KEY = os.getenv("KUCOIN_SECRET_KEY")
KUCOIN_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")

# XT.com API Authentication
def authenticate_xt(api_key, secret_key):
    try:
        client = XTClient(api_key=api_key, secret_key=secret_key)
        print("XT.com authentication successful!")
        return client
    except Exception as e:
        print(f"XT.com authentication failed: {e}")
        return None 
    

# KuCoin API Authentication
def authenticate_kucoin(api_key, secret_key, passphrase):
    try:
        client = Client(api_key, secret_key, passphrase)
        print("KuCoin authentication successful!")
        return client
    except Exception as e:
        print(f"KuCoin authentication failed: {e}")
        return None 
    

# Calculate and display spread
def calculate_spread(bids, asks):
    if bids and asks:
        highest_bid = max(bids, key=lambda x: x[0])[0] # Highestt bid price
        lowest_ask = min(asks, key=lambda x: x[0])[0] # Lowest ask priice
        spread = float(lowest_ask) - float(highest_bid)
        print(f"Spread: {spread:2f}")
        return spread
    else:
        print("Bids or asks data is missing. Cannot calculate spread.")
        return None
    
# Place orders on XT.com
async def place_xt_order(client, side, price, volume):
    try:
        order_response = await client.order(
            symbol="BTC-USDT",
            side=side,
            type=price,
            quantity=volume
        )
        print("XT Order Response:", order_response)
    except Exception as e:
        print(f"Failed to place order on XT.com: {e}")


# Place orders on KuCoin
async def place_kucoin_order(client, side, price, volume):
    try:
        order_response = client.order(
            symbol="BTC-USDT",
            side=side,
            type="limit",
            price=price,
            size=volume
        )
        print("KuCoin Order Response:", order_response)
    except Exception as e:
        print(f"Failed to place order on KuCoin: {e}")
    

# XT.com orderbook listener with trading logic
async def listen_xt_orderbook(api_key, secret_key, xt_client, symbol, kucoin_client):
    try:
        ws = XTWebSocket(api_key=api_key, secret_key=secret_key)
        await ws.subscribe_orderbook(symbol)
        print(f"Connected to XT.com WebSocket for {symbol}")

        async for message in ws.listen():
            if message["type"] == "orderbook":
                bids = message["data"]["bids"]
                asks = message["data"]["asks"]
                print("XT Orderbook Update:", {symbol})
                spread = calculate_spread(bids, asks)

                # Trading logic - example condition
                if spread and spread > 5: # Example threshold to trigger arbitrage logic
                    print("Executing trade logic due to high spread...")
                    # Example logic: Buy on XT.com and sell on KuCoin
                    if bids and asks:
                        await place_xt_order(xt_client, "buy", bids[0][0], 0.01) # Buy 0.01 BTC on XT.com
                        await place_kucoin_order(kucoin_client, "sell", asks[0][0], 0.01) # Sell 0.01 BTC on KuCoin
    
    except Exception as e:
        print(f"Error in XT WebSocket: {e}")


# WebSocket listener for KuCoin
async def listen_kucoin_orderbook(api_key, secret_key, passphrase, symbol):
    async def handle_msg(msg):
        if msg["topic"].endswith("/depths"): # Orderbook depth 5
            print("KuCoin Orderbook Update Received:", {symbol})
            bids = msg["data"]["bids"]
            asks = msg["data"]["asks"]
            calculate_spread(bids, asks)

    
    try:
        ws_token = WsToken(api_key, secret_key, passphrase)
        kucoin_ws = await KucoinWsClient.create(None, ws_token, handle_msg)
        await kucoin_ws.subscribe(f"/market/depth5:{symbol}")
        print(f"Connected to KuCoin WebSocket for {symbol}")
    except Exception as e:
        print(f"Error in KuCoin WebSocket: {e}")


# Main async function tot start WebSocket listeners
async def main_async():
    xt_symbol = "btc_usdt" # XT.com symbol format
    kucoin_symbol = "BTC-USDT" # KuCoin symbol format

    xt_client = authenticate_xt(XT_API_KEY, XT_SECRET_KEY)
    kucoin_client = authenticate_kucoin(KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE)

    if xt_client and kucoin_client:
        # Run both WebSocket listeners concurrently
        await asyncio.gather(
            listen_xt_orderbook(XT_API_KEY, XT_SECRET_KEY, xt_client, xt_symbol, kucoin_client),
            listen_kucoin_orderbook(KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE, kucoin_symbol)
        )
    
    
# Main function to authenticate and start WebSockett listeners
def main():
    # Authenticate with XT.com
    xt_client = authenticate_xt(XT_API_KEY, XT_SECRET_KEY)

    # Authenticate with KuCoin
    kucoin_client = authenticate_kucoin(KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE)

    # Add further logic here, such as fetching order book data
    if xt_client and kucoin_client:
        print("Both exchanges authenticated successfully! Starting WebSocket listeners.")
        asyncio.run(main_async())
    else:
        print("Authentication failed for one or both exchanges.")










if __name__ == "__main__":
    main()

