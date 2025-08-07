#!/usr/bin/env python3
"""
Script to send a test SMS message to the webhook endpoint in JustCall format.
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:8080/sms")
FROM_NUMBER = "3453"
MESSAGE = ""


def send_webhook_sms():
    """Send SMS message to webhook in JustCall format."""

    # JustCall webhook payload format
    payload = {"data": {"contact_number": FROM_NUMBER, "sms_info": {"body": MESSAGE}}}

    headers = {"Content-Type": "application/json"}

    try:
        print(f"Sending SMS webhook to: {WEBHOOK_URL}")
        print(f"From: {FROM_NUMBER}")
        print(f"Message: {MESSAGE}")
        print(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=30)

        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        if response.text:
            print(f"Response Body: {response.text}")
        else:
            print("Response Body: (empty)")

        if response.status_code == 204:
            print("✅ SMS webhook sent successfully!")
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error sending webhook: {e}")


if __name__ == "__main__":
    send_webhook_sms()
