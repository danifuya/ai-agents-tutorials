# SMS Booking Automation System

This system provides automated SMS booking capabilities using AI agents, integrating with Just Call for SMS handling and Telegram for notifications.

[Video tutorial](https://youtu.be/nlny25W3Oek)

## Prerequisites

- Docker and Docker Compose
- ngrok account with custom domain
- Just Call account
- Telegram account
- Python 3.8+

## Setup Instructions

### 1. Just Call Configuration

#### Create Tag and Phone Number

1. Login to your Just Call dashboard
2. Navigate to **Settings** > **Tags**
3. Create a new tag for SMS booking automation
4. Go to **Phone Numbers** section
5. Purchase or configure a phone number for SMS reception
6. Assign the created tag to the phone number

### 2. Telegram Bot Setup

1. Open Telegram and search for `@BotFather`
2. Start a chat and send `/newbot`
3. Follow the prompts to create your bot:
   - Choose a name for your bot
   - Choose a username (must end with 'bot')
4. Save the bot token provided by BotFather
5. Get your chat ID:
   - Send a message to your bot
   - Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat ID in the response

### 3. Environment Configuration

Create a copy of `.env.example` and name it `.env`. Fill all the variables.

### 4. ngrok Setup

1. Install ngrok from [https://ngrok.com/](https://ngrok.com/)
2. Sign up for an account and get your authtoken
3. Configure ngrok with your domain:

```bash
ngrok config add-authtoken your_authtoken
```

4. Expose your application:

```bash
ngrok http --domain=your_domain_app.app 8080
```

Replace `your_domain_app.app` with your actual ngrok domain.

### 5. Just Call Webhook Configuration

1. In your Just Call dashboard, go to **APIs & Webhooks**
2. Create a new webhook for incoming SMS
3. Set the webhook URL to: `https://your_domain_app.app/webhook/sms`
4. Select the events you want to receive (incoming SMS)
5. Add your webhook secret for security

### 6. Running the Application

#### Using Docker Compose

1. Make sure your `.env` file is configured
2. Start the application:

```bash
docker-compose up -d
```

3. Check the logs to ensure everything is running:

```bash
docker-compose logs -f
```

#### Manual Setup (Development)

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the application:

```bash
python -m app.main
```

## Usage

1. Once the system is running, customers can send SMS messages to your Just Call number
2. The AI agent will process the booking requests automatically
3. Booking confirmations and updates will be sent via SMS
4. Notifications will also be sent to your configured Telegram chat

### Interactive Terminal Demo

For testing and demonstration purposes, you can run an interactive terminal demo that simulates the SMS workflow without requiring JustCall integration:

```bash
python demo_terminal.py
```

This demo allows you to:

- Simulate incoming SMS messages from clients
- See how the AI agents process booking requests
- Test the complete booking workflow locally
- View agent responses and conversation flow
- **Receive real Telegram notifications** (if configured)

**Note:** The demo uses a mock JustCall service for SMS but uses the **real Telegram service**. If you have `TELEGRAM_BOT_TOKEN` and `TELEGRAM_TARGET_CHAT_IDS` configured in your `.env`, you'll receive actual Telegram notifications during the demo.

## API Endpoints

- `POST /webhook/sms` - Just Call SMS webhook endpoint
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint

## Troubleshooting

### Common Issues

1. **Webhook not receiving messages**

   - Verify ngrok is running and accessible
   - Check Just Call webhook configuration
   - Ensure webhook URL is correct

2. **Telegram notifications not working**

   - Verify bot token is correct
   - Check chat ID configuration
   - Ensure bot has been started in Telegram

3. **Database errors**
   - Check database connection string
   - Verify database permissions

### Logs

View application logs:

```bash
docker-compose logs -f app
```
