"""
Simple test script to upload files and process them directly.
This bypasses the webhook mechanism for easy testing.
"""

import os
import asyncio
from dotenv import load_dotenv

# Use absolute imports from the project root - updated path
from processing_logic.direct_processing import main as process_files
from tests.test_upload import (
    create_test_campaign_content,
    upload_file,
)

# Load environment variables
load_dotenv()


async def test_workflow():
    """Upload test files and process them directly."""
    print("=== SIMPLE WORKFLOW TEST (Single File) ===\n")
    print("1. Creating test campaign file...")

    # Create test file
    campaign_file = create_test_campaign_content()

    print("2. Uploading campaign file to Google Drive...")

    # Upload files to Google Drive
    campaign_id = upload_file(campaign_file, "campaign_content_english.csv")

    print(f"Uploaded campaign file with ID: {campaign_id}")

    # Process the files directly
    print("\n3. Processing campaign file directly...")
    await process_files()

    print("\n=== TEST COMPLETED ===")
    print("If successful, you should see a generated_report.pptx in both:")
    print("- Local reports directory (./reports/)")
    print("- Google Drive folder")


if __name__ == "__main__":
    asyncio.run(test_workflow())
