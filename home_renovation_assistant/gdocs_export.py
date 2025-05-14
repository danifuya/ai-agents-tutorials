"""
This module contains functionality to export renovation data to Google Docs and other formats.
This is a backend component that automatically handles data storage for the company's internal use.
NOTE: This is a placeholder implementation that would need to be connected to Google API.
In a real implementation, you would use the Google Docs API to create and share documents.
"""

import pandas as pd
from typing import List, Tuple, Optional, Dict
import json
import os
from pathlib import Path
import datetime
import mimetypes

# Google API Imports
from google.oauth2 import service_account
import google.auth
import google.auth.exceptions
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth import default
from googleapiclient.http import MediaFileUpload

# Define scopes required for Docs and Drive
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


def get_google_services():
    """Authenticate using Application Default Credentials (ADC) and return Google Docs and Drive service objects."""
    creds = None
    try:
        # Automatically finds credentials from the environment (gcloud, WIF, etc.)
        creds, project = default(scopes=SCOPES)
        print(f"Successfully obtained ADC credentials for project: {project}")
    except google.auth.exceptions.DefaultCredentialsError as e:
        print("Error: Could not automatically find Google Cloud credentials.")
        print(
            "Please run 'gcloud auth application-default login' for local development,"
        )
        print(
            "or ensure the environment is configured for ADC (e.g., Workload Identity Federation)."
        )
        print(f"Details: {e}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred during authentication: {e}")
        return None, None

    try:
        docs_service = build("docs", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)
        return docs_service, drive_service
    except HttpError as error:
        print(f"An error occurred building Google services: {error}")
        return None, None


def get_or_create_folder(
    drive_service, folder_name: str, parent_folder_id: str
) -> Optional[str]:
    """
    Check if a folder exists within a parent folder, create it if not.
    Returns the folder ID or None if an error occurs.
    """
    try:
        # Escape single quotes in folder_name for the query
        escaped_folder_name = folder_name.replace("'", "\\'")
        query = f"name='{escaped_folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_folder_id}' in parents and trashed=false"
        response = (
            drive_service.files()
            .list(q=query, fields="files(id, name)", spaces="drive")
            .execute()
        )
        folders = response.get("files", [])

        if folders:
            print(
                f"Folder '{folder_name}' already exists with ID: {folders[0].get('id')}"
            )
            return folders[0].get("id")
        else:
            print(f"Creating folder '{folder_name}' in parent {parent_folder_id}...")
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_folder_id],
            }
            folder = (
                drive_service.files().create(body=file_metadata, fields="id").execute()
            )
            folder_id = folder.get("id")
            print(f"Folder '{folder_name}' created with ID: {folder_id}")
            return folder_id
    except HttpError as error:
        print(
            f"An API error occurred while getting/creating folder '{folder_name}': {error}"
        )
        return None
    except Exception as e:
        print(
            f"An unexpected error occurred while getting/creating folder '{folder_name}': {e}"
        )
        return None


def format_data_for_gdocs(data: List[Tuple[str, str, Optional[str]]]) -> Dict:
    """
    Format the collected renovation data for Google Docs.

    Args:
        data: List of tuples containing (question, answer, image_path)

    Returns:
        Dict containing formatted data for Google Docs
    """
    # Get timestamp for the document title and content
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

    doc_data = {
        "title": f"{date_str} Chat Assessment",
        "timestamp": timestamp_str,
        "items": [],
    }

    for question, answer, img_path in data:
        item = {
            "question": question,
            "answer": answer,
            "has_image": img_path is not None,
            "image_path": img_path,
        }
        doc_data["items"].append(item)

    return doc_data


