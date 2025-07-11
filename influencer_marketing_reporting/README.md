# Google Drive Webhook for Data Analysis & Reporting

This webhook server automatically processes campaign data files uploaded to a specified Google Drive folder, analyzes the data, and generates PowerPoint reports.

[Link to YouTube Tutorial](https://www.youtube.com/watch?v=YgsVL-POOzM&t=1s)

## System Overview

When a file named `campaign.csv` is uploaded to your configured Google Drive folder, the webhook server:

1. Receives a notification from Google Drive
2. Downloads the campaign file
3. Processes the data using the analysis logic
4. Generates a summary CSV file
5. Creates a PowerPoint presentation based on a template
6. Uploads both results back to the same Google Drive folder

## Setup Instructions

### 1. Configure Google Cloud and Drive API

1. Create or select a Google Cloud project
2. Enable the Google Drive API
3. Install the [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install) if you haven't already
4. Set up Application Default Credentials (ADC):
   ```
   gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive
   ```
5. Create a folder in Google Drive and note its folder ID (the long string in the URL)

### 2. Environment Configuration

Create a `.env` file with these required variables:

```
GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id
WEBHOOK_SECRET=your_secret_token_for_webhook_security
WEBHOOK_PUBLIC_URL=your_public_facing_url
```

### 3. For Local Development: Set up ngrok

Google Drive webhooks require a public HTTPS URL. For local development:

1. Install [ngrok](https://ngrok.com/)
2. Run: `ngrok http 8000`
3. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)
4. Update `WEBHOOK_PUBLIC_URL` in your `.env` file

### 4. Install Dependencies

```
pip install -r requirements.txt
```

### 5. Run the Webhook Server

```
python webhook_server.py
```

The server will:

- Start on port 8000
- Automatically register the webhook if `WEBHOOK_PUBLIC_URL` is set
- Begin listening for notifications from Google Drive

## Server API Endpoints

- `/register-webhook` - Manually register a new webhook
- `/health` - Check server status
- `/webhook/google-drive` - The actual webhook endpoint (not called directly)

## File Requirements

Upload the following file to your Google Drive folder:

- `campaign.csv` - Campaign data file with required format

Optional:

- Any file with "template" in the name and `.pptx` extension - Custom PowerPoint template

**IMPORTANT**: Do not modify the structure of the PowerPoint template file. The report generation relies on specific slide layouts and placeholder elements. Changing these elements will cause the report generation to fail.

## Output Files

The server generates:

1. `generated_campaign_summary.csv` - Analysis results saved in the `./reports/` directory and uploaded to Drive
2. `generated_report.pptx` - PowerPoint presentation saved in the `./reports/` directory and uploaded to Drive

## Important Notes

- Google Drive webhook registrations expire after 24 hours (the server auto-renews)
- ngrok URLs expire when restarted, requiring webhook re-registration
- For production use, deploy to a stable public URL

## Troubleshooting

- **Webhook not receiving notifications?** Check that `WEBHOOK_PUBLIC_URL` is public and has HTTPS
- **Files not processing?** Verify file name is exactly `campaign.csv`
- **Drive API errors?** Ensure proper ADC configuration and Drive folder permissions
- **Report generation fails?** Make sure the template PowerPoint file has not been modified
