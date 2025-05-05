"""
This module contains functionality to export renovation data to Google Docs and other formats.
This is a backend component that automatically handles data storage for the company's internal use.
NOTE: This is a placeholder implementation that would need to be connected to Google API.
In a real implementation, you would use the Google Docs API to create and share documents.
"""

import pandas as pd
from typing import List, Tuple, Optional
import json
import os
from pathlib import Path
import datetime


def format_data_for_gdocs(data: List[Tuple[str, str, Optional[str]]]) -> dict:
    """
    Format the collected renovation data for Google Docs.

    Args:
        data: List of tuples containing (question, answer, image_path)

    Returns:
        Dict containing formatted data for Google Docs
    """
    # Get timestamp for the document
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    doc_data = {
        "title": "Home Renovation Project Assessment",
        "timestamp": timestamp,
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


def export_to_gdocs(data: List[Tuple[str, str, Optional[str]]]) -> str:
    """
    Export the collected renovation data to Google Docs.

    Args:
        data: List of tuples containing (question, answer, image_path)

    Returns:
        URL of the created Google Doc (placeholder in this implementation)
    """
    # This would be implemented with Google Docs API
    # Format the data
    doc_data = format_data_for_gdocs(data)

    # In a real implementation, this would:
    # 1. Create a Google Doc
    # 2. Format the document with company branding
    # 3. Add the questions and answers
    # 4. Insert images at appropriate locations
    # 5. Save the document to a specific folder in Google Drive
    # 6. Set appropriate sharing permissions

    # Log that export was attempted
    print(f"Export to Google Docs requested at {doc_data['timestamp']}")

    # Return a placeholder URL that would be the actual document URL in a real implementation
    return "https://docs.google.com/document/d/example"


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


def export_to_csv(
    data: List[Tuple[str, str, Optional[str]]], filename: str = None
) -> str:
    """
    Export the collected renovation data to CSV file.

    Args:
        data: List of tuples containing (question, answer, image_path)
        filename: Name of the CSV file to create

    Returns:
        Path to the created CSV file
    """
    # Create directory if it doesn't exist
    Path("data").mkdir(exist_ok=True)

    # Generate filename if not provided
    if filename is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/renovation_assistant_{timestamp}.csv"

    # Create a dataframe
    rows = []
    for question, answer, img_path in data:
        rows.append(
            {
                "Question": question,
                "Answer": answer,
                "Has Image": "Yes" if img_path else "No",
                "Image Path": img_path if img_path else "",
            }
        )

    df = pd.DataFrame(rows)

    # Save to CSV
    df.to_csv(filename, index=False)

    print(f"Data exported to CSV: {filename}")
    return filename
