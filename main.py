# import json
# import websockets
# import asyncio
# import logging
# import time
# import uuid  # To generate a unique connectId
# from dotenv import load_dotenv
# import os
# import requests

# # Configure logging
# logging.basicConfig(
#     filename='trading_bot.log',
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )

# # Load environment variables from .env file
# load_dotenv()

# # Fetch API credentials from environment variables
# XT_API_KEY = os.getenv("XT_API_KEY")
# XT_SECRET_KEY = os.getenv("XT_SECRET_KEY")
# XT_API_HOST = "https://sapi.xt.com"

# KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
# KUCOIN_SECRET_KEY = os.getenv("KUCOIN_SECRET_KEY")
# KUCOIN_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")
# KUCOIN_TOKEN = os.getenv("KUCOIN_TOKEN")

# # Global order book data
# xt_order_book = {"bids": [], "asks": []}
# kucoin_order_book = {"bids": [], "asks": []}

# # Process XT order book data
# def process_xt_data(data):
#     global xt_order_book
#     if 'bids' in data and 'asks' in data:
#         xt_order_book = {
#             "bids": sorted([[float(price), float(amount)] for price, amount in data.get("b", [])], reverse=True),
#             "asks": sorted([[float(price), float(amount)] for price, amount in data.get("a", [])])
#         }
#     else:
#         logging.warning(f"Unexpected XT data structure: {data}")
#     logging.info(f"Updated XT Order Book: {xt_order_book}")

# # Process KuCoin order book data
# def process_kucoin_data(data):
#     global kucoin_order_book
#     if 'bids' in data and 'asks' in data:
#         kucoin_order_book = {
#             "bids": sorted([[float(price), float(amount)] for price, amount in data["bids"]], reverse=True),
#             "asks": sorted([[float(price), float(amount)] for price, amount in data["asks"]])
#         }
#     else:
#         logging.warning(f"Unexpected KuCoin data structure: {data}")
#     logging.info(f"Updated KuCoin Order Book: {kucoin_order_book}")

# # Detect arbitrage opportunities
# def detect_arbitrage():
#     if not xt_order_book["bids"] or not kucoin_order_book["asks"]:
#         return None

#     # XT highest bid and KuCoin lowest ask
#     xt_highest_bid = xt_order_book["bids"][0][0]
#     kucoin_lowest_ask = kucoin_order_book["asks"][0][0]

#     # KuCoin highest bid and XT lowest ask
#     kucoin_highest_bid = kucoin_order_book["bids"][0][0]
#     xt_lowest_ask = xt_order_book["asks"][0][0]

#     # Detect opportunities
#     if xt_highest_bid > kucoin_lowest_ask:
#         profit = xt_highest_bid - kucoin_lowest_ask
#         logging.info(f"Arbitrage Opportunity! Buy on KuCoin at {kucoin_lowest_ask} and sell on XT at {xt_highest_bid}. Profit: {profit}")
#         return ("kucoin", "xt", kucoin_lowest_ask, xt_highest_bid)

#     elif kucoin_highest_bid > xt_lowest_ask:
#         profit = kucoin_highest_bid - xt_lowest_ask
#         logging.info(f"Arbitrage Opportunity! Buy on XT at {xt_lowest_ask} and sell on KuCoin at {kucoin_highest_bid}. Profit: {profit}")
#         return ("xt", "kucoin", xt_lowest_ask, kucoin_highest_bid)

#     return None

# # Unified Order Placement Function
# def place_order(exchange, side, price, quantity):
#     try:
#         if exchange == "xt":
#             # XT order placement logic
#             order = {
#                 "apiKey": XT_API_KEY,
#                 "side": side,
#                 "price": price,
#                 "quantity": quantity
#             }
#             response = requests.post(f"{XT_API_HOST}/v4/order", json=order)
#             response.raise_for_status()
#             logging.info(f"XT Order Response: {response.json()}")
#         elif exchange == "kucoin":
#             # KuCoin order placement logic
#             order = {
#                 "apiKey": KUCOIN_API_KEY,
#                 "passphrase": KUCOIN_PASSPHRASE,
#                 "side": side,
#                 "price": price,
#                 "quantity": quantity
#             }
#             response = requests.post(f"https://api.kucoin.com/api/v1/orders", json=order)
#             response.raise_for_status()
#             logging.info(f"KuCoin Order Response: {response.json()}")
#         else:
#             logging.error(f"Unsupported exchange: {exchange}")
#     except Exception as e:
#         logging.error(f"Order Placement Failed on {exchange}: {e}")

# # Execute arbitrage trade
# def execute_trade(buy_exchange, sell_exchange, buy_price, sell_price, quantity):
#     logging.info(f"Executing Arbitrage: Buy on {buy_exchange} at {buy_price}, Sell on {sell_exchange} at {sell_price}, Quantity: {quantity}")
#     place_order(buy_exchange, "buy", buy_price, quantity)
#     place_order(sell_exchange, "sell", sell_price, quantity)

# # XT WebSocket connection
# async def xt_websocket():
#     url = "wss://stream.xt.com/public"  # Confirm this URL from XT API documentation
#     retries = 0
#     while retries < 5:
#         try:
#             async with websockets.connect(url) as websocket:
#                 subscription_message = {
#                     "method": "subscribe",
#                     "params": ["trade.btc_usdt"],
#                     "id": 1
#                 }
#                 await websocket.send(json.dumps(subscription_message))
#                 logging.info(f"Subscription sent to XT: {subscription_message}")

#                 while True:
#                     response = await websocket.recv()
#                     try:
#                         message = json.loads(response)
#                         if "data" in message:
#                             process_xt_data(message["data"])
#                     except json.JSONDecodeError:
#                         logging.error(f"Invalid JSON from XT: {response}")
#         except Exception as e:
#             logging.error(f"XT WebSocket Error: {e}")
#             retries += 1
#             await asyncio.sleep(2 ** retries)  # Exponential backoff

# # KuCoin WebSocket connection
# async def kucoin_websocket():
#     retries = 0
#     while retries < 5:
#         try:
#             token = KUCOIN_TOKEN
#             connect_id = str(uuid.uuid4())
#             url = f"wss://ws-api-spot.kucoin.com/?token={token}&connectId={connect_id}"

