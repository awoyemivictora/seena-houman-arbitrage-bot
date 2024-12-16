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
import websocket
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from collections import deque
import threading
from get_kucoin_token import fetch_websocket_token


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

# Define trading fees for both exchanges
XT_TRADE_FEE_PERCENT = 0.1  # Example: 0.1% for XT.com
KUCOIN_TRADE_FEE_PERCENT = 0.1  # Example: 0.1% for KuCoin
STOP_LOSS = float(os.getenv('STOP_LOSS', '0.01'))  # Default 1%
TAKE_PROFIT = float(os.getenv('TAKE_PROFIT', '0.02'))  # Default 2%

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
# xt_order_book = {
#     "bids": [], 
#     "asks": []
# }
# kucoin_order_book = {
#     "bids": [], 
#     "asks": []
# }


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

# OLD ONES
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

    async def on_message(self, message):
        try:
            data = json.loads(message)
            if "depthUpdate" in data:
                self.update_order_book("XT", data["bids"], data["asks"])
        except Exception as e:
            logging.error(f"Error processing XT message: {e}")

    async def update_order_book(self, exchange, bids, asks):
        global order_books
        order_books[exchange]["bids"] = sorted(bids, key=lambda x: -float(x[0]))
        order_books[exchange]["asks"] = sorted(asks, key=lambda x: float(x[0]))
        logging.info(f"{exchange} order book updated: {len(bids)} bids, {len(asks)} asks")


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

    async def on_message(self, message):
        try:
            data = json.loads(message)
            if "depthUpdate" in data:
                self.update_order_book("KuCoin", data["bids"], data["asks"])
        except Exception as e:
            logging.error(f"Error processing KuCoin message: {e}")

    async def update_order_book(self, exchange, bids, asks):
        global order_books
        order_books[exchange]["bids"] = sorted(bids, key=lambda x: -float(x[0]))
        order_books[exchange]["asks"] = sorted(asks, key=lambda x: float(x[0]))
        logging.info(f"{exchange} order book updated: {len(bids)} bids, {len(asks)} asks")



#=================== 4. Define Handlers for WebSocket Events: #===================
#    - On open: Log the successful connection.
#    - On message: Process received data (e.g., update order books).
#    - On error: Log errors.
#    - On close: Log connection closure.

# Handlers to handle WebSocket events for XT.com
# def handle_open(ws):
#     """Handle WebSocket connection open event."""
#     logging.info("WebSocket connection opened.")

# def handle_message(ws, message):
#     """Handle incoming WebSocket messages."""
#     try:
#         # Process the message (e.g., update order books or log data)
#         data = json.loads(message)
#         logging.info(f"Message received: {data}")
#         # Example: Update a global or shared data structure (e.g., order book)
#         # xt_order_book or kucoin_order_book updates can be implemented here
#     except json.JSONDecodeError as e:
#         logging.error(f"Error decoding JSON message: {message}, Error: {e}")
#     except Exception as e:
#         logging.error(f"Unexpected error processing message: {message}, Error: {e}")

# def handle_error(ws, error):
#     """Handle WebSocket error event."""
#     logging.error(f"WebSocket encountered an error: {error}")

# def handle_close(ws, close_status_code, close_msg):
#     """Handle WebSocket connection closure event."""
#     logging.warning(f"WebSocket connection closed. Status Code: {close_status_code}, Message: {close_msg}")

def handle_on_open(exchange_name, ws, subscribe_callback):
    """Handler for WebSocket open event."""
    logging.info(f"{exchange_name} WebSocket connection opened.")
    subscribe_callback()


def handle_on_message(exchange_name, ws, message, process_callback):
    """Handler for WebSocket message event."""
    try:
        data = json.loads(message)
        process_callback(data)
    except Exception as e:
        logging.error(f"{exchange_name} WebSocket message processing error: {e}")


def handle_on_error(exchange_name, ws, error):
    """Handler for WebSocket error event."""
    logging.error(f"{exchange_name} WebSocket encountered an error: {error}")


