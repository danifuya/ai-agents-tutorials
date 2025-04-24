from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
import uvicorn
from pydantic import BaseModel
import os
import json
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import pandas as pd
from dotenv import load_dotenv
import asyncio
import nest_asyncio
import uuid
import requests
import time
# Removed agent imports
# from agents.data_analysis_agent import data_analysis_agent, AnalysisDependencies
# from agents.reporting_agent import reporting_agent, ReportingDependencies

# Import the new direct functions from the new location
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
INFLUENCER_PROFILES_FILENAME = "influencer_profiles_english.csv"
TEMPLATE_PPTX_PATH = "./reports/template/template.pptx"
OUTPUT_PPTX_PATH = "./reports/generated_report.pptx"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_CHANNEL_ID = str(uuid.uuid4())  # Generate a unique channel ID

# Store active channel IDs and the current page token
active_webhook_channels = {}
current_page_token = None  # Global variable to store the last known page token

# Store information about files being processed to prevent duplicates
processing_locks = {}
recently_processed_files = {}

# Simple dictionary to track processed files by ID, with timestamp
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
        # For local development, you might need to use a service like ngrok
        # to expose your local server to the internet
        # Example: webhook_url = "https://your-ngrok-url.ngrok.io/webhook/google-drive"
        public_url = os.getenv("WEBHOOK_PUBLIC_URL")
        if not public_url:
            print("WARNING: WEBHOOK_PUBLIC_URL not set in .env file.")
            print("For production, set this to your public-facing URL.")
            print("For local development, use a service like ngrok.")
            return False

        webhook_url = f"{public_url}/webhook/google-drive"

        # First, stop any existing webhooks to avoid duplicates
        # This is critical to prevent multiple webhooks causing confusing behavior
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

        # Register for changes to all files (Drive API limitation)
        # We need the start page token to initialize our change tracking
        print("Fetching initial start page token for webhook...")
        start_page_token_response = service.changes().getStartPageToken().execute()
        initial_page_token = start_page_token_response.get("startPageToken")
        print(f"Initial page token: {initial_page_token}")

        if not initial_page_token:
            print("ERROR: Could not get initial start page token.")
            return False

        # Create a new notification channel
        channel_id = str(uuid.uuid4())
        resource_id = None  # We will store the resourceId after successful registration
        expiration_time = int(
            (time.time() + 3600 * 24) * 1000
        )  # 24 hours in milliseconds

        watch_response = (
            service.changes()
            .watch(
                pageToken=initial_page_token,  # Watch changes starting from this token
                restrictToMyDrive=True,  # Watch only the user's My Drive
                supportsAllDrives=False,
                includeCorpusRemovals=False,
                includeItemsFromAllDrives=False,
                spaces="drive",  # This is important to watch the Drive space
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

        print(
            f"Webhook registered successfully: Channel ID={channel_id}, Resource ID={resource_id}"
        )
        print(f"Started watching changes from page token: {current_page_token}")
        print(
            f"Webhook expires around: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expiration_time / 1000))}"
        )
        return True

    except Exception as e:
        print(f"Error registering webhook: {e}")
        import traceback

        traceback.print_exc()
        return False


# Unregister webhook from Google Drive
def unregister_webhook(channel_id):
    """Unregister a webhook from Google Drive."""
    if channel_id not in active_webhook_channels:
        print(f"Channel ID {channel_id} not found in active channels.")
        return False

    try:
        service = get_drive_service()

        # Stop the notification channel
        service.channels().stop(
            body={
                "id": channel_id,
                "resourceId": active_webhook_channels[channel_id]["resourceId"],
            }
        ).execute()

        # Remove from active channels
        del active_webhook_channels[channel_id]

        print(f"Webhook channel {channel_id} unregistered successfully.")
        return True

    except Exception as e:
        print(f"Error unregistering webhook: {e}")
        return False


# Webhook notification model
class DriveNotification(BaseModel):
    kind: str
    id: str
    file_id: str
    file_name: str
    changed: bool


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


# Function to run the reporting agent to generate PowerPoint
async def generate_report():
    """Generate the PowerPoint report using the direct function."""
    try:
        # Changed from data to reports directory to match where the file is actually saved
        summary_csv_path = "./reports/generated_campaign_summary.csv"

        # Ensure the output directory exists
        os.makedirs(os.path.dirname(OUTPUT_PPTX_PATH), exist_ok=True)

        if not os.path.exists(summary_csv_path):
            print(f"Error: Summary CSV not found at {summary_csv_path}")
            return False

        if not os.path.exists(TEMPLATE_PPTX_PATH):
            print(f"Error: PowerPoint template not found at {TEMPLATE_PPTX_PATH}")
            return False

        # Removed ReportingDependencies
        # deps = ReportingDependencies(...)

        # Removed user_prompt for agent
        # user_prompt = f"..."

        print("Running direct PowerPoint generation function...")  # Updated log
        # Call the direct function
        generated_path = create_powerpoint_report(
            summary_csv_path=summary_csv_path,
            template_pptx_path=TEMPLATE_PPTX_PATH,
            output_pptx_path=OUTPUT_PPTX_PATH,
        )

        if generated_path:
            print(
                f"Report generation function finished successfully. Path: {generated_path}"
            )
            # Upload the generated report back to Google Drive
            print("Uploading report back to Google Drive...")
            report_file_id = await upload_to_drive(
                OUTPUT_PPTX_PATH, "generated_report.pptx"
            )

            if report_file_id:
                print(
                    f"Report uploaded successfully to Google Drive with ID: {report_file_id}"
                )
            else:
                print("Failed to upload report to Google Drive")
            return True
        else:
            print("Direct PowerPoint generation function failed.")  # Updated log
            return False

    except Exception as e:
        print(f"An error occurred while generating the report: {e}")  # Updated log
        import traceback

        traceback.print_exc()
        return False


# Function to run data analysis after file download
async def process_campaign_data():
    """Run the data analysis using the direct function."""
    try:
        # Only requires the campaign content CSV now
        campaign_path = os.path.join(DOWNLOAD_PATH, CAMPAIGN_CONTENT_FILENAME)
        if not os.path.exists(campaign_path):
            print(
                f"ERROR: Campaign content file not found at {campaign_path} for processing."
            )
            return False

        # Check if this file is already being processed
        file_stat = os.stat(campaign_path)
        file_key = (
            f"{CAMPAIGN_CONTENT_FILENAME}_{file_stat.st_size}_{file_stat.st_mtime}"
        )

        # Skip if we recently processed this exact file
        if file_key in recently_processed_files:
            last_processed = recently_processed_files[file_key]
            if time.time() - last_processed < 60:  # Within last minute
                print(
                    f"Skipping duplicate processing of {CAMPAIGN_CONTENT_FILENAME} (processed {int(time.time() - last_processed)} seconds ago)"
                )
                return True

        # Skip if this file is currently being processed
        if file_key in processing_locks:
            print(f"Skipping {CAMPAIGN_CONTENT_FILENAME} - already being processed")
            return True

        # Set the processing lock
        processing_locks[file_key] = time.time()
        print(f"Starting to process {file_key}")

        # Process the file
        print("Running direct data analysis function...")  # Updated log
        # Call the direct function
        df_summary = create_campaign_summary(campaign_path)

        # Convert to DataFrame for saving to CSV (function already returns DataFrame)
        if df_summary is not None:
            # Define the output path in the reports folder
            output_path = "./reports/generated_campaign_summary.csv"
            # Ensure the reports directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            df_summary.to_csv(output_path, index=False)
            print(f"Summary saved locally to {output_path}")

            # Upload the summary CSV to Google Drive
            print(f"Uploading summary CSV to Google Drive...")
            summary_drive_id = await upload_to_drive(
                output_path, "generated_campaign_summary.csv"
            )
            if summary_drive_id:
                print(
                    f"Summary CSV uploaded successfully to Google Drive with ID: {summary_drive_id}"
                )
            else:
                print("Failed to upload summary CSV to Google Drive.")

            # Now run the reporting function to generate the PowerPoint
            await generate_report()

            # Record that we processed this file
            recently_processed_files[file_key] = time.time()
            # Remove the processing lock
            if file_key in processing_locks:
                del processing_locks[file_key]

            return True
        else:
            print(
                "Direct data analysis function failed or returned no summary."
            )  # Updated log

            # Remove the processing lock even if failed
            if file_key in processing_locks:
                del processing_locks[file_key]

            return False

    except Exception as e:
        print(f"An error occurred while processing campaign data: {e}")  # Updated log
        import traceback

        traceback.print_exc()

        # Make sure to remove the processing lock on error
        if "file_key" in locals() and file_key in processing_locks:
            del processing_locks[file_key]

        return False


# Function to upload a file back to Google Drive
async def upload_to_drive(file_path, file_name):
    """Upload a file to the watched Google Drive folder."""
    try:
        service = get_drive_service()

        file_metadata = {"name": file_name, "parents": [WATCHED_FOLDER_ID]}

        from googleapiclient.http import MediaFileUpload

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


# Function to clean up old processing records (add this to avoid memory leaks)
def cleanup_processing_records():
    """Clean up old processing records to avoid memory buildup."""
    current_time = time.time()
    # Clean locks older than 10 minutes (something went wrong)
    for file_key in list(processing_locks.keys()):
        if current_time - processing_locks[file_key] > 600:  # 10 minutes
            print(f"Cleaning up stale processing lock for {file_key}")
            del processing_locks[file_key]

    # Clean recently processed records older than 1 hour
    for file_key in list(recently_processed_files.keys()):
        if current_time - recently_processed_files[file_key] > 3600:  # 1 hour
            del recently_processed_files[file_key]


@app.post("/webhook/google-drive")
async def google_drive_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook endpoint that receives notifications from Google Drive.
    Google Drive webhooks use a specific format with a verification token.
    """
    # Clean up old processing records
    cleanup_processing_records()

    try:
        # Google Drive sends a notification with headers but often an empty body
        # The important information is in the headers
        headers = dict(request.headers)

        # Log all headers for debugging
        print(f"Received webhook notification with headers: {headers}")

        # Check if this is a verification request (Google verifies the webhook first)
        if headers.get("x-goog-resource-state") == "sync":
            print("Received sync/verification request from Google")
            return {"status": "verified", "message": "Webhook verified"}

        # Get relevant headers
        resource_state = headers.get("x-goog-resource-state")
        resource_id = headers.get("x-goog-resource-id")
        changed = resource_state in ["add", "change", "update"]

        # Check the verification token
        received_token = headers.get("x-goog-channel-token", "")

        if WEBHOOK_SECRET and received_token != WEBHOOK_SECRET:
            print(
                f"Token mismatch. Expected: {WEBHOOK_SECRET}, Received: {received_token}"
            )
            return {"status": "unauthorized", "message": "Invalid token"}

        if not changed:
            return {
                "status": "ignored",
                "message": f"Ignored resource state: {resource_state}",
            }

        # Get resource ID from the notification
        if not resource_id:
            print("Missing resource ID in notification")
            return {"status": "ignored", "message": "Missing resource ID"}

        # Get the change details from Drive API
        print(f"Processing change notification for resource: {resource_id}")

        # Use a short delay to ensure the changes are propagated in Drive
        await asyncio.sleep(2)

        # Now fetch recent changes using the stored page token
        global current_page_token  # Use the global token
        service = get_drive_service()

        if not current_page_token:
            # Fallback: If token is lost, get a fresh one, but log it.
            print(
                "WARNING: current_page_token is missing. Fetching a new start page token."
            )
            response = service.changes().getStartPageToken().execute()
            current_page_token = response.get("startPageToken")
            if not current_page_token:
                print(
                    "ERROR: Could not fetch start page token. Cannot process changes."
                )
                raise HTTPException(
                    status_code=500, detail="Webhook state error: Missing page token"
                )

        # List all changes since the last known token
        changes = []
        page_token_to_fetch = current_page_token  # Start from the last known token
        print(f"Fetching changes starting from token: {page_token_to_fetch}")

        while True:  # Loop until no more pages
            try:
                print(f"  Requesting changes with token: {page_token_to_fetch}")
                response = (
                    service.changes()
                    .list(
                        pageToken=page_token_to_fetch,
                        spaces="drive",
                        fields="nextPageToken, newStartPageToken, changes(fileId, file(name, parents))",
                        restrictToMyDrive=True,
                        pageSize=100,  # Fetch more changes per page
                    )
                    .execute()
                )
            except Exception as e:
                print(f"ERROR fetching changes: {e}")
                # Handle common token expiration error (simplified handling)
                if "Invalid startPageToken" in str(e) or "401" in str(e):
                    print(
                        "Page token likely expired or invalid. Fetching new start token."
                    )
                    response = service.changes().getStartPageToken().execute()
                    current_page_token = response.get("startPageToken")
                    print(f"Reset current_page_token to: {current_page_token}")
                    # We should probably re-register the webhook here in a real app
                    # For now, just stop processing this notification to avoid loops
                    raise HTTPException(
                        status_code=500,
                        detail="Webhook state error: Page token expired",
                    )
                else:
                    raise  # Re-raise other errors

            current_changes = response.get("changes", [])
            print(f"  Found {len(current_changes)} changes on this page")
            changes.extend(current_changes)

            # Get the next page token for the next iteration
            next_page_token = response.get("nextPageToken")

            if next_page_token:
                print(f"  Next page token exists: {next_page_token}. Continuing fetch.")
                page_token_to_fetch = next_page_token
                # IMPORTANT: Update the global token *immediately* after getting the next page
                current_page_token = next_page_token
            else:
                # If no nextPageToken, the newStartPageToken represents the latest state
                new_start_page_token = response.get("newStartPageToken")
                print(
                    f"  No more pages. Updating global token to newStartPageToken: {new_start_page_token}"
                )
                current_page_token = new_start_page_token
                break  # Exit the while loop

        print(f"Total changes fetched this time: {len(changes)}")
        print(f"Global page token is now: {current_page_token}")

        # Process each changed file
        processed_relevant_file = False
        for change in changes:
            file_id = change.get("fileId")
            file_data = change.get("file", {})

            # Skip if file was removed (file data may be None or removed flag is True)
            if not file_data or change.get("removed", False):
                print(f"  Skipping change: File with ID {file_id} was removed")
                continue

            file_name = file_data.get("name", "")
            parents = file_data.get("parents", [])

            print(
                f"Processing change: File ID={file_id}, Name='{file_name}', Parents={parents}"
            )

            if not file_id or not file_name:
                print("  Skipping change: Missing file ID or name")
                continue

            if WATCHED_FOLDER_ID not in parents:
                print(
                    f"  Skipping change: File not in watched folder {WATCHED_FOLDER_ID}"
                )
                continue

            print(f"  File '{file_name}' is in the watched folder.")

            # Check if we've recently processed this file ID
            current_time = time.time()
            if file_id in processed_file_ids:
                last_processed_time = processed_file_ids[file_id]
                elapsed_seconds = current_time - last_processed_time

                if elapsed_seconds < DUPLICATE_PREVENTION_TIMEOUT:
                    print(
                        f"  DUPLICATE PREVENTION: Skipping file {file_name} (ID: {file_id})"
                    )
                    print(f"  It was processed {elapsed_seconds:.1f} seconds ago")
                    continue
                else:
                    print(
                        f"  File was processed before, but {elapsed_seconds:.1f} seconds have passed. Processing again."
                    )

            # Handle based on filename
            if file_name == CAMPAIGN_CONTENT_FILENAME:
                print(f"  Detected relevant file: {CAMPAIGN_CONTENT_FILENAME}")
                # Download the campaign content file
                print(f"  Attempting to download {CAMPAIGN_CONTENT_FILENAME}...")
                file_path = await download_file(file_id, CAMPAIGN_CONTENT_FILENAME)
                print(f"  Downloaded campaign content file to {file_path}")

                # Mark this file ID as processed with current timestamp
                processed_file_ids[file_id] = current_time
                print(
                    f"  Marked file ID {file_id} as processed at {time.ctime(current_time)}"
                )

                # Trigger processing immediately
                print("  Triggering background processing...")
                background_tasks.add_task(process_campaign_data)
                processed_relevant_file = True

                # Clean up older entries to prevent memory growth
                clean_old_processed_ids()

                return {
                    "status": "processing",
                    "message": "Campaign content file received, processing started",
                }

            # Handle template file upload if needed
            elif file_name.endswith(".pptx") and "template" in file_name.lower():
                print(f"  Detected template file: {file_name}")
                # Download and save as template
                template_dir = os.path.dirname(TEMPLATE_PPTX_PATH)
                os.makedirs(template_dir, exist_ok=True)

                # Download the template file
                print(f"  Attempting to download template file...")
                await download_file(file_id, os.path.basename(TEMPLATE_PPTX_PATH))
                print("  Template file updated.")
                processed_relevant_file = True
                return {"status": "success", "message": "Template file updated"}
            else:
                print(
                    "  Skipping change: File name does not match required files or template pattern."
                )

        # If loop finished without processing a relevant file from the notification
        if not processed_relevant_file:
            print("No relevant file changes processed for this notification.")

        return {
            "status": "processed",
            "message": "Notification processed, no relevant action taken",
        }

    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Error processing webhook: {str(e)}"
        )


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


@app.get("/unregister-webhook/{channel_id}")
async def unregister_webhook_endpoint(channel_id: str):
    """Endpoint to manually unregister a webhook."""
    success = unregister_webhook(channel_id)
    if success:
        return {
            "status": "success",
            "message": f"Webhook {channel_id} unregistered successfully",
        }
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Failed to unregister webhook {channel_id}. Check server logs for details.",
        )


@app.get("/list-webhooks")
async def list_webhooks_endpoint():
    """Endpoint to list all active webhook channels."""
    return {"active_channels": active_webhook_channels}


@app.get("/test-drive-changes")
async def test_drive_changes(background_tasks: BackgroundTasks):
    """
    Test endpoint to manually check for Drive changes and process them.
    """
    try:
        print("Manually checking for Drive changes...")

        # Get Drive service
        service = get_drive_service()

        # Declare global variable first before using it
        global current_page_token

        # For testing, we'll use a fresh start token to check recent changes
        # This helps detect changes that might have been missed by the webhook
        fresh_token = None
        try:
            # First try to list a few changes with the current page token to see if it works
            if current_page_token:
                try:
                    print(f"Testing current page token: {current_page_token}")
                    service.changes().list(
                        pageToken=current_page_token,
                        pageSize=1,
                        fields="changes(fileId)",
                    ).execute()
                    # If we reach here, the token is valid
                    fresh_token = current_page_token
                    print("Current page token is valid")
                except Exception as e:
                    print(f"Current page token is invalid or expired: {e}")
                    # We'll get a new token below

            if not fresh_token:
                # Get the latest token if the current one is invalid
                response = service.changes().getStartPageToken().execute()
                fresh_token = response.get("startPageToken")
                current_page_token = fresh_token
                print(f"Using fresh start token: {fresh_token}")
        except Exception as e:
            print(f"Error getting page token: {e}")
            # Continue with the rest of the function anyway

        # List files in the watched folder directly
        # This is the most reliable way to find recent files
        print(f"Listing files directly in the watched folder...")
        folder_files = []
        try:
            results = (
                service.files()
                .list(
                    q=f"'{WATCHED_FOLDER_ID}' in parents and trashed=false",
                    fields="files(id, name, createdTime, modifiedTime)",
                    orderBy="modifiedTime desc",
                    pageSize=20,
                )
                .execute()
            )

            folder_files = results.get("files", [])
            print(f"Found {len(folder_files)} files in the watched folder")

            # Process the most recently modified files
            for file in folder_files[:10]:  # Process up to 10 most recent files
                file_id = file.get("id")
                file_name = file.get("name")
                modified_time = file.get("modifiedTime")

                print(f"File: {file_name} (ID: {file_id}, Modified: {modified_time}")

                # Check if we've recently processed this file ID
                current_time = time.time()
                if file_id in processed_file_ids:
                    last_processed_time = processed_file_ids[file_id]
                    elapsed_seconds = current_time - last_processed_time

                    if elapsed_seconds < DUPLICATE_PREVENTION_TIMEOUT:
                        print(
                            f"DUPLICATE PREVENTION: Skipping file {file_name} (ID: {file_id})"
                        )
                        print(f"It was processed {elapsed_seconds:.1f} seconds ago")
                        continue
                    else:
                        print(
                            f"File was processed before, but {elapsed_seconds:.1f} seconds have passed. Processing again."
                        )

                # Process based on filename - only if file exists (not deleted)
                if file_name == CAMPAIGN_CONTENT_FILENAME:
                    print(f"Found target file: {file_name}")
                    # Verify file still exists and isn't in trash
                    try:
                        file_check = (
                            service.files()
                            .get(fileId=file_id, fields="trashed")
                            .execute()
                        )

                        if file_check.get("trashed", False):
                            print(f"  Skipping: File {file_name} is in trash")
                            continue

                        # Mark this file ID as processed with current timestamp
                        processed_file_ids[file_id] = current_time
                        print(
                            f"Marked file ID {file_id} as processed at {time.ctime(current_time)}"
                        )

                        await download_file(file_id, file_name)
                        print(f"Downloaded {file_name}")
                        # Start processing in the background
                        background_tasks.add_task(process_campaign_data)

                        # Clean up older entries to prevent memory growth
                        clean_old_processed_ids()

                        return {
                            "status": "processing",
                            "message": f"Found and processing {file_name}",
                            "files": [file_name],
                        }
                    except Exception as e:
                        print(f"  Error checking file {file_id}: {e}")
                        continue
        except Exception as e:
            print(f"Error listing files directly: {e}")
            # Continue with the changes API approach as fallback

        # Fallback to the changes API
        if not folder_files:
            print("No files found directly, trying changes API...")
            # Get the latest change token
            response = service.changes().getStartPageToken().execute()
            page_token = response.get("startPageToken")

            # List all changes to find the affected files
            changes = []

            # We'll limit to the last 10 changes to avoid fetching too many
            page_count = 0
            while page_token and page_count < 2:
                response = (
                    service.changes()
                    .list(
                        pageToken=page_token,
                        spaces="drive",
                        fields="nextPageToken, changes(fileId, file(name, parents))",
                        pageSize=5,  # Limit to 5 changes per page
                    )
                    .execute()
                )

                current_changes = response.get("changes", [])
                changes.extend(current_changes)
                page_token = response.get("nextPageToken")
                page_count += 1

                print(f"Fetched {len(current_changes)} changes")

                if not page_token:
                    break

            if not changes:
                return {"status": "no_changes", "message": "No recent changes found"}

            # Process each changed file
            processed_files = []
            for change in changes:
                file_id = change.get("fileId")
                file_data = change.get("file", {})
                file_name = file_data.get("name", "")
                parents = file_data.get("parents", [])

                if not file_id or not file_name:
                    continue

                # Check if the file is in our watched folder
                if WATCHED_FOLDER_ID not in parents:
                    continue

                print(
                    f"Found change for file: {file_name} (ID: {file_id}) in watched folder"
                )
                processed_files.append(file_name)

                # Download relevant files
                if file_name == CAMPAIGN_CONTENT_FILENAME:
                    await download_file(file_id, CAMPAIGN_CONTENT_FILENAME)
                    print(f"Downloaded {file_name}")
                elif file_name == INFLUENCER_PROFILES_FILENAME:
                    await download_file(file_id, INFLUENCER_PROFILES_FILENAME)
                    print(
                        f"Downloaded {file_name} (though not strictly required anymore)"
                    )
                elif file_name.endswith(".pptx") and "template" in file_name.lower():
                    template_dir = os.path.dirname(TEMPLATE_PPTX_PATH)
                    os.makedirs(template_dir, exist_ok=True)
                    await download_file(file_id, os.path.basename(TEMPLATE_PPTX_PATH))
                    print(
                        f"Downloaded template file as {os.path.basename(TEMPLATE_PPTX_PATH)}"
                    )

            # Check if we have the required campaign file
            campaign_file_path = os.path.join(DOWNLOAD_PATH, CAMPAIGN_CONTENT_FILENAME)
            # influencer_file_path = os.path.join(DOWNLOAD_PATH, INFLUENCER_PROFILES_FILENAME)

            if os.path.exists(campaign_file_path):  # Only check for campaign file
                print("Required campaign file found, starting data processing")
                background_tasks.add_task(process_campaign_data)
                return {
                    "status": "processing",
                    "message": "Found and processed files in watched folder",
                    "files": processed_files,
                    "data_processing": "started",
                }
            else:
                missing = []
                if not os.path.exists(campaign_file_path):
                    missing.append(CAMPAIGN_CONTENT_FILENAME)
                # if not os.path.exists(influencer_file_path):
                #     missing.append(INFLUENCER_PROFILES_FILENAME)

                return {
                    "status": "waiting",
                    "message": "Found files but missing some required files",
                    "files": processed_files,
                    "missing": missing,
                }

        # If we reach here, it means we found files in the folder but none matched
        # our specific requirements
        if folder_files:
            return {
                "status": "found_files",
                "message": "Found files in the watched folder, but none match required criteria",
                "file_count": len(folder_files),
            }
        else:
            return {
                "status": "no_files",
                "message": "No files found in the watched folder",
            }

    except Exception as e:
        print(f"Error in test endpoint: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Error testing Drive changes: {str(e)}"
        )


# Add a function to clean up old processed IDs
def clean_old_processed_ids():
    """Clean up old entries from processed_file_ids."""
    current_time = time.time()
    # Keep a list of IDs to remove to avoid modifying the dictionary during iteration
    ids_to_remove = []

    for file_id, timestamp in processed_file_ids.items():
        # Remove entries older than 1 hour
        if current_time - timestamp > 3600:  # 1 hour in seconds
            ids_to_remove.append(file_id)

    # Remove the old entries
    for file_id in ids_to_remove:
        del processed_file_ids[file_id]

    if ids_to_remove:
        print(f"Cleaned up {len(ids_to_remove)} old processed file entries")


if __name__ == "__main__":
    # Make sure the data and reports directories exist
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    os.makedirs(os.path.dirname(TEMPLATE_PPTX_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(OUTPUT_PPTX_PATH), exist_ok=True)

    # Try to register the webhook on startup
    if os.getenv("WEBHOOK_PUBLIC_URL"):
        print("Attempting to register webhook on startup...")
        try:
            success = register_webhook()
            if success:
                print("Webhook registered successfully!")

                # Auto-renew the webhook before it expires (webhooks expire after 24 hours)
                # This runs in the background and will re-register the webhook every 23 hours
                def auto_renew_webhook():
                    while True:
                        # Sleep for 23 hours
                        print("Webhook renewal task is active. Will renew in 23 hours.")
                        time.sleep(23 * 60 * 60)
                        print("Automatically renewing webhook registration...")
                        register_webhook()

                # Start the renewal in a background thread
                import threading

                renewal_thread = threading.Thread(
                    target=auto_renew_webhook, daemon=True
                )
                renewal_thread.start()
            else:
                print(
                    "Failed to register webhook on startup. Server will start anyway."
                )
                print(
                    "You can manually register the webhook using the /register-webhook endpoint."
                )
        except Exception as e:
            print(f"Error during webhook registration: {e}")
            print("Server will start without an active webhook registration.")
            print(
                "You can manually register the webhook using the /register-webhook endpoint."
            )
    else:
        print("WEBHOOK_PUBLIC_URL not set. Webhook registration skipped.")
        print(
            "To register the webhook, set WEBHOOK_PUBLIC_URL in .env and use the /register-webhook endpoint."
        )

    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000)
