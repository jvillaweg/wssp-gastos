import requests
import os
import logging

logger = logging.getLogger(__name__)

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Replace <your_phone_number_id> with actual phone number ID from Meta
META_API_URL = f"https://graph.facebook.com/v23.0/{os.getenv('META_PHONE_NUMBER_ID')}/messages"
META_TOKEN = os.getenv("META_ACCESS_TOKEN")

class WhatsAppSender:
    @staticmethod
    def send_message(phone_e164: str, text: str):
        try:
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
            # Add timeout to prevent hanging
            resp = requests.post(META_API_URL, headers=headers, json=payload, timeout=5)
            return resp.json()
        except requests.exceptions.ConnectTimeout:
            logger.warning(f"⚠️ Timeout sending message to {phone_e164} - Lambda VPC has no internet access")
            return {"error": "network_timeout", "message": "VPC needs internet access"}
        except Exception as e:
            logger.error(f"❌ Error sending message to {phone_e164}: {e}")
            return {"error": str(e)}
