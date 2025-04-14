import os
import requests
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")


def send_whatsapp_message(to: str, body: str):
    """
    Calls the WhatsApp Cloud API to send a text message.
    """
    url = f"https://graph.facebook.com/v15.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        # Handle errors, log them, etc.
        print("Error sending message:", response.text)
        response.raise_for_status()
