from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
import uvicorn
import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io
import pandas as pd
from dotenv import load_dotenv
import asyncio
import nest_asyncio
import uuid
import time

# Import the direct processing functions
from processing_logic.data_analyzer import create_campaign_summary
from processing_logic.report_generator import create_powerpoint_report

# Load environment variables
load_dotenv()
nest_asyncio.apply()

app = FastAPI(title="Google Drive Webhook for Data Analysis")

# Configuration for folder IDs and paths
WATCHED_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")  # The folder ID to monitor
DOWNLOAD_PATH = "./data/"
CAMPAIGN_CONTENT_FILENAME = "campaign.csv"
TEMPLATE_PPTX_PATH = "./reports/template/template.pptx"
OUTPUT_PPTX_PATH = "./reports/generated_report.pptx"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Store active channel IDs and the current page token
active_webhook_channels = {}
current_page_token = None

# Store information about files being processed to prevent duplicates
processing_locks = {}
recently_processed_files = {}
processed_file_ids = {}
DUPLICATE_PREVENTION_TIMEOUT = 120  # 2 minutes in seconds


# Google Drive API setup
def get_drive_service():
    """Create and return a Google Drive service object using ADC."""
    try:
        # Use ADC - this will automatically use the credentials from gcloud auth application-default login
        from google.auth import default
        from google.auth.transport.requests import Request

        credentials, project = default(scopes=["https://www.googleapis.com/auth/drive"])

        # Refresh token if needed
        if hasattr(credentials, "refresh"):
            credentials.refresh(Request())

        return build("drive", "v3", credentials=credentials)
    except Exception as e:
        print(f"Error creating Drive service: {e}")
        raise


# Register webhook with Google Drive
def register_webhook():
    """Register a webhook with Google Drive for changes to the watched folder."""
    try:
        # Get Drive service
        service = get_drive_service()

        # Get the base URL for the webhook
        public_url = os.getenv("WEBHOOK_PUBLIC_URL")
        if not public_url:
            print("WARNING: WEBHOOK_PUBLIC_URL not set in .env file.")
            print("For production, set this to your public-facing URL.")
            print("For local development, use a service like ngrok.")
            return False

        webhook_url = f"{public_url}/webhook/google-drive"

        # Stop any existing webhooks
        for channel_id, details in list(active_webhook_channels.items()):
            try:
                print(f"Stopping existing webhook channel {channel_id}...")
                service.channels().stop(
                    body={
                        "id": channel_id,
                        "resourceId": details["resourceId"],
                    }
                ).execute()
                print(f"Successfully stopped channel {channel_id}")
                del active_webhook_channels[channel_id]
            except Exception as e:
                print(f"Error stopping channel {channel_id}: {e}")

        # Get start page token
        start_page_token_response = service.changes().getStartPageToken().execute()
        initial_page_token = start_page_token_response.get("startPageToken")

        if not initial_page_token:
            print("ERROR: Could not get initial start page token.")
            return False

        # Create a new notification channel
        channel_id = str(uuid.uuid4())
        expiration_time = int((time.time() + 3600 * 24) * 1000)  # 24 hours

        watch_response = (
            service.changes()
            .watch(
                pageToken=initial_page_token,
                restrictToMyDrive=True,
                spaces="drive",
                body={
                    "id": channel_id,
                    "type": "web_hook",
                    "address": webhook_url,
                    "token": WEBHOOK_SECRET,
                    "expiration": expiration_time,
                },
            )
            .execute()
        )

        # Store the channel info and the initial token
        resource_id = watch_response.get("resourceId")
        active_webhook_channels[channel_id] = {
            "resourceId": resource_id,
            "expiration": watch_response.get("expiration"),
        }

        # Store the initial token globally
        global current_page_token
        current_page_token = initial_page_token

        print(f"Webhook registered successfully: Channel ID={channel_id}")
        print(f"Started watching changes from page token: {current_page_token}")
        return True

    except Exception as e:
        print(f"Error registering webhook: {e}")
        import traceback

        traceback.print_exc()
        return False