def handle_on_close(exchange_name, ws, close_status_code, close_msg):
    """Handler for WebSocket close event."""
    logging.info(f"{exchange_name} WebSocket connection closed.")


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
                        if "params" in message and "bids" in message["params"] and "asks" in message["params"]:
                            xt_order_book["bids"] = message["params"]["bids"]
                            xt_order_book["asks"] = message["params"]["asks"]
                            logging.info("XT.com order book updated.")

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
    token = fetch_websocket_token()
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
                    "id": int(time.time() * 1000),
                    "type": "subscribe",
                    # "topic": "/market/level2:BTC-USDT",
                    "topic": "/market/ticker:BTC-USDT",
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
                        if "data" in message and "bids" in message["data"] and "asks" in message["data"]:
                            kucoin_order_book["bids"] = message["data"]["bids"]
                            kucoin_order_book["asks"] = message["data"]["asks"]
                            logging.info("KuCoin order book updated.")

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
# Monitor Order Books
def monitor_order_books(interval=5):
    while True:
        try:
            logging.info("Order Book Snapshot:")
            for exchange, book in order_books.items():
                best_bid = book["bids"][0] if book["bids"] else ("N/A", "N/A")
                best_ask = book["asks"][0] if book["asks"] else ("N/A", "N/A")
                logging.info(f"{exchange} - Best Bid: {best_bid}, Best Ask: {best_ask}")
        except Exception as e:
            logging.error(f"Error monitoring order books: {e}")
        time.sleep(interval)


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
def start_heartbeat_threads(xt_client, kucoin_client):
    """Start heartbeat threads for both WebSocket clients."""
    xt_heartbeat_thread = threading.Thread(target=send_heartbeat, args=(xt_client,), daemon=True)
    kucoin_heartbeat_thread = threading.Thread(target=send_heartbeat, args=(kucoin_client,), daemon=True)

    xt_heartbeat_thread.start()
    kucoin_heartbeat_thread.start()

    logging.info("Heartbeat threads started.")


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
async def authenticate_all(XT_API_KEY, XT_SECRET_KEY, KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE):
    try:
        # Authenticate both XT and KuCoin concurrently
        await asyncio.gather(
            authenticate_xt(XT_API_KEY, XT_SECRET_KEY),
            authenticate_kucoin(KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE)
        )
        logging.info("Both XT and KuCoin authenticated successfully.")
    except Exception as e:
        logging.error(f"Authentication failed: {e}")
        raise SystemExit("Exiting program due to failed authentication.")

async def process_xt(queue):
    logging.info("Processing XT exchange...")
    await handle_xt_order_book_data(await authenticate_xt(XT_API_KEY, XT_SECRET_KEY), queue)
    print("XT processed, now switching to KuCoin.")
    await queue.put('kucoin')  # Add KuCoin to the queue for the next iteration

async def process_kucoin(queue):
    logging.info("Processing KuCoin exchange...")
    await handle_kucoin_order_book_data(await authenticate_kucoin(KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE), queue)
    print("KuCoin processed, now switching to XT.")
    await queue.put('xt')  # Add XT to the queue for the next iteration

async def main(XT_API_KEY, XT_SECRET_KEY, KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE):
    queue = asyncio.Queue()

    # Start by processing XT, then KuCoin, and alternate
    await queue.put('xt')

    # Authenticate both exchanges at the start
    await authenticate_all(XT_API_KEY, XT_SECRET_KEY, KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE)

    exchange_actions = {
        'xt': process_xt,
        'kucoin': process_kucoin,
    }

    while True:
        current_exchange = await queue.get()
        print(f"Processing {current_exchange} exchange...")

        # Call the appropriate function based on the exchange
        if current_exchange in exchange_actions:
            await exchange_actions[current_exchange](queue)

# Run the main function with the necessary API keys and secrets
asyncio.run(main(XT_API_KEY, XT_SECRET_KEY, KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE))