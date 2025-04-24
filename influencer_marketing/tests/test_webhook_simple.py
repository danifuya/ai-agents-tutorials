#!/usr/bin/env python3
"""
Simple test script to check if the webhook server can detect files in the watched folder.
"""

import os
import time
import requests
from google.auth import default
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
WEBHOOK_SERVER = (
    "http://localhost:8000"  # Change this if your server is on a different port
)


def get_drive_service():
    """Get authenticated Google Drive service."""
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/drive"])

    # Refresh token if needed
    if hasattr(credentials, "refresh"):
        credentials.refresh(Request())

    return build("drive", "v3", credentials=credentials)


def upload_test_file():
    """Create and upload a test file to the watched folder."""
    print("\n1. Creating test file...")
    timestamp = int(time.time())

    # Create two test files - a generic test file and a campaign file
    test_filename = f"webhook_test_{timestamp}.txt"
    campaign_filename = "campaign.csv"  # Updated to the new expected filename

    # Create the test file
    with open(test_filename, "w") as f:
        f.write(f"Test file created at {time.ctime()}\n")
        f.write(f"This file is used to test webhook notifications\n")

    # Create a simple campaign CSV file
    with open(campaign_filename, "w") as f:
        f.write(
            "campaign_id,influencer_handle,post_url,post_type,impressions,reach,likes,comments,saves\n"
        )
        f.write(
            "campaign1,@influencer1,http://example.com/post1,image,10000,5000,500,50,20\n"
        )

    print(f"2. Uploading test files: {test_filename} and {campaign_filename}")

    service = get_drive_service()

    # Create file metadata for the test file
    file_metadata = {
        "name": test_filename,
        "parents": [FOLDER_ID],
        "description": "Webhook test file",
    }

    # Upload the test file
    media = MediaFileUpload(test_filename, resumable=True)
    file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id,name")
        .execute()
    )

    # Upload the campaign file
    campaign_metadata = {
        "name": campaign_filename,
        "parents": [FOLDER_ID],
        "description": "Campaign test file",
    }

    campaign_media = MediaFileUpload(campaign_filename, resumable=True)
    campaign_file = (
        service.files()
        .create(body=campaign_metadata, media_body=campaign_media, fields="id,name")
        .execute()
    )

    # Clean up local files
    os.remove(test_filename)
    os.remove(campaign_filename)

    print(f"✅ Files uploaded successfully:")
    print(f"   - Test file: {file.get('name')} (ID: {file.get('id')})")
    print(
        f"   - Campaign file: {campaign_file.get('name')} (ID: {campaign_file.get('id')})"
    )

    return campaign_file.get("id"), campaign_file.get("name")


def check_webhook_detection():
    """Check if the webhook server detected the uploaded file."""
    print("\n3. Waiting 5 seconds for changes to propagate...")
    time.sleep(5)

    print("4. Checking if webhook server detected changes...")
    try:
        response = requests.get(f"{WEBHOOK_SERVER}/test-drive-changes", timeout=15)
        if response.status_code == 200:
            result = response.json()
            print(f"  Status: {result.get('status')}")
            print(f"  Message: {result.get('message')}")

            files = result.get("files", [])
            file_count = result.get("file_count", 0)

            if files:
                print("  Files found:")
                for file in files:
                    print(f"    - {file}")
                return True
            elif file_count:
                print(f"  Files found: {file_count}")
                return True
            else:
                print("  No files detected by webhook server")
                return False
        else:
            print(f"  Error: HTTP {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"  Error checking webhook: {e}")
        return False


def reset_webhook():
    """Reset the webhook by re-registering it."""
    print("\n5. Re-registering webhook...")
    try:
        response = requests.get(f"{WEBHOOK_SERVER}/register-webhook", timeout=10)
        if response.status_code == 200:
            print("  ✅ Webhook re-registered successfully")
            return True
        else:
            print(f"  Error: HTTP {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"  Error re-registering webhook: {e}")
        return False


def main():
    """Run the webhook test."""
    print("=== WEBHOOK DETECTION TEST ===")

    # 1. Upload a test file
    file_id, file_name = upload_test_file()

    # 2. Check if the webhook server detects the file
    detected = check_webhook_detection()

    if not detected:
        print("\n⚠️ Test file was not detected by the webhook server.")
        print("Attempting to fix the issue by re-registering the webhook...")

        # 3. Reset the webhook
        reset_webhook()

        # 4. Check again after reset
        print("\n6. Checking again after webhook reset...")
        detected_after_reset = check_webhook_detection()

        if detected_after_reset:
            print("\n✅ Success! The webhook is now working after re-registration.")
        else:
            print("\n❌ Webhook still not detecting files after re-registration.")
            print("Try restarting the webhook server completely.")
    else:
        print("\n✅ Success! The webhook server detected the test file.")

    print("\nTest completed.")


if __name__ == "__main__":
    main()