# Function to download a file from Google Drive
async def download_file(file_id, filename):
    """Download a file from Google Drive by its ID and save it to the specified path."""
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)

    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_PATH, filename)

    with open(file_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

    return file_path


# Function to run the reporting to generate PowerPoint
async def generate_report():
    """Generate the PowerPoint report using the data analyzer output."""
    try:
        summary_csv_path = "./reports/generated_campaign_summary.csv"

        # Ensure the output directory exists
        os.makedirs(os.path.dirname(OUTPUT_PPTX_PATH), exist_ok=True)

        if not os.path.exists(summary_csv_path):
            print(f"Error: Summary CSV not found at {summary_csv_path}")
            return False

        if not os.path.exists(TEMPLATE_PPTX_PATH):
            print(f"Error: PowerPoint template not found at {TEMPLATE_PPTX_PATH}")
            return False

        print("Generating PowerPoint report...")
        generated_path = create_powerpoint_report(
            summary_csv_path=summary_csv_path,
            template_pptx_path=TEMPLATE_PPTX_PATH,
            output_pptx_path=OUTPUT_PPTX_PATH,
        )

        if generated_path:
            print(f"Report generated successfully at: {generated_path}")

            # Upload the generated report back to Google Drive
            print("Uploading report to Google Drive...")
            report_file_id = await upload_to_drive(
                OUTPUT_PPTX_PATH, "generated_report.pptx"
            )

            if report_file_id:
                print(f"Report uploaded to Google Drive with ID: {report_file_id}")
            else:
                print("Failed to upload report to Google Drive")
            return True
        else:
            print("PowerPoint generation failed.")
            return False

    except Exception as e:
        print(f"Error generating report: {e}")
        import traceback

        traceback.print_exc()
        return False


# Function to process campaign data file
async def process_campaign_data():
    """Analyze campaign data and generate summary."""
    try:
        campaign_path = os.path.join(DOWNLOAD_PATH, CAMPAIGN_CONTENT_FILENAME)
        if not os.path.exists(campaign_path):
            print(f"ERROR: Campaign file not found at {campaign_path}")
            return False

        # Check if this file is already being processed
        file_stat = os.stat(campaign_path)
        file_key = (
            f"{CAMPAIGN_CONTENT_FILENAME}_{file_stat.st_size}_{file_stat.st_mtime}"
        )

        # Set the processing lock
        processing_locks[file_key] = time.time()
        print(f"Processing file: {CAMPAIGN_CONTENT_FILENAME}")

        # Process the file
        print("Analyzing campaign data...")
        df_summary = create_campaign_summary(campaign_path)

        if df_summary is not None:
            # Save summary to CSV
            output_path = "./reports/generated_campaign_summary.csv"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            df_summary.to_csv(output_path, index=False)
            print(f"Summary saved to {output_path}")

            # Upload the summary CSV to Google Drive
            print("Uploading summary to Google Drive...")
            summary_drive_id = await upload_to_drive(
                output_path, "generated_campaign_summary.csv"
            )
            if summary_drive_id:
                print(f"Summary uploaded to Google Drive with ID: {summary_drive_id}")
            else:
                print("Failed to upload summary to Google Drive.")

            # Generate the PowerPoint report
            await generate_report()

            # Record that we processed this file
            recently_processed_files[file_key] = time.time()

            # Remove the processing lock
            if file_key in processing_locks:
                del processing_locks[file_key]

            return True
        else:
            print("Data analysis failed or returned no summary.")

            # Remove the processing lock
            if file_key in processing_locks:
                del processing_locks[file_key]

            return False

    except Exception as e:
        print(f"Error processing campaign data: {e}")
        import traceback

        traceback.print_exc()

        # Remove the processing lock on error
        if "file_key" in locals() and file_key in processing_locks:
            del processing_locks[file_key]

        return False


# Function to upload a file back to Google Drive
async def upload_to_drive(file_path, file_name):
    """Upload a file to the watched Google Drive folder."""
    try:
        service = get_drive_service()
        file_metadata = {"name": file_name, "parents": [WATCHED_FOLDER_ID]}
        media = MediaFileUpload(file_path, resumable=True)

        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )

        print(
            f"Successfully uploaded {file_name} to Google Drive with ID: {file.get('id')}"
        )
        return file.get("id")

    except Exception as e:
        print(f"Error uploading file to Google Drive: {e}")
        return None


