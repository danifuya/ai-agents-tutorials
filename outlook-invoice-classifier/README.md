# AI Invoice Classifier for Outlook

An AI-powered application that automatically classifies invoices in Outlook emails using Microsoft Graph API and OpenAI.

## Setup Instructions

### 1. Azure App Registration

First, you need to register an application in Azure with the following permissions:

**Application Permissions:**

- `Contacts.Read` - Read contacts in all mailboxes
- `Mail.ReadWrite` - Read and write mail in all mailboxes
- `MailboxSettings.ReadWrite` - Read and write all user mailbox settings

**Delegated Permissions:**

- `User.Read` - Sign in and read user profile

Make sure to grant admin consent for all application permissions.

### 2. Start ngrok with domain

Start ngrok to create a public URL for webhook notifications:

```bash
ngrok http --domain=your-ngrok-domain 8000
```

### 2. Set up environment variables

Create a `.env` file in the project root with the following variables:

```env
# Microsoft Graph Configuration
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
TENANT_ID=your_tenant_id
USER_ID=your_user_id

# Webhook Configuration
WEBHOOK_URL=https://mustang-delicate-redbird.ngrok-free.app/webhook/outlook

# Email Processing Configuration
CATEGORY_NAME=Factura Guardada

# AI Configuration
OPENAI_API_KEY=your_openai_api_key

# Server Configuration (optional)
HOST=0.0.0.0
PORT=8000
RELOAD=true
```

### 3. Install dependencies

```bash
uv sync
```

### 4. Run the application

```bash
uv run main.py
```

The application will start on `http://localhost:8000`

### 5. Create subscription

Create a Microsoft Graph subscription to receive webhook notifications:

```bash
curl -X POST http://localhost:8000/create-subscription
```

## API Endpoints

- `GET /` - Health check
- `POST /webhook/outlook` - Outlook webhook endpoint
- `POST /create-subscription` - Create Microsoft Graph subscription
- `GET /subscriptions` - List active subscriptions
- `DELETE /subscription/{subscription_id}` - Delete a subscription
- `PUT /subscription/{subscription_id}/renew` - Renew a subscription
- `GET /health` - Health check endpoint

## Requirements

- Python >=3.13
- Microsoft Graph API access
- OpenAI API key
- ngrok for webhook tunneling
