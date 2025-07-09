from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ImageUrl, DocumentUrl, RunContext, BinaryContent
from pydantic_ai.models.openai import OpenAIModel
from typing import List, Optional
import httpx


load_dotenv()


class TechnicalSpecification(BaseModel):
    name: str = Field(description="Attribute name", max_length=22)
    value: str = Field(description="Attribute value", max_length=22)


class Variant(BaseModel):
    technical_specifications: List[TechnicalSpecification] = Field(
        description="Technical specifications of the variant"
    )


class ValidationError(BaseModel):
    """Pydantic validation error for the listing_summarizer_agent"""

    explanation: str


model = OpenAIModel("gpt-4o-mini")
system_prompt = """You are an assistant that extracts product variants and their technical specifications.
You will be provided with content in markdown format containing product information extracted from a distributor's website.
Your objective is to identify the product variants and filter the information to extract only technical specifications.
Variants are the different versions of the product that can be purchased (e.g., color, size, dimensions, etc.).
Products related to the main product are not variants.

Qualitative information is not a technical specification.

Important:
- Never add the product model or reference as a specification, even if the product model or reference appears on the product page.
- Include the product material as a specification if it appears somewhere. If it does not appear, do not add the material attribute.
- Attribute name cannot exceed 22 characters; use abbreviations if necessary.
- Attribute value cannot exceed 22 characters; use abbreviations if necessary.

Example of information that is not a technical specification:

- Code, model number or name, product reference (e.g., Code, Ref, Reference, SKU, Model)
- Product description
- Product advantages
- Product disadvantages
- Product price
- Product offer

Expected format:
- Units of measurement go at the end of the attribute name (e.g., Length (cm), Weight (kg))
- If the product contains multiple variants, include inside each variant the technical specifications that are different between the variants (e.g., Color, Size, Dimensions, etc.).

If the product contains images that may contain technical specifications, use the extract_image_description tool to extract information from the most relevant images. Use the tool a maximum of 10 times.
If the product contains a PDF that may contain technical specifications, use the extract_pdf_information tool to extract the information.
Avoid using instruction manuals or installation manuals to extract technical specifications. If a technical data sheet PDF exists, use the information from that PDF.
"""


listing_summarizer_agent = Agent(
    model,
    system_prompt=system_prompt,
    output_type=List[Variant],
    retries=3,
)


@listing_summarizer_agent.tool(retries=15)
async def extract_pdf_information(ctx: RunContext[None], pdf_url: str) -> str:
    """
    Extracts technical specifications from a PDF.
    """
    agent = Agent(model="openai:gpt-4o")
    try:
        if not pdf_url.lower().endswith(".pdf"):
            async with httpx.AsyncClient() as client:
                response = await client.get(pdf_url)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "").lower()
                if "application/pdf" in content_type:
                    pdf_bytes = await response.aread()
                    document_input = BinaryContent(
                        data=pdf_bytes, media_type="application/pdf"
                    )
                else:
                    print(
                        f"URL {pdf_url} did not return a PDF. Content-Type: {content_type}"
                    )
                    return "No technical specifications in the document"
        else:
            document_input = DocumentUrl(url=pdf_url)

        result = await agent.run(
            [
                """If the document contains technical specifications, extract them. Otherwise, return 'No technical specifications in the document'.
                A technical specification is information that can be measured or quantified. Always provide the name and value of the technical specification.
                Some technical specifications are represented by images. For example: weight, battery, motor power, colors.
                If the product has different variants that can be purchased, extract the variants and include the attributes that are different between the variants.""",
                document_input,
            ],
            usage=ctx.usage,
        )
        print("tool call extract_pdf_information:", pdf_url, "\n", result.output)
        return result.output
    except httpx.HTTPStatusError as e:
        print(f"HTTP error fetching PDF from {pdf_url}: {e}")
        return "No technical specifications in the document"
    except Exception as e:
        print("error extracting pdf information:", pdf_url, e)
        return "No technical specifications in the document"


@listing_summarizer_agent.tool(retries=20)
async def extract_image_description(ctx: RunContext[None], image_url: str) -> str:
    """
    Extracts technical specifications from an image.
    """
    agent = Agent(model="openai:gpt-4o")
    try:
        result = await agent.run(
            [
                """If the image contains technical specifications, extract them. Otherwise, return 'No technical specifications in the image'.
            A technical specification is information that can be measured or quantified. Always provide the name and value of the technical specification.""",
                ImageUrl(url=image_url),
            ],
            usage=ctx.usage,
        )
        print("tool call extract_image_description:", image_url, "\n", result.output)
        return result.output
    except Exception as e:
        print("error extracting image description:", e)
        return "No technical specifications in the image"
