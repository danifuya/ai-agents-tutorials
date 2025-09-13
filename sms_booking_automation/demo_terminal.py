#!/usr/bin/env python3
"""
Interactive Terminal Demo for SMS Booking Automation

This script provides a terminal-based demo where you can chat with the
SMS booking automation system and see the responses in real-time.

Usage: python demo_terminal.py
"""

import asyncio
import logging
import sys
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import os

# Add the app directory to the Python path
sys.path.append("app")
load_dotenv()

# Override database host for local demo
os.environ["POSTGRES_HOST"] = "localhost"

from services.database_service import DatabaseService
from workflows.sms_workflow import process_incoming_sms
from utils.utils import normalize_phone_number

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise
logger = logging.getLogger(__name__)


class MockJustCallService:
    """Mock JustCall service for demo purposes"""

    def __init__(self):
        self.conversation_history = {}
        self.escalation_tag_id = None

    def send_sms(self, to: str, body: str) -> str:
        """Print the automation's reply to terminal"""
        normalized_to = normalize_phone_number(to)

        print(f"\n🤖 Bot: {body}")

        # Store in conversation history
        if normalized_to not in self.conversation_history:
            self.conversation_history[normalized_to] = []

        self.conversation_history[normalized_to].append(
            {"role": "assistant", "content": body}
        )

        return "demo_msg_id"

    def get_conversation_history(
        self, participant_number: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        normalized_number = normalize_phone_number(participant_number)
        history = self.conversation_history.get(normalized_number, [])
        # Return history WITHOUT the current message (workflow will add it)
        return history[-limit:]

    def get_conversation_thread_tags(self, participant_number: str) -> List[str]:
        return []


class MockTelegramService:
    """Mock Telegram service - silent for cleaner demo"""

    async def send_notification(self, message: str) -> bool:
        return True


class TerminalDemo:
    """Main demo class"""

    def __init__(self):
        self.db_service = DatabaseService()
        self.justcall_service = MockJustCallService()
        self.telegram_service = MockTelegramService()
        self.demo_phone = "+1234567890"  # Fixed demo phone number

    async def initialize(self):
        """Initialize database connection"""
        await self.db_service.initialize()

    async def cleanup(self):
        """Cleanup resources"""
        await self.db_service.close()

    async def process_message(self, message: str):
        """Process a message through the SMS workflow"""
        # Initialize conversation history if needed
        normalized_phone = normalize_phone_number(self.demo_phone)
        if normalized_phone not in self.justcall_service.conversation_history:
            self.justcall_service.conversation_history[normalized_phone] = []

        # Add the current user message to history BEFORE processing
        # This ensures it's available for the next conversation
        self.justcall_service.conversation_history[normalized_phone].append({
            "role": "user",
            "content": message
        })

        # Process through the original workflow 
        # (it will get history, add current message temporarily, then process)
        async with self.db_service.get_connection() as conn:
            await process_incoming_sms(
                conn=conn,
                justcall_service=self.justcall_service,
                telegram_service=self.telegram_service,
                from_number=self.demo_phone,
                message_body=message,
            )
        
        # The assistant's reply gets saved automatically in MockJustCallService.send_sms()

    async def run(self):
        """Run the interactive demo"""
        await self.initialize()

        print("=" * 60)
        print("SMS BOOKING AUTOMATION - INTERACTIVE DEMO")
        print("=" * 60)
        print("Type your messages as a customer would send via SMS.")
        print("The automation will respond just like in the real system.")
        print("Type 'quit' to exit.\n")

        try:
            while True:
                try:
                    # Get user input
                    user_message = input("👤 You: ").strip()

                    if user_message.lower() == "quit":
                        break

                    if not user_message:
                        continue

                    # Process the message through the automation
                    await self.process_message(user_message)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")

        finally:
            await self.cleanup()
            print("\n👋 Demo ended!")


if __name__ == "__main__":
    demo = TerminalDemo()
    asyncio.run(demo.run())
