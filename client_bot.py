import asyncio
import websockets
import json
import time
from typing import Dict

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
import hmac
import hashlib
import aiohttp


import asyncio
import logging
from decimal import Decimal


#=================== 1. Initialize Logging: #===================
#    - Set up a logging system to capture bot activity and errors.
# Logging setup
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file = 'client_trading_bot.log'

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
# API Endpoints
XT_REST_URL = "https://sapi.xt.com/v4/public/depth"
XT_WS_URL = "wss://stream.xt.com/public"

# Variables for order book synchronization
lastUpdateId_xt = None
buffered_events = []

KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
KUCOIN_SECRET_KEY = os.getenv("KUCOIN_SECRET_KEY")
KUCOIN_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")
KUCOIN_BASE_URL = "https://api.kucoin.com"

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
#     'xt': {
#         'bids': deque(maxlen=5),
#         'asks': deque(maxlen=5),
#     },
#     'kucoin': {
#         'bids': deque(maxlen=5),
#         'asks': deque(maxlen=5),
#     }
# }

# Initialize order books
order_books = {
    "kucoin": {"bids": [], "asks": []},
    "xt": {"bids": [], "asks": []}
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


# Trading configuration
LONG_EXCHANGE = "kucoin"
SHORT_EXCHANGE = "xt"
SYMBOL = "BTC"
TOTAL_AMOUNT = 1.0
CHUNK_SIZE = 0.1
SPREAD = 0.001


trades = []  # To keep track of executed trades



# Function to get user inputs
async def get_user_inputs():
    """
    Prompt user for initial parameters.
    """
    long_exchange = input("Enter Long Exchange (e.g., kucoin): ").lower()
    short_exchange = input("Enter Short Exchange (e.g., xt): ").lower()
    symbol = input("Enter Symbol (e.g., BTC): ").upper()
    total_amount = Decimal(input("Enter Total Amount in tokens (e.g., 1.0): "))
    chunk_size = Decimal(input("Enter Chunk Size (e.g., 0.1): "))
    spread = Decimal(input("Enter Spread as decimal (e.g., 0.01 for 1%): "))

    print(f"Total USD Value: {await calculate_usd_value(symbol, long_exchange, total_amount)}")
    return long_exchange, short_exchange, symbol, total_amount, chunk_size, spread


# Function for symbol adjustments
async def adjust_symbol(exchange, symbol, amount):
    """
    Adjust symbol based on exchange-specific rules.
    """
    if exchange == "kucoin":
        if symbol == "BTC":
            symbol = "XBTUSDTM"
        elif symbol in ["BONK"]:
            symbol = "1000" + symbol + "USDTM"
            amount /= 1000
        elif symbol in ["SLP"]:
            return "-", amount
        else:
            symbol = symbol + "USDTM"
    elif exchange == "xt":
        if symbol in ["PEPE", "BONK", "SHIB", "FLOKI"]:
            symbol = "1000" + symbol.lower() + "_usdt"
            amount /= 1000
        else:
            symbol = symbol.lower() + "_usdt"
    return symbol, amount


# Function to calculate spread
async def calculate_spread(order_books, long_exchange, short_exchange):
    """
    Calculate orderbook spread.
    """
    long_best_bid = Decimal(order_books[long_exchange]["bids"][0][0])
    long_best_ask = Decimal(order_books[long_exchange]["asks"][0][0])
    short_best_bid = Decimal(order_books[short_exchange]["bids"][0][0])
    short_best_ask = Decimal(order_books[short_exchange]["asks"][0][0])

    spread_sell = (long_best_ask / short_best_bid) - 1
    spread_buy = (short_best_bid / long_best_bid) - 1

    return spread_sell, spread_buy


# Function to place orders
async def place_orders(long_exchange, short_exchange, symbol, chunk_size, spread):
    """
    Place limit orders on both exchanges.
    """
    long_best_bid = Decimal(order_books[long_exchange]["bids"][0][0])
    short_best_ask = Decimal(order_books[short_exchange]["asks"][0][0])

    # Place limit order to buy on Long exchange
    buy_price = long_best_bid * (1 - spread)
    print(f"Placing BUY order on {long_exchange} at {buy_price} for {chunk_size} {symbol}")

    # Place limit order to sell on Short exchange
    sell_price = short_best_ask * (1 + spread)
    print(f"Placing SELL order on {short_exchange} at {sell_price} for {chunk_size} {symbol}")

    # Simulate order placement (replace with actual API calls)
    await asyncio.sleep(0.1)


# Function to execute market order
async def execute_market_order(exchange, side, amount, symbol):
    """
    Execute market orders when a limit order is filled.
    """
    print(f"Executing {side.upper()} market order on {exchange} for {amount} {symbol}")
    # Simulate order execution (replace with actual API calls)
    await asyncio.sleep(0.1)


# Function to manage trading
async def manage_trading(long_exchange, short_exchange, symbol, total_amount, chunk_size, spread):
    """
    Main trading logic.
    """
    remaining_amount = total_amount
    while remaining_amount > 0:
        # Read order books
        spread_sell, spread_buy = await calculate_spread(order_books, long_exchange, short_exchange)

        # Place limit orders
        await place_orders(long_exchange, short_exchange, symbol, chunk_size, spread)

        # Simulate checking order statuses
        filled_amount = Decimal("0.05")  # Mock filled amount
        remaining_amount -= filled_amount

        # Execute market orders based on fills
        await execute_market_order(long_exchange, "buy", filled_amount, symbol)
        await execute_market_order(short_exchange, "sell", filled_amount, symbol)

        print(f"Remaining Amount to Trade: {remaining_amount} {symbol}")

        # Repeat until total amount is traded
        await asyncio.sleep(1)


# Function to calculate usd value
async def calculate_usd_value(symbol, exchange, amount):
    """
    Calculate the USD equivalent of the total amount.
    """
    best_bid = Decimal(order_books[exchange]["bids"][0][0])
    usd_value = best_bid * amount
    return usd_value



















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
                self.update_order_book("xt", data["bids"], data["asks"])
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
                self.update_order_book("kucoin", data["bids"], data["asks"])
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




#============= ALL KUCOIN.COM INTERACTIONS =============
# Instantiating with python-kucoin
client = Client(KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE)

# Function to generate the signature for KuCoin API requests
def generate_kucoin_signature(api_secret, api_passphrase, method, endpoint, body=None, key_version="2"):
    """
    Generate the KuCoin API signature and passphrase.

    Args:
        api_secret (str): The API secret.
        api_passphrase (str): The API passphrase.
        method (str): HTTP method (GET, POST, DELETE).
        endpoint (str): The request path (e.g., /api/v1/orders).
        body (dict or None): The request body as a dictionary, if any.
        key_version (str): API key version (default is "2").

    Returns:
        dict: A dictionary containing the signature, timestamp, and headers.
    """
    # Ensure the HTTP method is uppercase
    method = method.upper()

    # Serialize body if provided; otherwise, use an empty string
    body = json.dumps(body) if body else ""

    # Create the timestamp in milliseconds
    timestamp = str(int(time.time() * 1000))

    # Create the string to sign
    str_to_sign = f"{timestamp}{method}{endpoint}{body}"

    # Generate the signature
    signature = base64.b64encode(
        hmac.new(api_secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    ).decode('utf-8')

    # Generate the passphrase
    encoded_passphrase = base64.b64encode(
        hmac.new(api_secret.encode('utf-8'), api_passphrase.encode('utf-8'), hashlib.sha256).digest()
    ).decode('utf-8')

    # Return the signature and headers
    headers = {
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": timestamp,
        "KC-API-KEY": KUCOIN_API_KEY,
        "KC-API-PASSPHRASE": encoded_passphrase,
        "KC-API-KEY-VERSION": key_version,
        "Content-Type": "application/json"
    }
    return headers


# For encryptinng the API passphrase
def encrypt_passphrase():
    """
    Encrypt the API passphrase for secure transmission.
    """
    return base64.b64encode(hmac.new(KUCOIN_SECRET_KEY.encode(), KUCOIN_PASSPHRASE.encode(), hashlib.sha256).digest()).decode()


# Helper to generate headers for authentication
def generate_kucoin_headers(api_key, api_secret, api_passphrase, method, endpoint, data=""):
    now = str(int(time.time() * 1000))
    str_to_sign = f"{now}{method.upper()}{endpoint}{data}"
    signature = base64.b64encode(hmac.new(api_secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())
    passphrase = base64.b64encode(hmac.new(api_secret.encode('utf-8'), api_passphrase.encode('utf-8'), hashlib.sha256).digest())
    
    headers = {
        "KC-API-KEY": api_key,
        "KC-API-SIGN": signature.decode(),
        "KC-API-TIMESTAMP": now,
        "KC-API-PASSPHRASE": passphrase.decode(),
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }
    return headers

# Asynchronous Function to check KuCoin Balance
async def check_balance(client, symbol):
    account_balances = client.get_account_balance()
    print(account_balances)
    # Verify the required currency has enough balance.



# For Authenticating & Connecting to Kucoin.com Private Websocket
async def authenticate_kucoin_websocket(api_key, secret_key, passphrase):
    """
    Establish a private WebSocket connection to KuCoin and handle trading events.
    """
    # Use the valid token retrieved
    token = fetch_websocket_token()
    connect_id = str(uuid.uuid4())  # Generate a unique connect ID

    # Construct WebSocket URL with token and connect ID
    stream_url = f"wss://ws-api-spot.kucoin.com/?token={token}&connectId={connect_id}"

    async with websockets.connect(stream_url, ping_interval=30, ping_timeout=10) as websocket:
        # Wait for the welcome message
        response = await websocket.recv()
        logging.info(f"Welcome message received: {response}")

        # Subscribe to a private topic (e.g., orders, account balance)
        subscription_message = {
            "id": int(time.time() * 1000),
            "type": "subscribe",
            "topic": "/spotMarket/tradeOrders",
            "privateChannel": True,
            "response": True,
        }
        await websocket.send(json.dumps(subscription_message))
        logging.info(f"Subscription Message sent to KuCoin WebSocket Server: {subscription_message}")

        while True:
            response = await websocket.recv()
            try:
                message = json.loads(response)
                logging.info(f"You're now Connected to KuCoin.com private WebSocket. {message}")

                # Handle specific messages (e.g., order updates, balances)
                if "data" in message:
                    process_kucoin_order_update(message["data"])

            except json.JSONDecodeError:
                logging.error(f"Failed to parse JSON: {response}")

    logging.error("KuCoin WebSocket failed after maximum retries.")


# For processing the incoming order updates from the Kucoin WebSocket
async def process_kucoin_order_update(data):
    """
    Process private WebSocket messages for orders and balances.
    """
    if "type" in data:
        if data["type"] == "match":
            logging.info(f"Order match event: {data}")
        elif data["type"] == "done":
            logging.info(f"Order completion event: {data}")
        else:
            logging.info(f"Other private message: {data}")


# Function to place a limit order
async def place_limit_order_kucoin(api_key, api_secret, api_passphrase, symbol, side, price, size, time_in_force="GTC"):
    endpoint = "/api/v1/orders"
    url = KUCOIN_BASE_URL + endpoint

    # Unique client ID
    client_oid = str(uuid.uuid4())

    # Request payload
    payload = {
        "clientOid": client_oid,
        "side": side,  # "buy" or "sell"
        "symbol": symbol,
        "type": "limit",
        "price": str(price),
        "size": str(size),
        "timeInForce": time_in_force  # Default is "GTC"
    }

    headers = generate_kucoin_headers(api_key, api_secret, api_passphrase, "POST", endpoint, json.dumps(payload))
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        print("Error placing limit order:", response.json())
        return None


# Function to place a market order
async def place_market_order_kucoin(api_key, api_secret, api_passphrase, symbol, side, size=None, funds=None):
    """
    Either size or funds must be provided for a market order.
    """
    if not size and not funds:
        raise ValueError("Either 'size' or 'funds' must be specified for market orders.")
    
    endpoint = "/api/v1/orders"
    url = KUCOIN_BASE_URL + endpoint

    # Unique client ID
    client_oid = str(uuid.uuid4())

    # Request payload
    payload = {
        "clientOid": client_oid,
        "side": side,  # "buy" or "sell"
        "symbol": symbol,
        "type": "market"
    }

    if size:
        payload["size"] = str(size)
    elif funds:
        payload["funds"] = str(funds)

    headers = generate_kucoin_headers(api_key, api_secret, api_passphrase, "POST", endpoint, json.dumps(payload))
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        print("Error placing market order:", response.json())
        return None


# Asynchronous Function to cancel all orders on KuCoin
def cancel_all_orders_kucoin(api_key, api_secret, api_passphrase, symbol=None):
    """
    Cancel all open orders for a symbol on KuCoin.

    Args:
        api_key (str): The API key.
        api_secret (str): The API secret.
        api_passphrase (str): The API passphrase.
        symbol (str or None): The symbol for which to cancel orders (e.g., BTC-USDT). If None, cancel all orders.

    Returns:
        dict: The API response as a dictionary.
    """
    method = "DELETE"
    endpoint = "/api/v1/orders"
    
    # Add symbol query string if provided
    if symbol:
        endpoint += f"?symbol={symbol}"

    # Generate signature and headers
    headers = generate_kucoin_signature(
        api_secret=api_secret,
        api_passphrase=api_passphrase,
        method=method,
        endpoint=endpoint
    )

    # Define the base URL
    base_url = "https://api.kucoin.com"

    # Make the API request
    response = requests.delete(base_url + endpoint, headers=headers)

    # Handle response
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error cancelling orders: {response.status_code} - {response.text}")


# Function to cancel an order by it's ID on KuCoin
def cancel_order_by_id_kucoin(order_id, api_key, api_secret, api_passphrase):
    """
    Cancel a single order on KuCoin using the orderId.

    Parameters:
    - order_id (str): The unique ID of the order to cancel.
    - api_key (str): Your KuCoin API key.
    - api_secret (str): Your KuCoin API secret.
    - api_passphrase (str): Your KuCoin API passphrase.

    Returns:
    - dict: The response from KuCoin API.
    """
    url = f"https://api.kucoin.com/api/v1/orders/{order_id}"
    method = "DELETE"
    now = int(time.time() * 1000)

    # Prepare the string to sign
    str_to_sign = f"{now}{method}/api/v1/orders/{order_id}"
    signature = base64.b64encode(
        hmac.new(api_secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    )

    passphrase = base64.b64encode(
        hmac.new(api_secret.encode('utf-8'), api_passphrase.encode('utf-8'), hashlib.sha256).digest()
    )

    headers = {
        "KC-API-SIGN": signature.decode('utf-8'),
        "KC-API-TIMESTAMP": str(now),
        "KC-API-KEY": api_key,
        "KC-API-PASSPHRASE": passphrase.decode('utf-8'),
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }

    # Make the DELETE request
    response = requests.delete(url, headers=headers)

    if response.status_code == 200:
        logging.info("Order cancelled successfully!")
    else:
        logging.info(f"Error cancelling order: {response.status_code}, {response.text}")

    return response.json()


# Function to place multiple orders on KuCoin
def place_multiple_orders_kucoin(api_key, api_secret, api_passphrase, symbol, order_list):
    """
    Place multiple limit orders on KuCoin.
    
    Parameters:
        api_key (str): Your KuCoin API key.
        api_secret (str): Your KuCoin API secret.
        api_passphrase (str): Your KuCoin API passphrase.
        symbol (str): The trading symbol (e.g., "KCS-USDT").
        order_list (list): A list of orders, each being a dictionary with order details:
                           [
                               {
                                   "side": "buy" or "sell",
                                   "price": "order_price",
                                   "size": "order_size"
                               },
                               ...
                           ]
    
    Returns:
        dict: The response from KuCoin API.
    """
    url = "https://api.kucoin.com/api/v1/orders/multi"
    method = "POST"
    now = int(time.time() * 1000)

    # Construct the order list with unique clientOid for each order
    formatted_order_list = [
        {
            "clientOid": str(uuid.uuid4()),  # Unique identifier for each order
            "side": order["side"],
            "type": "limit",
            "price": order["price"],
            "size": order["size"]
        }
        for order in order_list
    ]

    # Request payload
    payload = {
        "symbol": symbol,
        "orderList": formatted_order_list
    }

    # Convert payload to JSON string
    payload_str = json.dumps(payload)

    # Prepare the string to sign
    str_to_sign = f"{now}{method}/api/v1/orders/multi{payload_str}"
    signature = base64.b64encode(
        hmac.new(api_secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    )

    passphrase = base64.b64encode(
        hmac.new(api_secret.encode('utf-8'), api_passphrase.encode('utf-8'), hashlib.sha256).digest()
    )

    # Request headers
    headers = {
        "Content-Type": "application/json",
        "KC-API-SIGN": signature.decode('utf-8'),
        "KC-API-TIMESTAMP": str(now),
        "KC-API-KEY": api_key,
        "KC-API-PASSPHRASE": passphrase.decode('utf-8'),
        "KC-API-KEY-VERSION": "2"
    }

    # Make the POST request
    response = requests.post(url, headers=headers, data=payload_str)
    logging.info(response.json())

    # Return the API response
    return response.json()


#******* For Getting KuCoin's Market Updates ****************
async def process_kucoin_level2_updates(message):
    """
    Process Level 2 updates for KuCoin and update the shared order_books dictionary.
    """
    global order_books

    data = message["data"]
    changes = data["changes"]
    sequence_start = data["sequenceStart"]
    sequence_end = data["sequenceEnd"]

    # Ensure sequence continuity
    kucoin_order_book = order_books['kucoin']
    if "sequence" in kucoin_order_book and sequence_start > kucoin_order_book["sequence"] + 1:
        logging.warning("KuCoin sequence gap detected. Consider re-synchronizing the order book.")
        return

    kucoin_order_book["sequence"] = sequence_end

    # Process asks and bids
    for change_type, updates in changes.items():
        for update in updates:
            price, size, _ = update
            price = float(price)
            size = float(size)

            # Update order book
            if change_type == "asks":
                if size == 0:
                    kucoin_order_book["asks"] = deque([ask for ask in kucoin_order_book["asks"] if ask[0] != price], maxlen=5)
                else:
                    kucoin_order_book["asks"].append((price, size))
                    kucoin_order_book["asks"] = deque(sorted(kucoin_order_book["asks"])[:5], maxlen=5)
            elif change_type == "bids":
                if size == 0:
                    kucoin_order_book["bids"] = deque([bid for bid in kucoin_order_book["bids"] if bid[0] != price], maxlen=5)
                else:
                    kucoin_order_book["bids"].append((price, size))
                    kucoin_order_book["bids"] = deque(sorted(kucoin_order_book["bids"], reverse=True)[:5], maxlen=5)

    logging.info(f"Updated KuCoin order book. Current top 5 bids and asks:\nBids: {list(kucoin_order_book['bids'])}\nAsks: {list(kucoin_order_book['asks'])}")


async def subscribe_to_kucoin_level2(symbol): # This function will await process_kucoin_level2_updates
    """
    Subscribe to the Level 2 market data for a specific symbol and update the shared order_books dictionary.
    """
    token = fetch_websocket_token()  # Fetch this via API
    connect_id = str(uuid.uuid4())
    stream_url = f"wss://ws-api-spot.kucoin.com/?token={token}&connectId={connect_id}"

    async with websockets.connect(stream_url, ping_interval=30, ping_timeout=10) as websocket:
        # Wait for the welcome message
        response = await websocket.recv()
        logging.info(f"Connected to KuCoin WebSocket: {response}")

        # Subscribe to the Level 2 data for the symbol
        subscription_message = {
            "id": int(time.time() * 1000),
            "type": "subscribe",
            "topic": f"/market/level2:{symbol}",
            "response": True,
        }
        await websocket.send(json.dumps(subscription_message))
        logging.info(f"KuCoin subscription sent: {subscription_message}")

        # Process incoming messages
        while True:
            response = await websocket.recv()
            try:
                message = json.loads(response)
                if "data" in message:
                    await process_kucoin_level2_updates(message)
            except json.JSONDecodeError:
                logging.error(f"Failed to parse KuCoin JSON: {response}")




#============= ALL XT.COM INTERACTIONS =============
# Generating the signature for XT API requests
def generate_xt_signature(params):
    """
    Generate a signature for XT API requests.
    """
    query_string = "&".join(f"{key}={value}" for key, value in sorted(params.items()))
    signature = hmac.new(
        XT_SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


# For Authenticating & Connecting to XT.com Private Websocket
async def authenticate_xt_websocket():
    """
    Authenticate and subscribe to XT WebSocket for private order updates.
    """
    ws_url = "wss://stream.xt.com/private"  # Replace with the private WebSocket endpoint
    timestamp = int(time.time() * 1000)
    
    # Generate authentication payload
    auth_payload = {
        "method": "login",
        "params": {
            "api_key": XT_API_KEY,
            "timestamp": timestamp,
            "sign": generate_xt_signature({
                "api_key": XT_API_KEY,
                "timestamp": timestamp
            })
        },
        "id": 1
    }

    try:
        async with websockets.connect(ws_url, ping_interval=30, ping_timeout=10) as websocket:
            logging.info("You're now Connected to XT.com private WebSocket.")
            
            # Authenticate WebSocket
            await websocket.send(json.dumps(auth_payload))
            auth_response = await websocket.recv()
            logging.info(f"You've successfully Authenticated to XT.com WebSocket: {auth_response}")

            # Check authentication success
            response = json.loads(auth_response)
            if response.get("code") != 0:
                logging.error("Your XT.com WebSocket authentication failed.")
                return

            # Subscribe to order updates
            subscribe_message = {
                "method": "subscribe",
                "params": ["order"],  # Subscribe to order updates
                "id": 2
            }
            await websocket.send(json.dumps(subscribe_message))
            logging.info(f"Your Subscription message has been sent to XT.com Websocket: {subscribe_message}")

            # Listen for updates
            while True:
                message = await websocket.recv()
                logging.info(f"XT.com Order update received: {message}")

                # Process order updates
                process_xt_order_update(json.loads(message))
    except Exception as e:
        logging.error(f"XT.com WebSocket connection error: {e}")


# For processing the incoming order updates from the XT WebSocket
def process_xt_order_update(message):
    """
    Processes the WebSocket order update message.
    """
    if "params" in message:
        params = message["params"]

        if "status" in params:
            status = params["status"]
            order_id = params.get("clientOrderId", "Unknown")

            if status == "FILLED":
                logging.info(f"Order {order_id} fully filled.")
            elif status == "PARTIALLY_FILLED":
                logging.info(f"Order {order_id} partially filled.")
            elif status == "CANCELED":
                logging.info(f"Order {order_id} canceled.")
            else:
                logging.info(f"Order {order_id} status updated: {status}")

        # Additional processing (e.g., updating local state or database)


# Place limit order on XT.com        
async def place_limit_order_xt(symbol, price, quantity, side):
    """
    Places a limit order on XT.com
    """
    endpoint = "https://api.xt.com/v4/order" 
    params = {
        "symbol": symbol,
        "side": side,  # BUY or SELL
        "type": "LIMIT",
        "timeInForce": "GTC",  # Good Till Canceled
        "bizType": "SPOT",  # SPOT or LEVER
        "price": price,
        "quantity": quantity,
        "clientOrderId": f"order_{int(time.time())}"  # Optional client-generated ID (Unique identifiier for tracking each orders sent to xt.com)
    }

    # Sign the request
    params["api_key"] = XT_API_KEY
    params["timestamp"] = str(int(time.time() * 1000))
    params["sign"] = generate_xt_signature(params)  # Assuming generate_signature exists

    # Submit the order
    try:
        response = requests.post(endpoint, data=params)
        response_json = response.json()

        if response.status_code == 200 and response_json.get("code") == 0:
            logging.info(f"XT Limit Order Success: {response_json}")
            return response_json
        else:
            logging.error(f"XT Limit Order Failed: {response_json}")
            return response_json
    except Exception as e:
        logging.error(f"Error placing XT limit order: {e}")
        return {"error": str(e)}


# Place market order on xt
async def place_market_order_xt(symbol, amount, side, is_quantity=True):
    """
    Places a market order on XT.com.
    `is_quantity`: If True, places order using quantity; otherwise, uses quoteQty.
    """
    endpoint = "https://api.xt.com/v4/order" 
    params = {
        "symbol": symbol,
        "side": side,  # BUY or SELL
        "type": "MARKET",
        "timeInForce": "GTC",  # Effective time not needed but included for consistency
        "bizType": "SPOT",  # SPOT or LEVER
        "clientOrderId": f"order_{int(time.time())}"  # Optional client-generated ID
    }

    # For BUY orders, use quoteQty; for SELL orders, use quantity
    if side == "BUY" and not is_quantity:
        params["quoteQty"] = amount  # Order based on the total amount to spend
    elif side == "SELL" and is_quantity:
        params["quantity"] = amount  # Order based on the number of units to sell
    else:
        raise ValueError("Invalid parameters for market order.")

    # Sign the request
    params["api_key"] = XT_API_KEY
    params["timestamp"] = str(int(time.time() * 1000))
    params["sign"] = generate_xt_signature(params)

    # Submit the order
    try:
        response = requests.post(endpoint, data=params)
        response_json = response.json()

        if response.status_code == 200 and response_json.get("code") == 0:
            logging.info(f"XT Market Order Success: {response_json}")
            return response_json
        else:
            logging.error(f"XT Market Order Failed: {response_json}")
            return response_json
    except Exception as e:
        logging.error(f"Error placing XT market order: {e}")
        return {"error": str(e)}


# Cancel all orders on XT.com
async def cancel_all_orders_xt(symbol):
    """
    Cancels all orders for the given symbol on XT.com.
    """
    endpoint = "https://api.xt.com/v4/order" 
    params = {
        "symbol": symbol,
        "api_key": XT_API_KEY,
        "timestamp": str(int(time.time() * 1000))
    }
    params["sign"] = generate_xt_signature(params)

    try:
        response = requests.post(endpoint, data=params)
        response_json = response.json()

        if response.status_code == 200 and response_json.get("code") == 0:
            logging.info(f"XT Cancel All Orders Success: {response_json}")
            return response_json
        else:
            logging.error(f"XT Cancel All Orders Failed: {response_json}")
            return response_json
    except Exception as e:
        logging.error(f"Error canceling XT orders: {e}")
        return {"error": str(e)}


# Cancel multiple orders on XT.com
def cancel_multiple_orders_xt(api_key, api_secret, order_ids, base_url="https://api.xt.com"):
    """
    Cancel multiple orders on XT.com using their IDs.
    
    :param api_key: Your XT.com API Key
    :param api_secret: Your XT.com API Secret
    :param order_ids: A list of order IDs to cancel
    :param base_url: Base URL for the XT API (default: "https://api.xt.com")
    :return: Response from the XT API
    """
    # Endpoint URL
    url = f"{base_url}/v4/batch-order"
    
    # Request body
    body = {
        "orderIds": order_ids
    }
    
    # XT requires a signature for authentication
    timestamp = str(int(time.time() * 1000))  # Current time in milliseconds
    body_str = json.dumps(body)
    prehash = f"{timestamp}POST/v4/batch-order{body_str}"
    signature = hmac.new(
        api_secret.encode('utf-8'),
        prehash.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Headers for the request
    headers = {
        "XT-APIKEY": api_key,
        "XT-TIMESTAMP": timestamp,
        "XT-SIGN": signature,
        "Content-Type": "application/json"
    }
    
    # Send the request
    try:
        response = requests.post(url, headers=headers, data=body_str)
        response.raise_for_status()  # Raise exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None



#******* For Getting XT's Market Updates ****************
"""
1. Connect to the WebSocket Stream
- Open a WebSocket stream to wss://stream.xt.com/public and subscribe to depth_update@btc_usdt.
- Buffer incoming incremental depth updates.
2. Fetch Initial Snapshot
- Request the depth snapshot using the REST API endpoint:
https://sapi.xt.com/v4/public/depth?symbol=btc_usdt&limit=500.
- Store the lastUpdateId from the snapshot and initialize the order book with its bids and asks.
3. Process Buffered Events
- Discard any events with fi (firstUpdateId) less than or equal to lastUpdateId.
- Ensure the first processed event meets the condition:
fi <= lastUpdateId + 1 and i >= lastUpdateId + 1.
4. Apply Incremental Updates
- Update the bids and asks from each new event.
- Remove price levels where the quantity is 0.
- Ensure event sequence integrity: new_event.fi == previous_event.i + 1.
5. Maintain a Local Order Book
- Store a deque for the top 5 bids and asks in the order_books dictionary for XT.com, similar to KuCoin.
"""
async def fetch_xt_market_depth_snapshot(symbol="btc_usdt"):
    """Fetch initial depth snapshot asynchronously."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(XT_REST_URL, params={"symbol": symbol, "limit": 500}) as response:
                response_json = await response.json()
                if response_json.get('rc') == 0 and response_json.get('result'):
                    await process_fetched_xt_market_depth(response_json['result'])
                else:
                    logging.error("Failed to fetch XT market depth snapshot. Invalid response.")
    except Exception as e:
        logging.error(f"Error fetching XT market depth snapshot: {e}")


# Asynchronous function to process the fetched json response received from xt.com and save it in the local order_books['xt'] for both bids and asks
async def process_fetched_xt_market_depth(data):
    """
    Processes and updates the order book with bids and asks.
    :param data: The parsed JSON 'result' containing bids and asks.
    """
    try:
        bids = data.get('bids', [])
        asks = data.get('asks', [])

        if bids:
            order_books['xt']['bids'] = deque(
                [(float(price), float(size)) for price, size in bids], maxlen=5
            )
            logging.info(f"Successfully saved order_books['xt']['bids'] {bids}")
        else:
            logging.warning("No bids received in the update.")

        if asks:
            order_books['xt']['asks'] = deque(
                [(float(price), float(size)) for price, size in asks], maxlen=5
            )
            logging.info(f"Successfully saved order_books['xt']['asks'] {asks}")
        else:
            logging.warning("No asks received in the update.")

        logging.info(f"XT Market Depth updated.")
        logging.info(f"Top 5 Bids: {list(order_books['xt']['bids'])}")
        logging.info(f"Top 5 Asks: {list(order_books['xt']['asks'])}")
    except Exception as e:
        logging.error(f"Error processing market depth: {e}")



# Websocket connection to get and retrieve live market data from xt and store it's highest and lowest bids/asks in the local order book
# async def xt_websocket(symbol="btc_usdt"):
#     """Connect to XT WebSocket and manage order book updates."""
#     try:
#         async with websockets.connect(XT_WS_URL) as websocket:
#             # Subscribe to depth updates
#             subscription_message = {
#                 "topic": f"depth_update@{symbol}",
#                 "event": "subscribe"
#             }
#             await websocket.send(json.dumps(subscription_message))
#             logging.info(f"Subscribed to XT market depth updates for {symbol}.")

#             # Fetch the initial depth snapshot
#             await fetch_xt_market_depth_snapshot(symbol)

#             # Listen to WebSocket updates
#             async for message in websocket:
#                 try:
#                     data = json.loads(message)
#                     if data.get("event") == "depth_update":
#                         # Process the real-time update
#                         await process_fetched_xt_market_depth(data["data"])
#                 except Exception as e:
#                     logging.error(f"Error processing WebSocket message: {e}")
#     except Exception as e:
#         logging.error(f"WebSocket connection error: {e}")



async def xt_websocket(api_key, secret_key):
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

                        # Process data
                        if "data" in message and "a" in message["data"] and "b" in message["data"]:
                            asks = message["data"]["a"]
                            bids = message["data"]["b"]

                            # Update the global order_books
                            order_books["xt"]["asks"] = deque(
                                [(float(price), float(size)) for price, size in asks if float(size) > 0], maxlen=500
                            )
                            order_books["xt"]["bids"] = deque(
                                [(float(price), float(size)) for price, size in bids if float(size) > 0], maxlen=500
                            )

                            logging.info("XT.com order book updated.")
                            logging.info(f"Top 5 Asks: {list(order_books['xt']['asks'])[:5]}")
                            logging.info(f"Top 5 Bids: {list(order_books['xt']['bids'])[:5]}")

                        else:
                            logging.warning("XT.com message does not contain valid bids and asks.")
                    except json.JSONDecodeError:
                        logging.error(f"Invalid JSON received from XT.com: {response}")
                    except Exception as e:
                        logging.error(f"Error processing XT.com message: {e}")
        
        except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e:
            logging.warning(f"XT.com WebSocket connection closed: {e}")
            retries += 1
            await asyncio.sleep(2 ** retries)  # Exponential backoff
        
        except Exception as e:
            logging.error(f"Error authenticating XT: {e}")
            retries += 1
            await asyncio.sleep(2 ** retries)

    logging.error("XT.com WebSocket failed after maximum retries.")






#========================== 

# WebSocket listeners for order book updates
async def listen_orderbook(exchange, symbol, orderbook_queue):
    ws_url = f"wss://{exchange}/ws/{symbol}/orderbook"  # Placeholder WebSocket URL
    async with websockets.connect(ws_url, timeout=30) as websocket:
        while True:
            message = await websocket.recv()
            orderbook = json.loads(message)
            await orderbook_queue.put(orderbook)


# Symbol adjustments for different exchanges
def adjust_symbol(symbol, exchange, amount):
    if exchange == "kucoin":
        if symbol == "BTC":
            symbol = "XBTUSDTM"
        elif symbol == "BONK":
            symbol = "1000BONKUSDTM"
            amount = amount / 1000
        elif symbol == "SLP":
            return "-", amount
        else:
            symbol = symbol + "USDTM"
    elif exchange == "xt":
        if symbol in ["PEPE", "BONK", "SHIB", "FLOKI"]:
            symbol = "1000" + symbol.lower() + "_usdt"
            amount = amount / 1000
        else:
            symbol = symbol.lower() + "_usdt"
    return symbol, amount

# Trade loop
async def trade_loop():
    remaining_amount = TOTAL_AMOUNT
    orderbook_queue = asyncio.Queue()

    # Launch WebSocket listeners for both exchanges
    asyncio.create_task(listen_orderbook(LONG_EXCHANGE, SYMBOL, orderbook_queue))
    asyncio.create_task(listen_orderbook(SHORT_EXCHANGE, SYMBOL, orderbook_queue))

    while remaining_amount > 0:
        orderbook_update = await orderbook_queue.get()  # Wait for an order book update

        if orderbook_update.get('exchange') == LONG_EXCHANGE:
            long_orderbook = orderbook_update
        elif orderbook_update.get('exchange') == SHORT_EXCHANGE:
            short_orderbook = orderbook_update

        # Extract best bid/ask prices and quantities
        long_best_bid = long_orderbook['bids'][0]['price'] if 'bids' in long_orderbook else 0
        long_best_bid_quantity = long_orderbook['bids'][0]['quantity'] if 'bids' in long_orderbook else 0
        short_best_ask = short_orderbook['asks'][0]['price'] if 'asks' in short_orderbook else 0
        short_best_ask_quantity = short_orderbook['asks'][0]['quantity'] if 'asks' in short_orderbook else 0

        # Calculate the limit order prices based on the spread
        long_limit_price = short_best_ask * (1 - SPREAD)
        short_limit_price = long_best_bid * (1 + SPREAD)

        # Determine the order amounts
        long_chunk = min(CHUNK_SIZE, short_best_ask_quantity)
        short_chunk = min(CHUNK_SIZE, long_best_bid_quantity)

        # Place limit orders on both exchanges
        await place_limit_order(LONG_EXCHANGE, SYMBOL, long_limit_price, long_chunk, "BUY")
        await place_limit_order(SHORT_EXCHANGE, SYMBOL, short_limit_price, short_chunk, "SELL")

        # Monitor orders and react to partial fills
        while True:
            long_position = await get_positions(LONG_EXCHANGE, SYMBOL)
            short_position = await get_positions(SHORT_EXCHANGE, SYMBOL)

            if long_position['filled'] > 0:
                # Place a market sell order on the short exchange for the filled amount
                await place_market_order(SHORT_EXCHANGE, SYMBOL, long_position['filled'], "SELL")
                await cancel_all_orders(LONG_EXCHANGE, SYMBOL)  # Reset orders
                remaining_amount -= long_position['filled']
                break

            if short_position['filled'] > 0:
                # Place a market buy order on the long exchange for the filled amount
                await place_market_order(LONG_EXCHANGE, SYMBOL, short_position['filled'], "BUY")
                await cancel_all_orders(SHORT_EXCHANGE, SYMBOL)  # Reset orders
                remaining_amount -= short_position['filled']
                break

            await asyncio.sleep(0.1)  # Small delay for polling


# # Main function to start the bot
# if __name__ == "__main__":
#     asyncio.run(trade_loop())


#============= TESTING EACH FUNCTIONS ================
#============== kucoin endpoint functions testing =======
#**** Testing the WebSocket connection to kucoin
# async def main():
#     KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
#     KUCOIN_SECRET_KEY = os.getenv("KUCOIN_SECRET_KEY")
#     KUCOIN_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")

#     await authenticate_kucoin_websocket(KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE)

# if __name__ == "__main__":
#     asyncio.run(main())

#**** Testing the order placements on kucoin
# if __name__ == "__main__":
#     KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
#     KUCOIN_SECRET_KEY = os.getenv("KUCOIN_SECRET_KEY")
#     KUCOIN_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")
#     KUCOIN_BASE_URL = "https://api.kucoin.com"

#     # Place a limit order
#     limit_order_response = place_limit_order_kucoin(
#         KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE,
#         symbol="BTC-USDT",
#         side="buy",
#         price="100000",
#         size="0.0001"
#     )
#     print("Limit Order Response:", limit_order_response)

#     # Place a market order
#     market_order_response = place_market_order_kucoin(
#      KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE,
#         symbol="BTC-USDT",
#         side="buy",
#         funds="1"  # Use funds or size
#     )
#     print("Market Order Response:", market_order_response)

#**** Testing order cancellations both ALL ORDERS or SPECIFIC ORDER on kucoin
# async def main():
#     KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
#     KUCOIN_SECRET_KEY = os.getenv("KUCOIN_SECRET_KEY")
#     KUCOIN_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")
#     symbol = 'BTC-USDT'  # Optional, set to None to cancel all orders
#     order_id = "5bd6e9286d99522a52e458de"
    
#     try:
#         # response = cancel_all_orders_kucoin(KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE, symbol=symbol) # To cancel all open orders on KuCoin
#         response = cancel_order_by_id_kucoin(order_id, KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE) # To cancel a specific order
#         print(response)
#         if response:
#             print("KuCoin Cancelled Order IDs:", response)
#         else:
#             print("No orders cancelled on KuCoin.")
#     except Exception as e:
#         print("Error:", e)

#**** Testing multiple orders on kucoin
# async def main():
    
#     KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
#     KUCOIN_SECRET_KEY = os.getenv("KUCOIN_SECRET_KEY")
#     KUCOIN_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")
#     symbol = "KCS-USDT"
#     order_list = [
#     {"side": "buy", "price": "0.05", "size": "2"},  # Total = 0.05 * 2 = 0.1 USDT
#     {"side": "buy", "price": "0.02", "size": "5"},  # Total = 0.02 * 5 = 0.1 USDT
#     {"side": "sell", "price": "0.03", "size": "4"}  # Total = 0.03 * 4 = 0.12 USDT
#     ]
    
#     try:
#         response = place_multiple_orders_kucoin(KUCOIN_API_KEY, KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE, symbol, order_list)
#         print(response)
#         if response:
#             print("Multiple Orders Successfully placed on KuCoin:", response)
#         else:
#             print("KuCoin Multiple Orders wasn't placed. Try again.")
#     except Exception as e:
#         print("Error:", e)

# # Run the example
# asyncio.run(main())

#**** Testing level2 market updates from kucoin via websocket
# async def main():
#     """
#     Main function to start the WebSocket subscription.
#     """
#     symbol = "BTC-USDT"  # Replace with your desired trading pair
#     await subscribe_to_kucoin_level2(symbol)


# # Run the WebSocket client
# if __name__ == "__main__":
#     asyncio.run(main())



#============== xt.com endpoint functions testing =====
# if __name__ == "__main__":
#     XT_API_KEY = os.getenv("XT_API_KEY")
#     XT_SECRET_KEY = os.getenv("XT_SECRET_KEY")

#     # Place a limit order
#     limit_order_response = asyncio.run(place_limit_order_xt(
#         symbol="BTC-USDT",
#         price="100000",
#         quantity="0.001",
#         side="BUY"
#     ))
#     print("Limit Order Response:", limit_order_response)

#     # Place a market order
#     market_order_response = asyncio.run(place_market_order_xt(
#         symbol="BTC-USDT",
#         amount="0.001",
#         side="BUY"
#     ))
#     print("Market Order Response:", market_order_response)


#**** Testing Multiple order cancellation on xt
# if __name__ == "__main__":
#     XT_API_KEY = os.getenv("XT_API_KEY")
#     XT_SECRET_KEY = os.getenv("XT_SECRET_KEY")
#     order_ids = ["6216559590087220004", "6216559590087220005"]

#     # Place a limit order
#     response = response = cancel_multiple_orders_xt(XT_API_KEY, XT_SECRET_KEY, order_ids)
#     logging.info(response)


# Connecting to XT's market data via websocket
# asyncio.run(xt_websocket(XT_API_KEY, XT_SECRET_KEY))







#============== FETCHING BOTH KUCOIN & XT MARKET DATA CONCURRENTLY AND SAVING IT IN THE order_books =========
# Assuming order_books is a shared dictionary for both KuCoin and XT
async def fetch_kucoin_data():
    """
    Fetch live market data from KuCoin and save to order_books["kucoin"].
    """
    symbol = "BTC-USDT"  # Replace with your desired trading pair
    while True:
        try:
            await subscribe_to_kucoin_level2(symbol)  # Assuming this updates order_books["kucoin"]
        except Exception as e:
            logging.error(f"Error fetching data from KuCoin: {e}")
        await asyncio.sleep(0.1)  # Small delay to prevent overloading

async def fetch_xt_data(api_key, secret_key):
    """
    Fetch live market data from XT.com and save to order_books["xt"].
    """
    while True:
        try:
            await xt_websocket(api_key, secret_key)  # Assuming this updates order_books["xt"]
        except Exception as e:
            logging.error(f"Error fetching data from XT: {e}")
        await asyncio.sleep(0.1)  # Small delay to prevent overloading

async def monitor_order_books():
    """
    Periodically logs the contents of the order_books.
    """
    while True:
        logging.info(f"KuCoin Order Book: {order_books['kucoin']}")
        logging.info(f"XT Order Book: {order_books['xt']}")
        await asyncio.sleep(2)  # Log every 5 seconds

# async def main():
#     """
#     Main function to run both tasks concurrently.
#     # """

#     await asyncio.gather(
#         fetch_kucoin_data(),
#         fetch_xt_data(XT_API_KEY, XT_SECRET_KEY),
#         monitor_order_books()
#     )

# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         logging.info("Program interrupted. Exiting...")









async def main():
    """
    Main function to initialize and run the trading bot.
    """
    # Get user inputs
    long_exchange, short_exchange, symbol, total_amount, chunk_size, spread = await get_user_inputs()

    # Adjust symbols for both exchanges
    symbol, total_amount = await adjust_symbol(long_exchange, symbol, total_amount)
    symbol, total_amount = await adjust_symbol(short_exchange, symbol, total_amount)

    # Start WebSocket connections (replace with actual implementations)
    await asyncio.gather(
        subscribe_to_kucoin_level2(symbol),
        xt_websocket(XT_API_KEY, XT_SECRET_KEY),
        manage_trading(long_exchange, short_exchange, symbol, total_amount, chunk_size, spread),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