#             async with websockets.connect(url) as websocket:
#                 logging.info("Connected to KuCoin WebSocket")

#                 subscription_message = {
#                     "id": connect_id,
#                     "type": "subscribe",
#                     "topic": "/market/level2:BTC-USDT",
#                     "privateChannel": False,
#                     "response": True
#                 }
#                 await websocket.send(json.dumps(subscription_message))
#                 logging.info(f"Subscription sent to KuCoin: {subscription_message}")

#                 # Fetch initial snapshot
#                 initial_snapshot_url = "https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol=BTC-USDT"
#                 response = requests.get(initial_snapshot_url, headers={"Authorization": f"Bearer {KUCOIN_TOKEN}"})
#                 if response.status_code == 200:
#                     snapshot = response.json()
#                     process_kucoin_data(snapshot['data'])
#                     logging.info(f"KuCoin Initial Snapshot: {snapshot}")
#                 else:
#                     logging.error(f"Failed to fetch KuCoin snapshot: {response.text}")

#                 while True:
#                     response = await websocket.recv()
#                     try:
#                         message = json.loads(response)
#                         logging.info(f"KuCoin Response: {message}")
#                         if "data" in message:
#                             process_kucoin_data(message["data"])
#                     except json.JSONDecodeError:
#                         logging.error(f"Invalid JSON from KuCoin: {response}")
#         except Exception as e:
#             logging.error(f"KuCoin WebSocket Error: {e}")
#             retries += 1
#             await asyncio.sleep(2 ** retries)  # Exponential backoff

# # Main loop
# async def main():
#     asyncio.create_task(xt_websocket())
#     asyncio.create_task(kucoin_websocket())

#     while True:
#         opportunity = detect_arbitrage()
#         if opportunity:
#             buy_exchange, sell_exchange, buy_price, sell_price = opportunity
#             quantity = 0.01  # Example quantity
#             execute_trade(buy_exchange, sell_exchange, buy_price, sell_price, quantity)
#         await asyncio.sleep(1)  # Polling interval

# if __name__ == "__main__":
#     asyncio.run(main())













import base64
import uuid
import random
import time
from kucoin.client import Client
from dotenv import load_dotenv
import os
import asyncio
from pyxt.websocket.xt_websocket import XTWebsocketClient
from pyxt.websocket.perp import PerpWebsocketStreamClient
from kucoin.ws_client import KucoinWsClient
import logging
from logging.handlers import RotatingFileHandler
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import signal
import json
import hmac
import hashlib
import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from collections import deque

#=================== 1. Initialize Logging: #===================
#    - Set up a logging system to capture bot activity and errors.
# Logging setup
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file = 'trading_bot.log'

# File handler with rotation
file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)  # 5MB per file, 3 backups
file_handler.setFormatter(log_formatter)

# Stream handler (console output)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)

# Root logger configuration
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, stream_handler]
)

# Example log message
logging.info("Logging system initialized.")


#=================== 2. Load Configuration: #===================
#    - Import environment variables from a `.env` file.
#    - Fetch API keys, secret keys, and other constants (e.g., trade fees, risk percentage, stop-loss, and take-profit).
# Load environment variables
load_dotenv()

# Fetch API credentials from environment variables
XT_API_KEY = os.getenv("XT_API_KEY")
XT_SECRET_KEY = os.getenv("XT_SECRET_KEY")
XT_API_HOST = "https://sapi.xt.com"

KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
KUCOIN_SECRET_KEY = os.getenv("KUCOIN_SECRET_KEY")
KUCOIN_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")
KUCOIN_TOKEN = os.getenv("KUCOIN_TOKEN")

# Define trading fees for both exchanges
XT_TRADE_FEE_PERCENT = 0.1  # Example: 0.1% for XT.com
KUCOIN_TRADE_FEE_PERCENT = 0.1  # Example: 0.1% for KuCoin

# Define a minimum spread threshold (in percentage)
MIN_ARBITRAGE_SPREAD_PERCENT = 0.001  # Example: 0.2% spread required to execute an arbitrage


# Validate API credentials
if not all([XT_API_KEY, XT_SECRET_KEY, KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE]):
    logging.error("Missing one or more API credentials. Please check your .env file.")
    raise ValueError("Missing required API credentials.")

# Constants for risk management and fees
CONFIG = {
    "xt_trade_fee_percent": 0.1,  # XT.com trading fee percentage (example: 0.1%)
    "kucoin_trade_fee_percent": 0.1,  # KuCoin trading fee percentage (example: 0.1%)
    "risk_percent": 1,  # Risk as a percentage of the available balance
    "stop_loss_percent": 0.5,  # Stop-loss as a percentage below the entry price
    "take_profit_percent": 1,  # Take-profit as a percentage above the entry price
}

# Initialize order book storage
# order_books = {
#     "xt": asyncio.Queue(),
#     "kucoin": asyncio.Queue(),
# }
order_books = {
    'xt': {
        'bids': deque(maxlen=5),
        'asks': deque(maxlen=5),
    },
    'kucoin': {
        'bids': deque(maxlen=5),
        'asks': deque(maxlen=5),
    }
}

# Log successful configuration loading
logging.info("Configuration loaded successfully.")
logging.debug(f"XT API Key: {XT_API_KEY[:4]}*** (masked for security)")
logging.debug(f"KuCoin API Key: {KUCOIN_API_KEY[:4]}*** (masked for security)")

# Global order books for XT and KuCoin
xt_order_book = {
    "bids": [], 
    "asks": []
}
kucoin_order_book = {
    "bids": [], 
    "asks": []
}


#=================== 3. Define WebSocket Client Classes: #===================
#    - XTWebsocketClient:
#      - Connect to XT.com WebSocket.
#      - Subscribe to order book streams.
#      - Listen for incoming data and log updates.
#    - KuCoin WebSocket Client:
#      - Authenticate using API credentials.
#      - Subscribe to KuCoin order book streams.
#      - Listen for incoming data and log updates.

class WsToken:
    """WebSocket Token Handler for KuCoin"""
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.timestamp = str(int(time.time() * 1000))  # Current timestamp in milliseconds
        self.signature = self._generate_signature()

    def _generate_signature(self):
        """Generate HMAC-SHA256 signature"""
        message = self.timestamp + "GET" + "/api/v1/bullet-public"
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def get_headers(self):
        """Return the authentication headers"""
        return {
            "KC-API-KEY": self.api_key,
            "KC-API-PASSPHRASE": self.passphrase,
            "KC-API-TIMESTAMP": self.timestamp,
            "KC-API-SIGN": self.signature
        }


class XTWebsocketClient:
    """WebSocket Client for XT.com"""
    def __init__(self, uri):
        self.uri = uri
        self.connection = None

    async def connect(self):
        """Establish WebSocket connection"""
        try:
            self.connection = await websockets.connect(self.uri)
            logging.info(f"Connected to {self.uri}")
        except Exception as e:
            logging.error(f"Error connecting to {self.uri}: {e}")
            raise

    async def send(self, message):
        """Send a message over the WebSocket connection"""
        try:
            await self.connection.send(message)
            logging.info(f"Message sent: {message}")
        except Exception as e:
            logging.error(f"Error sending message: {e}")

    async def subscribe(self, symbol):
        """Subscribe to order book updates for a given symbol"""
        subscribe_message = {
            "method": "subscribe",
            "params": [f"depth_update@{symbol}"],  # Adjust for XT.com stream format
            "id": 1
        }
        await self.send(json.dumps(subscribe_message))

    async def listen(self):
        """Listen for incoming messages"""
        try:
            while True:
                message = await self.connection.recv()
                logging.info(f"Received message: {message}")
        except websockets.ConnectionClosed as e:
            logging.warning(f"WebSocket connection closed: {e}")
        except Exception as e:
            logging.error(f"Error in WebSocket listen: {e}")


class KucoinWebSocketClient:
    """WebSocket Client for KuCoin"""
    def __init__(self, uri, headers):
        self.uri = uri
        self.headers = headers
        self.connection = None

    async def connect(self):
        """Establish WebSocket connection with headers"""
        try:
            self.connection = await websockets.connect(self.uri, extra_headers=self.headers)
            logging.info(f"Connected to {self.uri}")
        except Exception as e:
            logging.error(f"Error connecting to {self.uri}: {e}")
            raise

    async def listen(self):
        """Listen for incoming messages"""
        try:
            while True:
                message = await self.connection.recv()
                logging.info(f"Received message: {message}")
        except websockets.ConnectionClosed as e:
            logging.warning(f"WebSocket connection closed: {e}")
        except Exception as e:
            logging.error(f"Error in WebSocket listen: {e}")



#=================== 4. Define Handlers for WebSocket Events: #===================
#    - On open: Log the successful connection.
#    - On message: Process received data (e.g., update order books).
#    - On error: Log errors.
#    - On close: Log connection closure.

# Handlers to handle WebSocket events for XT.com
def handle_open(ws):
    """Handle WebSocket connection open event."""
    logging.info("WebSocket connection opened.")

def handle_message(ws, message):
    """Handle incoming WebSocket messages."""
    try:
        # Process the message (e.g., update order books or log data)
        data = json.loads(message)
        logging.info(f"Message received: {data}")
        # Example: Update a global or shared data structure (e.g., order book)
        # xt_order_book or kucoin_order_book updates can be implemented here
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON message: {message}, Error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error processing message: {message}, Error: {e}")

def handle_error(ws, error):
    """Handle WebSocket error event."""
    logging.error(f"WebSocket encountered an error: {error}")

def handle_close(ws, close_status_code, close_msg):
    """Handle WebSocket connection closure event."""
    logging.warning(f"WebSocket connection closed. Status Code: {close_status_code}, Message: {close_msg}")

def handle_ping(ws, ping_data):
    """Handle WebSocket ping event."""
    logging.info("Ping received from WebSocket server.")

def handle_pong(ws, pong_data):
    """Handle WebSocket pong event."""
    logging.info("Pong received from WebSocket server.")




# 5. WebSocket Connection:
#    - XT.com:
#      - Connect to XT.com WebSocket.
#      - Subscribe to BTC/USDT market updates.
#      - Continuously listen for depth updates and update the local order book.
#    - KuCoin:
#      - Connect to KuCoin WebSocket.
#      - Subscribe to BTC/USDT market updates.
#      - Continuously listen for depth updates and update the local order book.


#=================== 5. XT.com WebSocket Connection ==============
async def authenticate_xt(api_key, secret_key):
    """
    Connect to XT.com WebSocket, subscribe to BTC/USDT updates, and listen for depth updates.
    """
    stream_url = "wss://stream.xt.com/public"  # Confirm this with XT.com documentation
    retries = 0

    while retries < 5:  # Retry up to 5 times on connection failure
        try:
            logging.info("Authenticating XT WebSocket")
            async with websockets.connect(stream_url, ping_interval=30, ping_timeout=10) as websocket:
                # Prepare subscription message
                timestamp = int(time.time() * 1000)
                subscribe_message = {
                    "method": "subscribe",
                    "params": ["depth_update@btc_usdt"],  # Replace with the correct stream key
                    "id": 1,
                    "timestamp": timestamp
                }

                # Send subscription message
                await websocket.send(json.dumps(subscribe_message))
                logging.info(f"XT.com subscription sent: {subscribe_message}")

                # Listen to incoming messages
                while True:
                    response = await websocket.recv()
                    try:
                        message = json.loads(response)
                        logging.info(f"XT.com message received: {message}")

                        # Process data (e.g., update global order book)
                        # if "params" in message and "bids" in message["params"] and "asks" in message["params"]:
                        #     xt_order_book["bids"] = message["params"]["bids"]
                        #     xt_order_book["asks"] = message["params"]["asks"]
                        #     logging.info("XT.com order book updated.")

                        # Push the processed message into the queue
                        # await order_books["xt"].append(message)
                        # logging.info(f"XT.com WebSocket data pushed to order_books['xt'] queue.")
                    except json.JSONDecodeError:
                        logging.error(f"Invalid JSON received from XT.com: {response}")
        
        except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e:
            logging.warning(f"XT.com WebSocket connection closed: {e}")
            retries += 1
            await asyncio.sleep(2 ** retries)  # Exponential backoff
        
        except Exception as e:
            logging.error(f"Error authenticating XT: {e}")
            retries += 1
            await asyncio.sleep(2 ** retries)

    logging.error("XT.com WebSocket failed after maximum retries.")


