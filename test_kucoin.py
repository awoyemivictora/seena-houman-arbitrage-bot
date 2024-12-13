import hmac
import base64
import time
import requests
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
KUCOIN_SECRET_KEY = os.getenv("KUCOIN_SECRET_KEY")
KUCOIN_PASSPHRASE = os.getenv("KUCOIN_PASSPHRASE")

url = "https://api.kucoin.com/api/v1/bullet-private"

# Generate signature
now = int(time.time() * 1000)
str_to_sign = f"{now}POST/api/v1/bullet-private"
signature = base64.b64encode(
    hmac.new(KUCOIN_SECRET_KEY.encode(), str_to_sign.encode(), digestmod="sha256").digest()
).decode()

# Use raw passphrase first
headers = {
    "KC-API-KEY": KUCOIN_API_KEY,
    "KC-API-SIGN": signature,
    "KC-API-TIMESTAMP": str(now),
    "KC-API-PASSPHRASE": KUCOIN_PASSPHRASE,  # Start with raw passphrase
    "Content-Type": "application/json",
}

response = requests.post(url, headers=headers)

# If the raw passphrase fails, try hashed passphrase
if response.json().get("code") == "400004":  # Invalid KC-API-PASSPHRASE
    hashed_passphrase = base64.b64encode(
        hmac.new(KUCOIN_SECRET_KEY.encode(), KUCOIN_PASSPHRASE.encode(), digestmod="sha256").digest()
    ).decode()

    headers["KC-API-PASSPHRASE"] = hashed_passphrase
    response = requests.post(url, headers=headers)

print(response.json())


