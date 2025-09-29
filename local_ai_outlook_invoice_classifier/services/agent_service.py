from openai import OpenAI
from pydantic import BaseModel
from typing import Optional
from datetime import date

# Extract JSON from response
import json
import re


class InvoiceData(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None


class AgentService:
    """Service class to handle AI-powered document analysis"""

    def __init__(
        self,
        openai_api_key: str = "dummy",
        local_api_url: str = "http://localhost:12434/engines/v1",
    ):
        self.client = OpenAI(api_key=openai_api_key, base_url=local_api_url)

    async def extract_invoice_data(self, text: str) -> InvoiceData:
        """
        Extract invoice number and date from text using local AI
        """
        try:
            print("🤖 Extracting invoice data with AI...")

            response = self.client.chat.completions.create(
                model="ai/mistral:7B-Q4_K_M",
                messages=[
                    {
                        "role": "system",
                        "content": 'You are an expert at extracting invoice information from documents. Extract the invoice number and invoice date from the provided text. Respond ONLY with JSON in this exact format: {"invoice_number": "value or null", "invoice_date": "YYYY-MM-DD or null"}',
                    },
                    {
                        "role": "user",
                        "content": f"Extract the invoice number and invoice date from this document text:\n\n{text}",
                    },
                ],
                temperature=0.1,
            )

            # Parse the JSON response manually
            response_text = response.choices[0].message.content
            print(f"🤖 Raw AI response: {response_text}")

            json_match = re.search(r"\{[^{}]*\}", response_text)
            if json_match:
                json_data = json.loads(json_match.group())

                # Parse date if it exists and is not null
                invoice_date = None
                if (
                    json_data.get("invoice_date")
                    and json_data["invoice_date"] != "null"
                ):
                    from datetime import datetime

                    try:
                        invoice_date = datetime.strptime(
                            json_data["invoice_date"], "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        pass

                invoice_data = InvoiceData(
                    invoice_number=json_data.get("invoice_number")
                    if json_data.get("invoice_number") != "null"
                    else None,
                    invoice_date=invoice_date,
                )
            else:
                invoice_data = InvoiceData()

            print(f"📊 Extracted data:")
            print(f"  📄 Invoice Number: {invoice_data.invoice_number}")
            print(f"  📅 Invoice Date: {invoice_data.invoice_date}")

            return invoice_data

        except Exception as e:
            print(f"❌ Error extracting invoice data: {e}")
            return InvoiceData()