def export_to_gdocs(data: List[Tuple[str, str, Optional[str]]]) -> Optional[str]:
    """
    Export the collected renovation data to Google Docs in a specific Drive folder.
    Also uploads images to a structured subfolder system in Drive.
    """
    target_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not target_folder_id or target_folder_id == "YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE":
        print(
            "Error: GOOGLE_DRIVE_FOLDER_ID environment variable not set or is placeholder."
        )
        return None

    docs_service, drive_service = get_google_services()
    if not docs_service or not drive_service:
        return None

    # --- Determine image upload destination folder ---
    images_base_folder_name = "Images"
    images_base_folder_id = get_or_create_folder(
        drive_service, images_base_folder_name, target_folder_id
    )

    # Determine chat-specific folder name based on the eventual doc title
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    prospective_doc_title = f"{date_str} Chat Assessment"
    chat_specific_images_folder_name = prospective_doc_title

    image_upload_destination_folder_id = (
        target_folder_id  # Default to main target folder
    )

    if images_base_folder_id:
        chat_specific_folder_id = get_or_create_folder(
            drive_service, chat_specific_images_folder_name, images_base_folder_id
        )
        if chat_specific_folder_id:
            image_upload_destination_folder_id = chat_specific_folder_id
            print(
                f"Images will be uploaded to: {images_base_folder_name}/{chat_specific_images_folder_name} (ID: {image_upload_destination_folder_id})"
            )
        else:
            image_upload_destination_folder_id = (
                images_base_folder_id  # Fallback to "Session Images"
            )
            print(
                f"Warning: Could not get/create chat-specific images folder '{chat_specific_images_folder_name}'. Uploading images to '{images_base_folder_name}' (ID: {image_upload_destination_folder_id})."
            )
    else:
        print(
            f"Warning: Could not get/create base images folder '{images_base_folder_name}'. Uploading images to target folder '{target_folder_id}'."
        )
    # --- End image upload destination logic ---

    formatted_data = format_data_for_gdocs(data)
    doc_title = formatted_data["title"]

    # Get timestamp string for the header (used for title in format_data_for_gdocs already)
    # We can reuse the timestamp from formatted_data or recalculate if needed
    # Let's use the one from formatted_data for consistency
    submission_timestamp_str = formatted_data[
        "timestamp"
    ]  # Assumes format YYYY-MM-DD HH:MM:SS
    # Reformat to exclude seconds for the header
    try:
        dt_obj = datetime.datetime.strptime(
            submission_timestamp_str, "%Y-%m-%d %H:%M:%S"
        )
        header_time_str = dt_obj.strftime("%Y-%m-%d %H:%M")
    except ValueError:  # Fallback if parsing fails
        header_time_str = submission_timestamp_str  # Use original if parsing error

    blue_color = {"color": {"rgbColor": {"red": 0.0, "green": 0.0, "blue": 1.0}}}
    image_width = 300

    # --- Build requests for batchUpdate ---
    # Prepare the header text
    header_text = f"Submitted: {header_time_str}\n\n"  # Updated header text
    header_len = len(header_text)

    requests = [
        {"insertText": {"location": {"index": 1}, "text": header_text}},
        # Format the header (Bold, Size 14pt)
        {
            "updateTextStyle": {
                "range": {"startIndex": 1, "endIndex": header_len},
                "textStyle": {
                    "bold": True,
                    "fontSize": {"magnitude": 14, "unit": "PT"},
                },
                "fields": "bold,fontSize",  # Specify both fields
            }
        },
    ]
    # Adjust starting index for subsequent content
    current_index = header_len + 1  # Start after the header text

    for item in formatted_data["items"]:
        q_text = f"Q: {item['question']}\n"
        a_text = f"A: {item['answer']}\n"
        img_text = (
            f"(Image Provided: Yes - Path: {item['image_path']})\n"
            if item["has_image"]
            else "(Image Provided: No)\n"
        )
        separator = "\n"

        # Insert Question Text
        requests.append(
            {"insertText": {"location": {"index": current_index}, "text": q_text}}
        )
        requests.append(
            {
                "updateTextStyle": {
                    "range": {
                        "startIndex": current_index,
                        "endIndex": current_index + len(q_text),
                    },
                    "textStyle": {"bold": True},
                    "fields": "bold",
                }
            }
        )
        current_index += len(q_text)

        # Insert Answer Text
        requests.append(
            {"insertText": {"location": {"index": current_index}, "text": a_text}}
        )
        requests.append(
            {
                "updateTextStyle": {
                    "range": {
                        "startIndex": current_index,
                        "endIndex": current_index + len(a_text),
                    },
                    "textStyle": {"foregroundColor": blue_color},
                    "fields": "foregroundColor",
                }
            }
        )
        current_index += len(a_text)

        # Insert Image (if applicable)
        if item["has_image"] and item["image_path"]:
            image_path = item["image_path"]
            if os.path.exists(image_path):
                try:
                    print(
                        f"Attempting to upload image: {image_path} to folder ID: {image_upload_destination_folder_id}"
                    )
                    mime_type, _ = mimetypes.guess_type(image_path)
                    if not mime_type:
                        mime_type = "application/octet-stream"
                    image_filename = Path(image_path).name
                    file_metadata = {
                        "name": image_filename,
                        "parents": [
                            image_upload_destination_folder_id
                        ],  # Use determined parent ID
                    }
                    media = MediaFileUpload(image_path, mimetype=mime_type)
                    drive_file = (
                        drive_service.files()
                        .create(body=file_metadata, media_body=media, fields="id")
                        .execute()
                    )
                    file_id = drive_file.get("id")
                    print(f"Image uploaded to Drive with ID: {file_id}")

                    print(f"Making Drive file {file_id} publicly readable...")
                    permission_body = {"type": "anyone", "role": "reader"}
                    drive_service.permissions().create(
                        fileId=file_id, body=permission_body, fields="id"
                    ).execute()
                    print(f"Permissions updated for file {file_id}.")

                    image_uri = f"https://drive.google.com/uc?id={file_id}"
                    requests.append(
                        {
                            "insertInlineImage": {
                                "location": {"index": current_index},
                                "uri": image_uri,
                                "objectSize": {
                                    "width": {"magnitude": image_width, "unit": "PT"}
                                },
                            }
                        }
                    )
                    current_index += 1
                    requests.append(
                        {
                            "insertText": {
                                "location": {"index": current_index},
                                "text": "\n",
                            }
                        }
                    )
                    current_index += 1
                except HttpError as drive_error:
                    print(
                        f"\nERROR uploading/inserting image {image_path}: {drive_error}"
                    )
                    fail_note = f"[Error processing image: {image_filename}]\n"
                    requests.append(
                        {
                            "insertText": {
                                "location": {"index": current_index},
                                "text": fail_note,
                            }
                        }
                    )
                    current_index += len(fail_note)
                except FileNotFoundError:
                    print(f"\nERROR: Image file not found at path: {image_path}")
                    fail_note = f"[Image file not found: {Path(image_path).name}]\n"
                    requests.append(
                        {
                            "insertText": {
                                "location": {"index": current_index},
                                "text": fail_note,
                            }
                        }
                    )
                    current_index += len(fail_note)
                except Exception as e:
                    print(
                        f"\nAn unexpected error occurred processing image {image_path}: {e}"
                    )
                    fail_note = f"[Unexpected error processing image: {Path(image_path).name}]\n"
                    requests.append(
                        {
                            "insertText": {
                                "location": {"index": current_index},
                                "text": fail_note,
                            }
                        }
                    )
                    current_index += len(fail_note)
            else:
                print(f"\nWarning: Image file path listed but not found: {image_path}")
                missing_note = (
                    f"[Listed image file not found: {Path(image_path).name}]\n"
                )
                requests.append(
                    {
                        "insertText": {
                            "location": {"index": current_index},
                            "text": missing_note,
                        }
                    }
                )
                current_index += len(missing_note)

        requests.append(
            {"insertText": {"location": {"index": current_index}, "text": separator}}
        )
        current_index += len(separator)

    body = {
        "title": doc_title,
    }
    try:
        print(f"Creating Google Doc: {doc_title}")
        document = docs_service.documents().create(body=body).execute()
        doc_id = document.get("documentId")
        print(f"Document created with ID: {doc_id}")

        print("Adding content to document...")
        if requests:  # Only run batchUpdate if there are requests
            docs_service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()
            print("Content added.")
        else:
            print("No content requests to add.")

        print(f"Moving document {doc_id} to folder {target_folder_id}...")
        file = drive_service.files().get(fileId=doc_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents"))
        drive_service.files().update(
            fileId=doc_id,
            addParents=target_folder_id,
            removeParents=previous_parents,
            fields="id, parents",
        ).execute()
        print(f"Document moved successfully to folder {target_folder_id}.")

        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        print(f"Export to Google Docs successful: {doc_url}")
        return doc_url
    except HttpError as error:
        print(f"An API error occurred: {error}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def export_to_json(
    data: List[Tuple[str, str, Optional[str]]], filename: str = None
) -> str:
    """
    Export the collected renovation data to JSON file.

    Args:
        data: List of tuples containing (question, answer, image_path)
        filename: Name of the JSON file to create

    Returns:
        Path to the created JSON file
    """
    # Create directory if it doesn't exist
    Path("data").mkdir(exist_ok=True)

    # Generate filename if not provided
    if filename is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/renovation_assistant_{timestamp}.json"

    # Format the data
    doc_data = format_data_for_gdocs(data)

    # Write to file
    with open(filename, "w") as f:
        json.dump(doc_data, f, indent=2)

    print(f"Data exported to JSON: {filename}")
    return filename
