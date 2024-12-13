# import requests

# bot_token = "8160702051:AAFAzAyDcTZsHV9EAwYNCZ-hua2aMhwlhhQ"
# url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

# response = requests.get(url)
# print(response.json())




import requests

bot_token = "8160702051:AAFAzAyDcTZsHV9EAwYNCZ-hua2aMhwlhhQ"
chat_id = "382532635"
message = "Test message"

url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
data = {"chat_id": chat_id, "text": message}

response = requests.post(url, data=data)
print(response.json())
