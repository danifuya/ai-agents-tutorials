from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from typing import List, Optional, AsyncGenerator
import asyncpg
import os
import re
import unicodedata
from contextlib import asynccontextmanager
import asyncio


load_dotenv()


@asynccontextmanager
async def database_connect() -> AsyncGenerator[asyncpg.Pool, None]:
    """Connect to the PostgreSQL database."""
    # Get database connection details from environment variables
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")

    # Create connection string
    dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    # Create connection pool with disabled statement cache for PgBouncer compatibility
    pool = await asyncpg.create_pool(
        dsn,
        statement_cache_size=0,  # Disable statement cache for PgBouncer
    )
    try:
        yield pool
    finally:
        await pool.close()


def slugify(value: str) -> str:
    """Slugify a string, to make it URL friendly."""
    # Replace Extended Latin characters with ASCII
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[\s-]+", "-", value)


class SourceTypeClassification(BaseModel):
    """Model for source type classification."""

    is_open_source: bool = Field(
        description="Indicates whether the agent is open source (true) or closed source (false)"
    )
    confidence_score: float = Field(
        description="Confidence level of the open source classification, ranging from 0 to 1"
    )


class CategoryScore(BaseModel):
    """Model for category confidence scoring."""

    category_id: str = Field(description="UUID of the category in the database")
    category_name: str = Field(description="Display name of the category for reference")
    score: float = Field(
        description="Confidence score for category relevance, ranging from 0 to 1"
    )


class TagScore(BaseModel):
    """Model for tag confidence scoring."""

    tag_id: str = Field(description="UUID of the tag in the database")
    tag_name: str = Field(description="Display name of the tag for reference")
    score: float = Field(
        description="Confidence score for tag relevance, ranging from 0 to 1"
    )


class AIAgentListing(BaseModel):
    """Model for AI agent listing data."""

    name: str = Field(description="The name of the AI agent")
    short_description: Optional[str] = Field(
        default=None, description="Brief description of the agent (max 10 words)"
    )
    long_description: Optional[str] = Field(
        default=None,
        description="Detailed description of the agent's capabilities and purpose (max 100 words)",
    )
    website_url: str = Field(description="URL of the agent's primary website")
    logo_url: str = Field(description="URL of the agent's logo image")
    video_url: Optional[str] = Field(
        default=None, description="URL of the agent's demo or promotional video"
    )
    github_url: Optional[str] = Field(
        default=None, description="URL of the agent's GitHub repository if open source"
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
    category_score: CategoryScore = Field(
        description="Category of the agent with the confidence score"
    )
    tag_scores: List[TagScore] = Field(
        default_factory=list,
        description="List of relevant tags with their confidence scores",
    )


async def get_categories_from_db() -> List[dict]:
    """Fetch all categories from the database."""
    print("-" * 100)
    print("getting categories")
    print("-" * 100)
    try:
        async with database_connect() as pool:
            async with pool.acquire() as conn:
                categories = await conn.fetch(
                    """
                    SELECT id, name
                    FROM public.categories
                    """
                )

                return [dict(cat) for cat in categories]
    except Exception as e:
        print(f"Error fetching categories: {str(e)}")
        return []


async def get_category_tags_from_db(category_id: str) -> List[dict]:
    """Fetch tags used by other listings in the same category."""
    try:
        async with database_connect() as pool:
            async with pool.acquire() as conn:
                tags = await conn.fetch(
                    """
                    SELECT DISTINCT t.id, t.name, COUNT(lt.listing_id) as usage_count
                    FROM public.tags t
                    JOIN public.listings_tags lt ON lt.tag_id = t.id
                    JOIN public.listings_categories lc ON lc.listing_id = lt.listing_id
                    WHERE lc.category_id = $1
                    GROUP BY t.id, t.name
                    ORDER BY usage_count DESC
                    """,
                    category_id,
                )
                print("tags fetched are", tags)
                print("-" * 100)
                # Still only return id and name in the result
                return [{"id": tag["id"], "name": tag["name"]} for tag in tags]
    except Exception as e:
        print(f"Error fetching category tags: {str(e)}")
        return []


model = OpenAIModel("gpt-4o-mini")

# Fetch categories at startup
categories = asyncio.run(get_categories_from_db())
categories_text = "\n".join(
    [f"- {cat['name']} (ID: {cat['id']})" for cat in categories]
)

system_prompt = f"""
You are a listing classifier expert. You will be provided with information about an AI Agent. Your task is to assign a category and tags to the AI Agent.
The information you will be provided with is:
- Name
- Short description
- Long description 
- Array of features of the agent
- Array of Use cases of the agent
- github url (optional)
- youtube video url (optional)

Available categories:
{categories_text}

For the category assignment:
  * Analyze the agent's description, features, and use cases
  * Select the SINGLE most appropriate category that best describes the agent's primary purpose from the available categories above
  * Assign only the most fitting category to the listing
  * Assign as category "agent builder" only when the tool is clearly used to create sector/industry-agnostic agents.

- Tag Assignment: After selecting the category, you will:
  * Fetch commonly used tags in that category using get_category_tags tool
  * Analyze the agent against each tag
  * For matching tags, create a list of dictionaries in this exact format:
  * Be extremely conservative - only assign scores > 0.9 for perfect matches
  * Maximum of 2 tags will be used, selecting those confidence scores and about 0.9
  * Tags must be mutually exclusive (e.g., don't assign both 'email' and 'email-marketing')

Tag scoring criteria:
- Score 0.9+: Perfect match with tag's meaning and purpose
- Score 0.7-0.8: Strong match but not perfect
- Score < 0.7: Any uncertainty or partial match
- Only tags scoring > 0.9 will be used
"""

listing_classifier_agent = Agent(
    model,
    system_prompt=system_prompt,
    result_type=AIAgentListing,
)


@listing_classifier_agent.tool_plain(retries=0)
async def get_category_tags(category_id: str) -> List[dict]:
    """Get commonly used tags for a specific category.

    Args:
        category_id: The unique identifier of the category to fetch tags for

    Returns:
        List of dictionaries containing:
        - id: The unique identifier of the tag
        - name: The display name of the tag
    """
    print("-" * 100)
    print("getting category tags")
    print(category_id)
    print("-" * 100)
    return await get_category_tags_from_db(category_id)