#=================== 5. KuCoin WebSocket Connection ==============
async def authenticate_kucoin(api_key, secret_key, passphrase):
    """
    Connect to KuCoin WebSocket, subscribe to BTC/USDT updates, and listen for depth updates.
    """
    # Use the valid token retrieved
    token = KUCOIN_TOKEN
    connect_id = str(uuid.uuid4())  # Generate a unique connect ID

    # Construct WebSocket URL with token and connect ID
    stream_url = f"wss://ws-api-spot.kucoin.com/?token={token}&connectId={connect_id}"

    retries = 0
    while retries < 5:
        try:
            logging.info("Authenticating KuCoin WebSocket")
            async with websockets.connect(stream_url, ping_interval=30, ping_timeout=10) as websocket:
                # Authenticate and subscribe
                subscription_message = {
                    "id": 1,
                    "type": "subscribe",
                    "topic": "/market/level2:BTC-USDT",
                    "privateChannel": False,
                    "response": True
                }

                # Send subscription message
                await websocket.send(json.dumps(subscription_message))
                logging.info(f"KuCoin subscription sent: {subscription_message}")

                # Listen to incoming messages
                while True:
                    # Receive a message from the WebSocket
                    response = await websocket.recv()
                    try:
                        message = json.loads(response)
                        logging.info(f"KuCoin message received: {message}")

                        # Process the message only if it contains valid order book data
                        # if "data" in message and "bids" in message["data"] and "asks" in message["data"]:
                        #     kucoin_order_book["bids"] = message["data"]["bids"]
                        #     kucoin_order_book["asks"] = message["data"]["asks"]
                        #     logging.info("KuCoin order book updated.")

                        # Push the processed message into the queue
                        # await order_books["kucoin"].append(message)
                        # logging.info(f"KuCoin.com WebSocket data pushed to order_books['kucoin'] queue.")

                    except json.JSONDecodeError:
                        logging.error(f"Invalid JSON received from KuCoin: {response}")

        except (websockets.exceptions.ConcurrencyError, websockets.exceptions.ConnectionClosedOK) as e:
            logging.warning(f"KuCoin WebSocket connection closed: {e}")
            retries += 1
            await asyncio.sleep(2 ** retries)  # Exponential backoff
        
        except Exception as e:
            logging.error(f"Error authenticating KuCoin: {e}")
            retries += 1
            await asyncio.sleep(2 ** retries)

    logging.error("KuCoin WebSocket failed after maximum retries.")





# 6. Data Processing:
#    - Parse and store bids and asks from WebSocket messages into local order book structures for XT and KuCoin.
#=================== PROCESSING WEBSOCKET DATA FROM XT.COM ===================

# Log the updated order books
async def log_order_book_data():
    """
    Logs the current order book data for XT and KuCoin.
    """
    logging.info("Current XT Order Book:")
    logging.info(f"Bids: {list(order_books['xt']['bids'])}")
    logging.info(f"Asks: {list(order_books['xt']['asks'])}")

    logging.info("Current KuCoin Order Book:")
    logging.info(f"Bids: {list(order_books['kucoin']['bids'])}")
    logging.info(f"Asks: {list(order_books['kucoin']['asks'])}")



async def handle_xt_order_book_data(data, queue):
    """
    Handle incoming XT.com order book data with a strict timeout.
    """
    timeout_duration = 2  # seconds

    try:
        # Process the XT order book data
        async def process_xt_data():
            bids = data['b']['bids']
            asks = data['b']['asks']

            # Append data into deques for XT
            for bid in bids:
                order_books['xt']['bids'].append(bid)
            for ask in asks:
                order_books['xt']['asks'].append(ask)

            logging.info(f"XT Order Book Updated. Bids: {len(order_books['xt']['bids'])}, Asks: {len(order_books['xt']['asks'])}")

            # Log current order book data
            await log_order_book_data()

            if len(order_books['xt']['bids']) >= 5 and len(order_books['kucoin']['bids']) >= 5:
                await detect_arbitrage_opportunity()

        # Use asyncio.wait_for to enforce the timeout
        await asyncio.wait_for(process_xt_data(), timeout_duration)

    except asyncio.TimeoutError:
        logging.info("XT processing timeout reached. Switching to KuCoin.")
    except Exception as e:
        logging.error(f"Error handling XT order book data: {e}")
    finally:
        # Put the 'next' task into the queue to ensure sequential processing
        await queue.put('kucoin')



async def handle_kucoin_order_book_data(data, queue):
    """
    Handle incoming KuCoin order book data with a strict timeout.
    """
    timeout_duration = 2  # seconds

    try:
        # Process the KuCoin order book data
        async def process_kucoin_data():
            bids = data['b']['bids']
            asks = data['b']['asks']

            # Append data into deques for KuCoin
            for bid in bids:
                order_books['kucoin']['bids'].append(bid)
            for ask in asks:
                order_books['kucoin']['asks'].append(ask)

            logging.info(f"KuCoin Order Book Updated. Bids: {len(order_books['kucoin']['bids'])}, Asks: {len(order_books['kucoin']['asks'])}")

            # Log current order book data
            await log_order_book_data()

            if len(order_books['xt']['bids']) >= 5 and len(order_books['kucoin']['bids']) >= 5:
                await detect_arbitrage_opportunity()

        # Use asyncio.wait_for to enforce the timeout
        await asyncio.wait_for(process_kucoin_data(), timeout_duration)

    except asyncio.TimeoutError:
        logging.info("KuCoin processing timeout reached. Switching to XT.")
    except Exception as e:
        logging.error(f"Error handling KuCoin order book data: {e}")
    finally:
        # Put the 'next' task into the queue to ensure sequential processing
        await queue.put('xt')

