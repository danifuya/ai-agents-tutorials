from crawl4ai import AsyncWebCrawler
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from typing import List, Optional, AsyncGenerator
import asyncpg
import os

from contextlib import asynccontextmanager

from crawl4ai.async_configs import CrawlerRunConfig
from crawl4ai import CacheMode


load_dotenv()


config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)


async def crawl_ai_agent_page(url: str) -> dict:
    """Crawl both homepage and pricing page of an AI agent.

    Args:
        url: The base URL of the AI agent page

    Returns:
        Dict containing homepage and pricing page content
    """
    print(f"Crawling ai agent pages: {url}")
    async with AsyncWebCrawler() as crawler:
        # Crawl homepage
        try:
            homepage_result = await crawler.arun(url=url, config=config)
            if homepage_result.status_code == 404:
                print("Homepage not found!")
                homepage_content = ""
            else:
                homepage_content = homepage_result.markdown
        except Exception as e:
            print(f"Failed to fetch homepage: {e}")
            homepage_content = ""

        # Construct and crawl pricing page
        pricing_url = url.rstrip("/") + "/pricing"
        try:
            pricing_result = await crawler.arun(url=pricing_url, config=config)
            if pricing_result.status_code == 404:
                print("Pricing page not found!")
                pricing_content = ""
            else:
                pricing_content = pricing_result.markdown
        except Exception as e:
            print(f"Failed to fetch pricing page: {e}")
            pricing_content = ""

        return {"homepage": homepage_content, "pricing": pricing_content}


class SourceTypeClassification(BaseModel):
    """Model for source type classification."""

    is_open_source: bool
    confidence_score: float  # Between 0 and 1


class AIAgentListing(BaseModel):
    """Model for AI agent listing data."""

    name: str = Field(description="The name of the AI agent")
    short_description: str = Field(
        default="", description="Brief description of the agent (max 10 words)"
    )
    long_description: str = Field(
        default="",
        description="Detailed description of the agent's capabilities and purpose (max 100 words)",
    )
    website_url: str = Field(description="URL of the agent's primary website")
    logo_url: str = Field(description="URL of the agent's logo image")
    video_url: Optional[str] = Field(
        default="", description="URL of the agent's demo or promotional video"
    )
    github_url: Optional[str] = Field(
        default="", description="URL of the agent's GitHub repository if open source"
    )
    features: List[str] = Field(
        default_factory=list, description="List of key features, each max 10 words"
    )
    use_cases: List[str] = Field(
        default_factory=list, description="List of primary use cases, each max 5 words"
    )
    pricing_tiers: List[float] = Field(
        default_factory=list,
        description="List of pricing tiers in USD (0.0 for free tier)",
    )
    source_type: SourceTypeClassification = Field(
        description="Classification of the agent's source code availability"
    )


model = OpenAIModel("gpt-4o-mini")
system_prompt = """
You are a content manager and expert in scrapping collecting, and summarizing information about ai agents. You will be provided with website links about AI Agents. Your task is to create the content that will be listed as a page for an AI agent directory. Condense each agent info in a listing. Do not copy literally from sources, Use common and easy to understand language. Do not use the word "ai-powered"
output as plain text. 
Each listing has to have: 
- Name
- Short description (max 10 words). be accurate and do not use vague cliche words. Use keywords that you will use both in long description and key features and use cases.
- Long description (max 100 words, starts with "%name is an AI agent/platform, etc etc"). In long description use keywords that have potential to be high-volume keywords. Separate content in differnet lines.
- Array of features (max 10 words each), each starting with capital letters.
- Array of Use cases (max 5 words each), each starting with capital letters.
- website url
- github url (if not provided empty)
- youtube video url (if not provided empty)
- Pricing tiers: List all pricing tiers as float numbers. Free tiers should be listed as 0. Example: [0, 10, 50] for a service with free, $10 and $50 tiers.
- Source type classification: Determine if the agent is open-source or closed-source. Provide:
  * is_open_source: true/false
  * open_source_confidence: float between 0 and 1 indicating confidence level
  
  Use these criteria for classification:
  - Check if source code is publicly available (GitHub link)
  - Higher confidence (>0.8) when clear evidence exists
  - Lower confidence (<0.5) when uncertain
  - Medium confidence (0.5-0.8) when some indicators exist but not definitive
    Only classify as open-source if you have higher confidence than 0.8.


Must do: 
- Do not use the word "ai-powered", ever.
- Use the text and information on the files uploaded to have as a guide of the output you should provide.
- Make sure features and use cases follow instuctions, remember, only caps in the first word after every comma
- Never use bullet points



Reply just with agent data after inserting the agent listing into the database.
"""

listing_summarizer_agent = Agent(
    model,
    system_prompt=system_prompt,
    result_type=AIAgentListing,
)


@listing_summarizer_agent.tool_plain
async def get_ai_agent_information(url: str) -> str:
    """Get content from a specific ai agent page

    Args:
        url: The URL of the ai agent page

    Returns:
        The content of the ai agent page
    """
    print("-" * 100)
    print("getting ai agent information")
    print(url)
    print("-" * 100)
    return await crawl_ai_agent_page(url)
