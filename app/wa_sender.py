import requests
import os

# Replace <your_phone_number_id> with actual phone number ID from Meta
META_API_URL = f"https://graph.facebook.com/v18.0/{os.getenv('META_PHONE_NUMBER_ID')}/messages"
META_TOKEN = os.getenv("META_ACCESS_TOKEN")

class WhatsAppSender:
    @staticmethod
    def send_message(phone_e164: str, text: str):
        headers = {
            "Authorization": f"Bearer {META_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_e164,
            "type": "text",
            "text": {"body": text}
        }
        resp = requests.post(META_API_URL, headers=headers, json=payload)
        return resp.json()