# 7. Heartbeat Mechanism:
#    - Send periodic "ping" messages to WebSocket servers to keep connections alive.
#=================== SENDING HEARTBEAT TO KEEP XT.COM WEBSOCKET CONNECTION ALIVE ==============
# async def send_heartbeat(client):
#     """
#     Send periodic 'ping' messages to the WebSocket server to keep the connection alive.
#     :param client: The WebSocket client instance.
#     """
#     while True:
#         try:
#             # Send a heartbeat message
#             ping_message = json.dumps({"ping": time.time()})
#             await client.send(ping_message)
#             logging.info("Sent heartbeat to WebSocket server.")
#         except Exception as e:
#             logging.error(f"Error during heartbeat: {e}")
#         await asyncio.sleep(30)  # Send ping every 30 seconds

# #=================== HEARTBEAT FOR KUCOIN WEBSOCKET CONNECTION =================
# async def send_kucoin_heartbeat(client):
#     """
#     Send periodic 'ping' messages to KuCoin WebSocket to keep the connection alive.
#     :param client: The WebSocket client instance.
#     """
#     while True:
#         try:
#             # KuCoin requires a different ping format (if specified)
#             ping_message = json.dumps({"id": int(time.time() * 1000), "type": "ping"})
#             await client.send(ping_message)
#             logging.info("Sent heartbeat to KuCoin WebSocket server.")
#         except Exception as e:
#             logging.error(f"Error during KuCoin heartbeat: {e}")
#         await asyncio.sleep(30)  # Send ping every 30 seconds



# 8. Balance Retrieval:
#    - Fetch account balances from both exchanges using their respective APIs.
#=================== GETTING BALANCE FROM XT.COM & KUCOIN.COM ==============
# def get_balance_xt(client, symbol):
#     """
#     Fetch account balance for a specific symbol from XT.com.
#     :param client: XT.com API client instance.
#     :param symbol: The currency symbol (e.g., "BTC", "USDT").
#     :return: The available balance as a float.
#     """
#     try:
#         balance = client.get_account()  # Replace with XT.com API call to fetch balances
#         for asset in balance["data"]:
#             if asset["currency"] == symbol:
#                 available_balance = float(asset["available"])
#                 logging.info(f"XT.com balance for {symbol}: {available_balance}")
#                 return available_balance
#     except Exception as e:
#         logging.error(f"Error fetching balance from XT.com: {e}")
#         return 0.0

# def get_balance_kucoin(client, symbol):
#     """
#     Fetch account balance for a specific symbol from KuCoin.
#     :param client: KuCoin API client instance.
#     :param symbol: The currency symbol (e.g., "BTC", "USDT").
#     :return: The available balance as a float.
#     """
#     try:
#         balance = client.get_account_list()  # Replace with KuCoin API call to fetch balances
#         for asset in balance:
#             if asset["currency"] == symbol:
#                 available_balance = float(asset["available"])
#                 logging.info(f"KuCoin balance for {symbol}: {available_balance}")
#                 return available_balance
#     except Exception as e:
#         logging.error(f"Error fetching balance from KuCoin: {e}")
#         return 0.0



# 9. Spread Calculation:
#    - For each update in order books:
#      - Calculate the highest bid on one exchange and the lowest ask on the other.
#      - Include trading fees in the calculation to compute an adjusted spread.
#      - Log the spread.
#=================== CALCULATING & DISPLAYING SPREADS ==============
async def calculate_spread_with_fees(xt_bids, xt_asks, kucoin_bids, kucoin_asks):
    """
    Calculate the spreads between bids and asks from both exchanges.
    Adjust the spreads by considering fees (example: 0.1% trading fee).
    """
    if not xt_bids or not xt_asks or not kucoin_bids or not kucoin_asks:
        return None, None

    xt_highest_bid = float(xt_bids[0][0])  # Highest bid on XT
    xt_lowest_ask = float(xt_asks[0][0])  # Lowest ask on XT
    kucoin_highest_bid = float(kucoin_bids[0][0])  # Highest bid on KuCoin
    kucoin_lowest_ask = float(kucoin_asks[0][0])  # Lowest ask on KuCoin

    # Example fee: 0.1% for both exchanges
    fee_rate = 0.001  # Fee rate of 0.1%

    # Adjust the spreads considering the fee
    spread_1 = ((xt_highest_bid - kucoin_lowest_ask) / kucoin_lowest_ask) * 100
    spread_2 = ((kucoin_highest_bid - xt_lowest_ask) / xt_lowest_ask) * 100

    # Adjust spreads with fees
    spread_1 -= fee_rate * 100  # Subtract fee for XT -> KuCoin
    spread_2 -= fee_rate * 100  # Subtract fee for KuCoin -> XT

    return spread_1, spread_2


# 10. Detect Arbitrage Opportunities:
#     - Check if the adjusted spread exceeds a predefined threshold.
#     - If so, initiate trading logic.
#=================== DETECTING ARBITRAGE OPPORTUNITIES ON XT.COM & KUCOIN ==============
async def detect_arbitrage_opportunity():
    """
    Detect arbitrage opportunities based on the saved order book data.
    """
    logging.info("Checking for arbitrage opportunities...")

    xt_bids = list(order_books['xt']['bids'])
    xt_asks = list(order_books['xt']['asks'])
    kucoin_bids = list(order_books['kucoin']['bids'])
    kucoin_asks = list(order_books['kucoin']['asks'])

    # Log the order book data being used for arbitrage
    logging.info(f"XT Bids: {xt_bids}")
    logging.info(f"XT Asks: {xt_asks}")
    logging.info(f"KuCoin Bids: {kucoin_bids}")
    logging.info(f"KuCoin Asks: {kucoin_asks}")

    # Proceed with your arbitrage detection logic...
    adjusted_spread_1, adjusted_spread_2 = await calculate_spread_with_fees(xt_bids, xt_asks, kucoin_bids, kucoin_asks)

    # Log the adjusted spread values
    logging.info(f"Adjusted Spread 1 (XT -> KuCoin): {adjusted_spread_1}")
    logging.info(f"Adjusted Spread 2 (KuCoin -> XT): {adjusted_spread_2}")

    if adjusted_spread_1 is None and adjusted_spread_2 is None:
        logging.info("No arbitrage opportunity found. Resetting order book data.")
        # Reset the deques after checking for arbitrage
        order_books['xt']['bids'].clear()
        order_books['xt']['asks'].clear()

        order_books['kucoin']['bids'].clear()
        order_books['kucoin']['asks'].clear()

    else:
        # Handle detected arbitrage opportunity...
        if adjusted_spread_1 > MIN_ARBITRAGE_SPREAD_PERCENT:
            logging.info(f"Arbitrage Opportunity (XT -> KuCoin): Spread: {adjusted_spread_1:.2f}%")
        
        if adjusted_spread_2 > MIN_ARBITRAGE_SPREAD_PERCENT:
            logging.info(f"Arbitrage Opportunity (KuCoin -> XT): Spread: {adjusted_spread_2:.2f}%")


