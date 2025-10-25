#!/usr/bin/env python3
"""
Test script to verify AgentService connection to local Mistral model
"""

import asyncio
from services.agent_service import AgentService

# Sample invoice text for testing
SAMPLE_INVOICE_TEXT = """
INVOICE

Date: 2024-09-26
Invoice Number: INV-12345
Bill To: ABC Construction Company

Description         Quantity    Unit Price    Total
Concrete blocks          50        $25.00    $1,250.00
Steel rebar             100        $15.50    $1,550.00
Labor costs               8        $75.00      $600.00

Subtotal:                                   $3,400.00
Tax (8%):                                     $272.00
Total:                                      $3,672.00

Payment due within 30 days.
"""


async def test_agent_service():
    """Test the AgentService with local Mistral model"""

    print("🔧 Testing AgentService with local Mistral model...")
    print("=" * 60)

    # Initialize the service with Docker Model Runner endpoint
    agent_service = AgentService(
        openai_api_key="dummy", local_api_url="http://localhost:12434/engines/v1"
    )

    print("📄 Sample invoice text:")
    print(SAMPLE_INVOICE_TEXT)
    print("=" * 60)

    try:
        # Test invoice data extraction
        result = await agent_service.extract_invoice_data(SAMPLE_INVOICE_TEXT)

        print("✅ SUCCESS: AI extraction completed!")
        print(f"📄 Invoice Number: {result.invoice_number}")
        print(f"📅 Invoice Date: {result.invoice_date}")

        # Validate results
        if result.invoice_number:
            print("✅ Invoice number extracted successfully")
        else:
            print("❌ Invoice number not extracted")

        if result.invoice_date:
            print("✅ Invoice date extracted successfully")
        else:
            print("❌ Invoice date not extracted")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("\n🔍 Troubleshooting tips:")
        print("1. Make sure your local model is running:")
        print("   docker model run ai/mistral:7B-Q4_K_M")
        print("2. Check if the endpoint is accessible:")
        print("   curl http://localhost:12434/v1/models")
        print("3. Verify the port number (12434) is correct")


if __name__ == "__main__":
    asyncio.run(test_agent_service())