# Cleanup utility
def cleanup_processing_records():
    """Clean up old processing records to avoid memory buildup."""
    current_time = time.time()

    # Clean locks older than 10 minutes
    for file_key in list(processing_locks.keys()):
        if current_time - processing_locks[file_key] > 600:  # 10 minutes
            del processing_locks[file_key]

    # Clean recently processed records older than 1 hour
    for file_key in list(recently_processed_files.keys()):
        if current_time - recently_processed_files[file_key] > 3600:  # 1 hour
            del recently_processed_files[file_key]


@app.post("/webhook/google-drive")
async def google_drive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook endpoint that receives notifications from Google Drive."""
    cleanup_processing_records()

    try:
        headers = dict(request.headers)
        print(f"Received webhook notification")

        # Verification request
        if headers.get("x-goog-resource-state") == "sync":
            print("Received verification request from Google")
            return {"status": "verified", "message": "Webhook verified"}

        # Get relevant headers
        resource_state = headers.get("x-goog-resource-state")
        changed = resource_state in ["add", "change", "update"]

        # Check token
        received_token = headers.get("x-goog-channel-token", "")
        if WEBHOOK_SECRET and received_token != WEBHOOK_SECRET:
            print(f"Token mismatch - unauthorized request")
            return {"status": "unauthorized", "message": "Invalid token"}

        if not changed:
            return {"status": "ignored", "message": f"Ignored state: {resource_state}"}

        # Process Drive changes
        service = get_drive_service()

        # List files in the watched folder
        print(f"Listing files in the watched folder...")
        results = (
            service.files()
            .list(
                q=f"'{WATCHED_FOLDER_ID}' in parents and trashed=false",
                fields="files(id, name, createdTime, modifiedTime)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )

        files = results.get("files", [])

        # Look for our campaign file
        for file in files:
            file_id = file.get("id")
            file_name = file.get("name")

            if file_name == CAMPAIGN_CONTENT_FILENAME:
                print(f"Found campaign file: {file_name}")

                # Check if recently processed
                current_time = time.time()
                if file_id in processed_file_ids:
                    last_time = processed_file_ids[file_id]
                    if current_time - last_time < DUPLICATE_PREVENTION_TIMEOUT:
                        print(f"Skipping recently processed file")
                        continue

                # Mark as processed
                processed_file_ids[file_id] = current_time

                # Download and process
                await download_file(file_id, file_name)
                background_tasks.add_task(process_campaign_data)

                return {"status": "processing", "message": f"Processing campaign file"}

        return {"status": "no_action", "message": "No relevant files found"}

    except Exception as e:
        print(f"Error processing webhook: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/register-webhook")
async def register_webhook_endpoint():
    """Endpoint to manually register the webhook."""
    success = register_webhook()
    if success:
        return {"status": "success", "message": "Webhook registered successfully"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to register webhook. Check server logs for details.",
        )


if __name__ == "__main__":
    # Try to register webhook on startup
    if os.getenv("WEBHOOK_PUBLIC_URL"):
        print("Attempting to register webhook on startup...")
        try:
            success = register_webhook()
            if success:
                print("Webhook registered successfully!")
            else:
                print(
                    "Failed to register webhook on startup. Server will start anyway."
                )
        except Exception as e:
            print(f"Error during webhook registration: {e}")
            print("Server will start without an active webhook registration.")
    else:
        print("WEBHOOK_PUBLIC_URL not set. Webhook registration skipped.")

    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000)
