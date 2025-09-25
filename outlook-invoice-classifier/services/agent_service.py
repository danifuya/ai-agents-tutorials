from openai import OpenAI
from pydantic import BaseModel
from typing import Optional
from datetime import date


class InvoiceData(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None


class AgentService:
    """Service class to handle AI-powered document analysis"""

    def __init__(self, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)

    async def extract_invoice_data(self, text: str) -> InvoiceData:
        """
        Extract invoice number and date from text using OpenAI
        """
        try:
            print("🤖 Extracting invoice data with AI...")

            response = self.client.responses.parse(
                model="gpt-4o-mini",
                input=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting invoice information from documents. Extract the invoice number and invoice date from the provided text. For the invoice_date field, return it as a proper date in YYYY-MM-DD format. If you cannot find either piece of information, set it to null.",
                    },
                    {
                        "role": "user",
                        "content": f"Extract the invoice number and invoice date from this document text:\n\n{text}",
                    },
                ],
                text_format=InvoiceData,
            )

            invoice_data = response.output_parsed

            print(f"📊 Extracted data:")
            print(f"  📄 Invoice Number: {invoice_data.invoice_number}")
            print(f"  📅 Invoice Date: {invoice_data.invoice_date}")

            return invoice_data

        except Exception as e:
            print(f"❌ Error extracting invoice data: {e}")
            return InvoiceData()