# 11. Execute Trades:
#     - XT.com:
#       - Place a limit buy order for BTC/USDT at the best available price.
#     - KuCoin:
#       - Place a limit sell order for BTC/USDT at the best available price.
#=================== EXECUTE TRADES ON XT.COM & KUCOIN.COM ==============
async def execute_trade(buy_exchange, sell_exchange, buy_price, sell_price, quantity):
    """
    Executes arbitrage trade by placing limit orders on both exchanges.

    :param buy_exchange: "kucoin" or "xt" - Exchange to buy from.
    :param sell_exchange: "kucoin" or "xt" - Exchange to sell on.
    :param buy_price: Price for the buy order.
    :param sell_price: Price for the sell order.
    :param quantity: Amount of BTC to trade.
    """
    try:
        if buy_exchange == "xt":
            buy_response = await xt_api.place_order("BTC/USDT", "buy", quantity, buy_price)
            sell_response = await kucoin_api.place_order("BTC-USDT", "sell", quantity, sell_price)
        else:  # buy_exchange == "kucoin"
            buy_response = await kucoin_api.place_order("BTC-USDT", "buy", quantity, buy_price)
            sell_response = await xt_api.place_order("BTC/USDT", "sell", quantity, sell_price)

        logging.info(f"Trade executed: {buy_exchange}->Buy, {sell_exchange}->Sell")
        logging.info(f"Buy Response: {buy_response}, Sell Response: {sell_response}")
        return buy_response, sell_response
    except Exception as e:
        logging.error(f"Trade execution failed: {e}")
        return None



# 12. Risk Management:
#     - Calculate position size based on available balance and predefined risk percentage.
#     - Set stop-loss and take-profit orders based on entry price.
#=================== RISK MANAGEMENT FOR ARBITRAGE TRADES ==============
def calculate_position_size(balance, risk_percentage, entry_price):
    """
    Calculate the position size based on available balance, risk percentage, and entry price.

    :param balance: Available balance in the account (in USDT).
    :param risk_percentage: Percentage of the balance to risk (e.g., 1%).
    :param entry_price: The entry price of the trade (in USDT).
    :return: Position size (quantity of BTC to trade).
    """
    try:
        risk_amount = balance * (risk_percentage / 100)
        position_size = risk_amount / entry_price
        logging.info(f"Calculated position size: {position_size:.6f} BTC")
        return position_size
    except Exception as e:
        logging.error(f"Error calculating position size: {e}")
        return 0.0


def set_stop_loss_and_take_profit(entry_price, stop_loss_percentage, take_profit_percentage):
    """
    Calculate stop-loss and take-profit prices based on entry price.

    :param entry_price: The entry price of the trade (in USDT).
    :param stop_loss_percentage: Percentage below the entry price for stop-loss.
    :param take_profit_percentage: Percentage above the entry price for take-profit.
    :return: Tuple of (stop_loss_price, take_profit_price).
    """
    try:
        stop_loss_price = entry_price * (1 - stop_loss_percentage / 100)
        take_profit_price = entry_price * (1 + take_profit_percentage / 100)
        logging.info(
            f"Stop-Loss Price: {stop_loss_price:.2f} USDT, Take-Profit Price: {take_profit_price:.2f} USDT"
        )
        return stop_loss_price, take_profit_price
    except Exception as e:
        logging.error(f"Error calculating stop-loss and take-profit: {e}")
        return None, None

# 13. Retry Mechanism:
#     - Retry WebSocket connections and trade executions using an exponential backoff strategy.
def exponential_backoff(attempt, base_delay=1, max_delay=60):
    """
    Exponential backoff strategy to gradually increase the delay between retries.
    
    :param attempt: The number of attempts that have been made
    :param base_delay: The base delay (in seconds) for the first retry
    :param max_delay: The maximum delay (in seconds)
    :return: The delay time (in seconds) to wait before retrying
    """
    delay = min(base_delay * (2 ** attempt), max_delay)  # Exponential backoff
    jitter = random.uniform(0, 1)  # Add some randomness to avoid retry storm
    return delay + jitter

async def retry_connection(client, retries=5):
    """
    Retries a connection attempt using exponential backoff strategy.
    
    :param connect_function: The function that attempts to connect (e.g., WebSocket connection)
    :param max_retries: The maximum number of retries before giving up
    :return: None
    """
    attempt = 0
    while attempt < retries:
        try:
            # connect_function()
            await client.connect()
            logging.info("Connection successful.")
            return
        except Exception as e:
            logging.error(f"Error reconnecting {attempt+1}: {e}")
            attempt += 1
            delay = exponential_backoff(attempt)
            logging.info(f"Retrying in {delay:.2f} seconds...")
            time.sleep(delay)
    logging.error("Max retries reached. Could not establish connection.")
    # Handle max retries reached (maybe send alert or exit)

