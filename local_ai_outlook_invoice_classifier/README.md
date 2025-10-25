# AI Invoice Classifier for Outlook

An AI-powered application that automatically classifies invoices in Outlook emails using Microsoft Graph API and local AI models.

[Video Tutorial](https://youtu.be/zwGzqiA0BWI)

## Requirements

- **Docker Desktop** with AI capabilities (Docker Model Runner)
- **Python >=3.13**
- **UV** package manager (recommended) or pip
- **Microsoft Graph API access**
- **ngrok** for webhook tunneling

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
brew install ngrok
ngrok config add-authtoken XXXX
ngrok http --domain=mustang-delicate-redbird.ngrok-free.app 8000
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
CATEGORY_NAME=Invoice Saved

# AI Configuration (for local Docker Model Runner)
OPENAI_API_KEY=dummy
LOCAL_API_URL=http://localhost:12434/engines/v1

# Server Configuration (optional)
HOST=0.0.0.0
PORT=8000
RELOAD=true
```

### 3. Setup Docker Model Runner

Enable Docker Model Runner in Docker Desktop:

1. Open Docker Desktop
2. Go to **Settings → AI tab**
3. Enable **"Docker Model Runner"**
4. Enable **"Enable host-side TCP support"**
5. Set port to **12434**
6. Apply & Restart Docker Desktop

Then pull and run the AI model:

```bash
docker model pull ai/mistral:7B-Q4_K_M
```

### 4. Install dependencies

Install with UV (recommended):

```bash
uv sync
```

Or with pip:

```bash
pip install -e .
```

### 5. Run the application

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

- `POST /webhook/outlook` - Outlook webhook endpoint
- `POST /create-subscription` - Create Microsoft Graph subscription
- `GET /subscriptions` - List active subscriptions
- `DELETE /subscription/{subscription_id}` - Delete a subscription
- `PUT /subscription/{subscription_id}/renew` - Renew a subscription
- `GET /health` - Health check endpoint
