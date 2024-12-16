import requests
import time
import hmac
import base64
import os
from dotenv import load_dotenv

# # Load environment variables from .env file
load_dotenv()

# KuCoin API credentials
KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
KUCOIN_SECRET_KEY = os.getenv("KUCOIN_SECRET_KEY")
KUCOIN_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")

def fetch_websocket_token():
    url = "https://api.kucoin.com/api/v1/bullet-private"
    now = int(time.time() * 1000)
    str_to_sign = f"{now}POST/api/v1/bullet-private"
    signature = base64.b64encode(
        hmac.new(KUCOIN_SECRET_KEY.encode(), str_to_sign.encode(), digestmod="sha256").digest()
    ).decode()

    headers = {
        "KC-API-KEY": KUCOIN_API_KEY,
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": str(now),
        "KC-API-PASSPHRASE": KUCOIN_PASSPHRASE,
    }

    response = requests.post(url, headers=headers)
    response_data = response.json()

    # Extract and return the token if the response is successful
    if response_data['code'] == '200000':
        token = response_data['data']['token']
        return token
    else:
        print(f"Erroor: {response_data['msg']}")
        return None

token = fetch_websocket_token()
# print(f"WebSocket Token: {token}")