def retry_trade_execution(execute_trade_function, max_retries=3):
    """
    Retries trade execution with exponential backoff.
    
    :param execute_trade_function: The function that executes the trade
    :param max_retries: The maximum number of retries before giving up
    :return: None
    """
    attempt = 0
    while attempt < max_retries:
        try:
            execute_trade_function()
            logging.info("Trade executed successfully.")
            return
        except Exception as e:
            logging.error(f"Trade execution attempt {attempt+1} failed: {e}")
            attempt += 1
            delay = exponential_backoff(attempt)
            logging.info(f"Retrying trade execution in {delay:.2f} seconds...")
            time.sleep(delay)
    logging.error("Max retries reached. Could not execute trade.")
    # Handle max retries reached (maybe send alert or exit)


# 15. Start Bot:
#     - Initialize XT.com and KuCoin WebSocket connections.
#     - Fetch initial order book data.
#     - Continuously monitor spreads, detect arbitrage opportunities, and execute trades.
#=================== Unified Entry Point for WebSockets ==============
async def main():
    # Load credentials from environment variables
    xt_api_key = os.getenv("XT_API_KEY")
    xt_secret_key = os.getenv("XT_SECRET_KEY")
    kucoin_api_key = os.getenv("KUCOIN_API_KEY")
    kucoin_secret_key = os.getenv("KUCOIN_SECRET_KEY")
    kucoin_passphrase = os.getenv("KUCOIN_PASSPHRASE")

    # Global order book data
    xt_order_book = {"bids": [], "asks": []}
    kucoin_order_book = {"bids": [], "asks": []}

    # PSEUDOCODE
    # Step 1: Authenticate Both Exchanges
    #======== Authenticating both XT.com andn KuCoin =========
    async def authenticate_all(xt_api_key, xt_secret_key, kucoin_api_key, kucoin_secret_key, kucoin_passphrase):
        try:
            await asyncio.gather(
                authenticate_xt(xt_api_key, xt_secret_key),
                authenticate_kucoin(kucoin_api_key, kucoin_secret_key, kucoin_passphrase)
            )
            logging.info("Both XT and KuCoin authenticated successfully.")
        except Exception as e:
            logging.error(f"Authentication failed: {e}")
            raise SystemExit("Exiting program due to failed authentication.")
    await authenticate_all(xt_api_key, xt_secret_key, kucoin_api_key, kucoin_secret_key, kucoin_passphrase)

    # Step 2: Initialize Clients
    xt_client = XTWebsocketClient(api_key=xt_api_key, secret_key=xt_secret_key)
    kucoin_client = KucoinWebSocketClient(api_key=kucoin_api_key, secret_key=kucoin_secret_key, passphrase=kucoin_passphrase)
    
    # Step 3: Fetch Initial Order Books  for XT.com and KuCoin.
    async def fetch_initial_order_books(xt_client, kucoin_client, xt_order_book, kucoin_order_book):
        try:
            xt_order_book.update(await xt_client.subscribe("BTC/USDT"))
            kucoin_order_book.update(await kucoin_client.listen("BTC/USDT"))
            logging.info(f"XT Order book: {xt_order_book}")
            logging.info(f"Kucoin Order book: {kucoin_order_book}")
        except Exception as e:
            logging.error(f"Error fetching initial order books: {e}")
            raise SystemExit("Exiting program due to failed initial order book fetch.")
    await fetch_initial_order_books(xt_client, kucoin_client, xt_order_book, kucoin_order_book)

    # Step 4: Run WebSocket Clients
    # async def run_clients(xt_client, kucoin_client, xt_order_book, kucoin_order_book):
    #     await asyncio.gather(
    #         handle_xt_client(xt_client, xt_order_book),
    #         handle_kucoin_client(kucoin_client, kucoin_order_book)
    #     )

    # await run_clients(xt_client, kucoin_client, xt_order_book, kucoin_order_book)


    # async def handle_xt_client(xt_client, xt_order_book):
    #     try:
    #         await xt_client.connect()
    #         await xt_client.subscribe("BTC/USDT")
    #         while True:
    #             data = await xt_client.listen()
    #             process_xt_data(data)
    #             xt_order_book.update(data)
    #     except Exception as e:
    #         logging.error(f"XT WebSocket Error: {e}")
    #         raise SystemExit("Terminating due to XT WebSocket failure.")

    # async def handle_kucoin_client(kucoin_client, kucoin_order_book):
    #     try:
    #         await kucoin_client.connect()
    #         await kucoin_client.subscribe("/market/level2:BTC-USDT")
    #         while True:
    #             data = await kucoin_client.listen()
    #             process_kucoin_data(data)
    #             kucoin_order_book.update(data)
    #     except Exception as e:
    #         logging.error(f"KuCoin WebSocket Error: {e}")
    #         raise SystemExit("Terminating due to KuCoin WebSocket failure.")


    


    #============== STOP HERE==============

    # # Authenticating both XT.com and KuCoin
    # async def authenticate_all():
    #     """
    #     Authenticate XT and KuCoin concurrently.
    #     """
    #     try:
    #         await asyncio.gather(
    #             authenticate_xt(xt_api_key, xt_secret_key),
    #             authenticate_kucoin(kucoin_api_key, kucoin_secret_key, kucoin_passphrase),
    #         )
    #         logging.info("Both XT and KuCoin authenticated successfully.")
    #     except Exception as e:
    #         logging.error(f"Authentication failed: {e}")
    #         raise SystemExit("Exiting program due to failed authentication.")

    # # Authenticating Websocket for both XT and KuCoin
    # await authenticate_all()

    # # Initialize XT and Kucoin client
    # xt_client = XTWebsocketClient(api_key=xt_api_key, secret_key=xt_secret_key)
    # kucoin_client = KucoinWebSocketClient(api_key=kucoin_api_key, secret_key=kucoin_secret_key, passphrase=kucoin_passphrase)

    # # Connecting and subscribing to both XT.com and KuCoin
    # async def connect_and_subscribe_all():
    #     try:
    #         await asyncio.gather(
    #             xt_client.connect(),
    #             kucoin_client.connect(),
    #         )
    #         await asyncio.gather(
    #             xt_client.subscribe("BTC/USDT"),
    #             kucoin_client.subscribe("/market/ticker:BTC-USDT"),
    #         )
    #         logging.info("Both XT and KuCoin subscriptions successful.")
    #     except Exception as e:
    #         logging.error(f"Connection or subscription failed: {e}")
    #         exit(1)

    # await connect_and_subscribe_all()

    # # Helper functions for data processing
    # async def xt_websocket_handler():
    #     try:
    #         while True:
    #             data = await xt_client.listen()
    #             process_xt_data(data)
    #             xt_order_book.update(data)
    #             await send_heartbeat(xt_client)
    #     except Exception as e:
    #         logging.error(f"XT WebSocket error: {e}")
    #         exit(1)

    # async def kucoin_websocket_handler():
    #     try:
    #         while True:
    #             data = await kucoin_client.listen()
    #             process_kucoin_data(data)
    #             kucoin_order_book.update(data)
    #             await send_kucoin_heartbeat(kucoin_client)
    #     except Exception as e:
    #         logging.error(f"KuCoin WebSocket error: {e}")
    #         exit(1)

    # async def arbitrage_monitor():
    #     while True:
    #         try:
    #             spread = calculate_spread_with_fees(
    #                 xt_order_book["bids"], kucoin_order_book["asks"]
    #             )
    #             arbitrage_opportunity = detect_arbitrage()
    #             if arbitrage_opportunity:
    #                 buy_exchange, sell_exchange, buy_price, sell_price, quantity = arbitrage_opportunity
    #                 execute_trade(buy_exchange, sell_exchange, buy_price, sell_price, quantity)
    #             await asyncio.sleep(0.5)
    #         except Exception as e:
    #             logging.error(f"Error in arbitrage monitoring: {e}")

    # async def fetch_initial_order_books():
    #     try:
    #         xt_order_book.update(await xt_client.fetch_order_book("BTC/USDT"))
    #         kucoin_order_book.update(await kucoin_client.fetch_order_book("BTC/USDT"))
    #     except Exception as e:
    #         logging.error(f"Error fetching initial order books: {e}")
    #         exit(1)

    # await fetch_initial_order_books()

    # # Run all tasks concurrently
    # await asyncio.gather(
    #     xt_websocket_handler(),
    #     kucoin_websocket_handler(),
    #     arbitrage_monitor(),
    # )

