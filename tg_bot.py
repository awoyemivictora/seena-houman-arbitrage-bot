import requests

bot_token = "8160702051:AAFAzAyDcTZsHV9EAwYNCZ-hua2aMhwlhhQ"  # Replace with your actual bot token
url = f"https://api.telegram.org/bot{bot_token}/getMe"

response = requests.get(url)

if response.status_code == 200:
    print("Token is valid!")
    print(response.json())
else:
    print("Invalid token!")
    print(response.json())
