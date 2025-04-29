from crawl4ai import AsyncWebCrawler
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from typing import List, Optional

load_dotenv()


async def crawl_listing(url: str) -> str:
    print(f"Crawling listing: {url}")
    # Create an instance of AsyncWebCrawler
    async with AsyncWebCrawler() as crawler:
        # Run the crawler on a URL
        result = await crawler.arun(url=url)

        # Print the extracted content
        return result.markdown


class potential_ai_agent(BaseModel):
    name: str = Field(description="The name of the agent")
    url: str = Field(description="The URL of the agent")
    confidence: float = Field(
        description="The confidence score that the tool is an AI agent between 0 and 1"
    )
    reasoning: Optional[str] = Field(
        default="",
        description="The reasoning for the confidence score",
    )


model = OpenAIModel("gpt-4o-mini")
system_prompt = """You are a content classifier expert. Your task is to filter a list of tools to only return the tools that are AI Agents or AI Agent builders. A toolcan be considered an AI Agent if it is autodenomiated as "AI Agent".
A tool can be considered an AI Agent builder if it's a tool that can help build AI Agents. 
You will be given a list of tools with name, description and url and you will need to return a list of tools that are AI Agents or AI Agent builders (confidence score between 0.9 and 1). 
If you have not enough information from the description and the name, you can use the url to get more information. 
For each tool, return a confidence score between 0 and 1 about how confident you are that the tool is an AI Agent or AI Agent builder.
Be conservative in your assessment. If you are not sure, assign a confidence score below 0.9 and do not return the tool.
Threshold criteria for confidence score:
1. If the tool is autodenomiated as "AI Agent", the confidence score is between 0.9 and 1
2. Just beceause the tool uses AI, it does not mean it is an AI Agent. If it does not use external tools, the confidence score is below 0.5
3. If the tool is not autodenomiated as "AI Agent", but the description and the name suggest that the tool is used to build AI Agents the confidence score is between 0.9 and 1
4. If the tool is an ai powered app but it does not take actions autonomously, the confidence score is between 0.5 and 0.9
"""


listing_filtering_agent = Agent(
    model,
    system_prompt=system_prompt,
    output_type=List[potential_ai_agent],
)


@listing_filtering_agent.tool_plain
async def get_listing_content(url: str) -> str:
    """Get content from a listing homepage

    Args:
        url: The URL of the listing

    Returns:
        The content of the listing homepage
    """
    return await crawl_listing(url)