async def main():
    # Load credentials from environment variables
    xt_api_key = os.getenv("XT_API_KEY")
    xt_secret_key = os.getenv("XT_SECRET_KEY")
    kucoin_api_key = os.getenv("KUCOIN_API_KEY")
    kucoin_secret_key = os.getenv("KUCOIN_SECRET_KEY")
    kucoin_passphrase = os.getenv("KUCOIN_PASSPHRASE")

    try:
        tasks = [
            asyncio.create_task(authenticate_xt(xt_api_key, xt_secret_key)),
            asyncio.create_task(authenticate_kucoin(kucoin_api_key, kucoin_secret_key, kucoin_passphrase)),
        ]
        await asyncio.gather(*tasks)       
       
       # Start WebSocket handlers to listen for order book updates
        websocket_tasks = [
            asyncio.create_task(handle_xt_order_book_data(await get_xt_order_book_data())),
            asyncio.create_task(handle_kucoin_order_book_data(await get_kucoin_order_book_data())),
        ]
        await asyncio.gather(*websocket_tasks)

        # pending_tasks = asyncio.all_tasks()
        # logging.info(f"Pending tasks: {pending_tasks}")
    except asyncio.CancelledError:
        logging.info("Tasks canceled, shutting down gracefully.")
    # finally:
    #     # Clean up tasks
    #     for task in tasks:
    #         task.cancel()


# async def main():
#     # Load credentials from environment variables
#     xt_api_key = os.getenv("XT_API_KEY")
#     xt_secret_key = os.getenv("XT_SECRET_KEY")
#     kucoin_api_key = os.getenv("KUCOIN_API_KEY")
#     kucoin_secret_key = os.getenv("KUCOIN_SECRET_KEY")
#     kucoin_passphrase = os.getenv("KUCOIN_PASSPHRASE")

#     queue = asyncio.Queue()

#     # Start by processing XT, then KuCoin, then alternate
#     await queue.put('xt')

#     while True:
#         current_exchange = await queue.get()
#         print(f"Processing {current_exchange} exchange...") 

#         if current_exchange == 'xt':
#             # Process XT data and then pass control to KuCoin
#             # Log before processing XT
#             logging.info("Processing XT exchange...")
#             await handle_xt_order_book_data(await authenticate_xt(xt_api_key, xt_secret_key), queue)
#             print("XT processed, now switching to KuCoin.")
#             # Add KuCoin to the queue for the next iteration
#             await queue.put('kucoin')

#         elif current_exchange == 'kucoin':
#             # Process KuCoin data and then pass control to XT
#             # Log before processing KuCoin
#             logging.info("Processing KuCoin exchange...")
#             await handle_kucoin_order_book_data(await authenticate_kucoin(kucoin_api_key, kucoin_secret_key, kucoin_passphrase), queue)
#             print("KuCoin processed, now switching to XT.")
#             # Add XT to the queue for the next iteration
#             await queue.put('xt')


async def main():
    try:
        # Load credentials
        xt_api_key = os.getenv("XT_API_KEY")
        xt_secret_key = os.getenv("XT_SECRET_KEY")
        kucoin_api_key = os.getenv("KUCOIN_API_KEY")
        kucoin_secret_key = os.getenv("KUCOIN_SECRET_KEY")
        kucoin_passphrase = os.getenv("KUCOIN_PASSPHRASE")

        # Authenticate
        await authenticate_all(xt_api_key, xt_secret_key, kucoin_api_key, kucoin_secret_key, kucoin_passphrase)

        # Initialize WebSocket clients
        xt_client = XTWebsocketClient(xt_api_key, xt_secret_key)
        kucoin_client = KucoinWebSocketClient(kucoin_api_key, kucoin_secret_key, kucoin_passphrase)

        # Start WebSocket handlers
        await asyncio.gather(
            handle_xt_client(xt_client),
            handle_kucoin_client(kucoin_client),
            detect_arbitrage_opportunity()
        )
    except Exception as e:
        logging.error(f"Main function error: {e}")
        raise


# Run the main function
if __name__ == "__main__":
    asyncio.run(main())

