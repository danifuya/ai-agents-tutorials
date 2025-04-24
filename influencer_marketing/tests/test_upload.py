"""
Test file upload to Google Drive folder to trigger webhook
"""

import os
from google.auth import default
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")


def create_test_file():
    """Create a test CSV file"""
    with open("test_file.csv", "w") as f:
        f.write("column1,column2\nvalue1,value2\n")
    return "test_file.csv"


def create_test_campaign_content():
    """Create a test campaign content CSV file"""
    with open("campaign_content_test.csv", "w") as f:
        f.write("""campaign_id,influencer_handle,post_url,post_type,impressions,reach,likes,comments,saves
campaign1,@influencer1,http://example.com/post1,image,10000,5000,500,50,20
campaign1,@influencer1,http://example.com/post2,video,20000,8000,700,80,40
campaign1,@influencer2,http://example.com/post3,image,15000,6000,600,60,30
campaign2,@influencer2,http://example.com/post4,video,25000,10000,800,100,50
""")
    return "campaign_content_test.csv"


def upload_file(file_path, file_name=None):
    """Upload a file to Google Drive in the watched folder"""
    if file_name is None:
        file_name = os.path.basename(file_path)

    # Use Application Default Credentials
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/drive"])

    # Refresh token if needed
    if hasattr(credentials, "refresh"):
        credentials.refresh(Request())

    drive_service = build("drive", "v3", credentials=credentials)

    # First check if file already exists to avoid duplicates
    query = f"name='{file_name}' and '{FOLDER_ID}' in parents and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()

    # If file exists, delete it first
    for item in results.get("files", []):
        print(f"Deleting existing file: {item['name']} (ID: {item['id']})")
        drive_service.files().delete(fileId=item["id"]).execute()

    # Upload the new file
    file_metadata = {"name": file_name, "parents": [FOLDER_ID]}

    media = MediaFileUpload(file_path, resumable=True)

    file = (
        drive_service.files()
        .create(body=file_metadata, media_body=media, fields="id")
        .execute()
    )

    print(f"File uploaded: {file_name} (ID: {file.get('id')})")
    return file.get("id")


if __name__ == "__main__":
    # Create and upload a test file first
    test_file = create_test_file()
    test_file_id = upload_file(test_file, "test_webhook_trigger.csv")

    # Create and upload only the campaign content file
    campaign_file = create_test_campaign_content()
    upload_file(campaign_file, "campaign.csv")

    print("Files uploaded. Check webhook server logs for notifications.")
