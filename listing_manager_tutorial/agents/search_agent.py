from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from typing import List
import datetime
from crawl4ai.async_configs import CrawlerRunConfig
from crawl4ai import AsyncWebCrawler, CacheMode


load_dotenv()


config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)


async def crawl_neurondaily() -> str:
    print("Crawling Neuron Daily")
    # Create an instance of AsyncWebCrawler
    async with AsyncWebCrawler() as crawler:
        # Run the crawler on a URL
        result = await crawler.arun(
            url="https://www.theneurondaily.com/", config=config
        )
        if result.status_code == 404:
            print("Page not found!")
            return "Page not found!"
        # Print the extracted content
        return result.markdown


async def crawl_article(url: str) -> str:
    print(f"Crawling article: {url}")
    # Create an instance of AsyncWebCrawler
    async with AsyncWebCrawler() as crawler:
        # Run the crawler on a URL
        result = await crawler.arun(url=url, config=config)
        if result.status_code == 404:
            print("Page not found!")
            return "Page not found!"
        # Print the extracted content
        return result.markdown


class Tool(BaseModel):
    name: str = Field(description="The name of the tool")
    description: str = Field(description="The description of the tool")
    url: str = Field(description="The website url of the tool")


# Get the current date and time
current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

model = OpenAIModel("gpt-4o-mini")
system_prompt = f"""You are a web crawler that can crawl the Neuron Daily website. Your task is to return tools listed within the "treats to try" section of the articles in the newsletter. If the user asks for a specific article, you should only return the tools listed in that article. If no article specified, return tools from the latest article published on the Neuron Daily.
Today is {current_datetime}
When you return urls of the tools, make sure they are not articles but the website of the tool. Remove all query parameters from the urls.
"""


search_agent = Agent(
    model,
    system_prompt=system_prompt,
    result_type=List[Tool],
)


@search_agent.tool_plain
async def get_latest_articles() -> str:
    """Get list of published articles in Neuron Daily"""
    return await crawl_neurondaily()


@search_agent.tool_plain
async def get_article_content(url: str) -> str:
    """Get content from a specific article on the Neuron Daily website

    Args:
        url: The URL of the article

    Returns:
        The content of the article
    """
    return await crawl_article(url)
