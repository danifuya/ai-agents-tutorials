# WhatsApp Customer Support Agent

This repository contains a WhatsApp customer support agent built with FastAPI.
[Link to YouTube Tutorial](https://www.youtube.com/watch?v=8h6oWnNgkGA&t=1836s)

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Install uv](#install-uv)
  - [Create Virtual Environment](#create-virtual-environment)
  - [Install Dependencies](#install-dependencies)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
  - [Start the FastAPI Server](#start-the-fastapi-server)
  - [Set Up Tunneling with Ngrok](#set-up-tunneling-with-ngrok)
- [Usage](#usage)

## Prerequisites

- Python 3.9+
- Ngrok account (for tunneling)

### Install Ngrok

#### macOS with Homebrew:

```bash
brew install ngrok
```

#### Manual Installation:

1. Download ngrok from [ngrok download page](https://ngrok.com/download)

#### Connect your account:

1. Sign up for an ngrok account if you haven't already
2. Copy your ngrok authtoken from your ngrok dashboard
3. Install the authtoken:

```bash
ngrok config add-authtoken <TOKEN>
```

## Installation

### Install uv

[uv](https://github.com/astral-sh/uv) is a faster alternative to pip for Python package management.

```bash
curl -sSf https://astral.sh/uv/install.sh | bash
```

### Create Virtual Environment

```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# OR
.venv\Scripts\activate     # On Windows
```

### Install Dependencies

```bash
uv pip install .
```

## Configuration

1. Create a `.env` file in the root directory using the example template:

```bash
cp .env.example .env
```

2. Open the `.env` file and fill in your credentials:

```
# WhatsApp API credentials
WHATSAPP_TOKEN=your_whatsapp_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
VERIFY_TOKEN=your_custom_verify_token

# OpenAI API credentials
OPENAI_API_KEY=your_openai_api_key

# Optional configurations
DEBUG=False
LOG_LEVEL=INFO
```

## Running the Application

### Start the FastAPI Server

```bash
uvicorn api.app:app --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000

### Set Up Tunneling with Ngrok

To expose your local server to the internet (required for WhatsApp webhooks):

```bash
ngrok http 8000
```

Take note of the HTTPS URL provided by ngrok (e.g., `https://your-unique-id.ngrok.io`). You'll need to configure this as your webhook URL in the WhatsApp Business API.

## Usage

1. Configure your WhatsApp webhook URL in the [Meta Developer Portal](https://developers.facebook.com/) using the ngrok URL.
2. Set up your verification token to match the one in your `.env` file.
