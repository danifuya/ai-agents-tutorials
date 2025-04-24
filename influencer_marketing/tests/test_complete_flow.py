"""
Test complete data processing flow by uploading both required files
"""

import os
import time
from google.auth import default
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

# Use absolute imports from the project root
from tests.test_upload import (
    create_test_campaign_content,
    upload_file,
)

# Load environment variables
load_dotenv()

FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")


# Functions moved to test_upload.py
# def create_test_campaign_content():
#     ...
# def create_test_influencer_profiles():
#     ...
# def upload_file(file_path, file_name=None):
#     ...


def check_webhook_processing():
    """Check if the webhook server has processed the files"""
    import requests

    try:
        response = requests.get("http://localhost:8000/test-drive-changes")
        print(f"Webhook test response: {response.json()}")
    except Exception as e:
        print(f"Error checking webhook: {e}")


if __name__ == "__main__":
    # Create only the campaign content file
    campaign_file = create_test_campaign_content()

    print("Uploading campaign content file...")
    # Upload the file
    upload_file(campaign_file, "campaign.csv")
    print("Waiting 5 seconds for changes to propagate...")
    time.sleep(5)

    # Check if webhook server processed the file
    print("Checking webhook processing status...")
    check_webhook_processing()

    print("\nTest complete. Check webhook server logs for details.")
