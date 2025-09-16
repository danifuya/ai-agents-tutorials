#!/usr/bin/env python3
"""
Test script to validate get_conversation_history time filtering functionality
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from services.justcall_service import JustCallService


async def test_time_filtering():
    """Test the time filtering functionality of get_conversation_history"""

    # Initialize JustCall service
    justcall = JustCallService()

    # You'll need to replace this with a real phone number that has recent messages
    test_phone_number = input(
        "Enter a phone number to test (with recent messages): "
    ).strip()

    if not test_phone_number:
        print("❌ No phone number provided. Exiting.")
        return

    print(f"🧪 Testing time filtering for {test_phone_number}")
    print("=" * 60)

    try:
        # Test 1: Get messages from last 30 minutes
        print("📅 Test 1: Fetching messages from last 30 minutes...")
        messages_30min = justcall.get_conversation_history(
            participant_number=test_phone_number,
            limit=50,  # Higher limit to catch more messages
            last_minutes=30,
        )
        print(f"✅ Found {len(messages_30min)} messages in last 30 minutes")

        # Test 2: Get messages from last 5 minutes
        print("\n📅 Test 2: Fetching messages from last 5 minutes...")
        messages_5min = justcall.get_conversation_history(
            participant_number=test_phone_number,
            limit=50,  # Higher limit to catch more messages
            last_minutes=5,
        )
        print(f"✅ Found {len(messages_5min)} messages in last 5 minutes")

        # Test 3: Get all recent messages (no time filter)
        print("\n📅 Test 3: Fetching recent messages (no time filter)...")
        messages_all = justcall.get_conversation_history(
            participant_number=test_phone_number, limit=50
        )
        print(f"✅ Found {len(messages_all)} recent messages (no filter)")

        # Analysis
        print("\n🔍 Analysis:")
        print(f"Messages in last 5 minutes: {len(messages_5min)}")
        print(f"Messages in last 30 minutes: {len(messages_30min)}")
        print(f"All recent messages: {len(messages_all)}")

        # Validation
        if len(messages_5min) <= len(messages_30min):
            print("✅ PASS: 5-minute filter returned <= 30-minute filter results")
        else:
            print(
                "❌ FAIL: 5-minute filter returned more messages than 30-minute filter"
            )

        if len(messages_30min) <= len(messages_all):
            print("✅ PASS: 30-minute filter returned <= all messages")
        else:
            print("❌ FAIL: 30-minute filter returned more messages than unfiltered")

        # Show sample messages if any found
        if messages_5min:
            print(f"\n📱 Sample from last 5 minutes:")
            for i, msg in enumerate(messages_5min[:3], 1):
                role = "🤖" if msg["role"] == "assistant" else "👤"
                content = (
                    msg["content"][:50] + "..."
                    if len(msg["content"]) > 50
                    else msg["content"]
                )
                print(f"  {i}. {role} {content}")

        if messages_30min:
            print(f"\n📱 Sample from last 30 minutes:")
            for i, msg in enumerate(messages_30min[:3], 1):
                role = "🤖" if msg["role"] == "assistant" else "👤"
                content = (
                    msg["content"][:50] + "..."
                    if len(msg["content"]) > 50
                    else msg["content"]
                )
                print(f"  {i}. {role} {content}")

        # Time information
        now_cest = datetime.now() + timedelta(hours=2)
        print(f"\n🕐 Current CEST time: {now_cest.strftime('%Y-%m-%d %H:%M:%S')}")
        print(
            f"🕐 5 minutes ago: {(now_cest - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print(
            f"🕐 30 minutes ago: {(now_cest - timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')}"
        )

    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🧪 JustCall Time Filtering Test")
    print("This script tests the get_conversation_history time filtering functionality")
    print()

    asyncio.run(test_time_filtering())
