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


class InsertionResult(BaseModel):
    """Model for insertion result."""

    success: bool = Field(description="Whether the insertion was successful")
    name: str = Field(description="The name of the AI agent")


class SourceTypeClassification(BaseModel):
    """Model for source type classification."""

    is_open_source: bool
    confidence_score: float


class TagScore(BaseModel):
    """Model for tag confidence scoring."""

    tag_id: str
    tag_name: str
    score: float


class AIAgentListing(BaseModel):
    """Model for AI agent listing data."""

    name: str
    short_description: Optional[str] = ""
    long_description: Optional[str] = ""
    website_url: str
    logo_url: Optional[str] = ""
    video_url: Optional[str] = ""
    github_url: Optional[str] = ""
    features: List[str] = Field(default_factory=list)
    use_cases: List[str] = Field(default_factory=list)
    pricing_tiers: List[float] = Field(default_factory=list)
    source_type: SourceTypeClassification
    category_id: str
    tag_scores: List[TagScore] = Field(default_factory=list)

    class Config:
        validate_assignment = True

    def __init__(self, **data):
        # Ensure URLs are empty strings instead of None
        for url_field in ["logo_url", "video_url", "github_url", "website_url"]:
            if url_field in data and data[url_field] is None:
                data[url_field] = ""

        super().__init__(**data)


async def insert_ai_agent_in_db(agent_data: AIAgentListing) -> str:
    """Insert AI agent information into the database."""
    slug = slugify(agent_data.name)

    try:
        async with database_connect() as pool:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # First get the source type ID
                    source_type_slug = (
                        "open-source"
                        if agent_data.source_type.is_open_source
                        else "closed-source"
                    )
                    source_type_id = await conn.fetchval(
                        "SELECT id FROM public.source_types WHERE slug = $1",
                        source_type_slug,
                    )

                    if not source_type_id:
                        raise ValueError(
                            f"Source type {source_type_slug} not found in database"
                        )

                    # Check if agent exists
                    existing = await conn.fetchrow(
                        "SELECT id FROM public.listings WHERE slug = $1", slug
                    )

                    if existing:
                        return (
                            f"AI agent '{agent_data.name}' already exists in database"
                        )

                    # Insert listing and get ID
                    listing_id = await conn.fetchval(
                        """
                        INSERT INTO public.listings 
                        (slug, name, short_description, long_description, website_url, 
                         logo_url, video_url, github_url)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        RETURNING id
                        """,
                        slug,
                        agent_data.name,
                        agent_data.short_description,
                        agent_data.long_description,
                        agent_data.website_url,
                        agent_data.logo_url,
                        agent_data.video_url,
                        agent_data.github_url,
                    )

                    # Insert features
                    if agent_data.features:
                        await conn.executemany(
                            """
                            INSERT INTO public.listings_features 
                            (listing_id, name)
                            VALUES ($1, $2)
                            """,
                            [(listing_id, feature) for feature in agent_data.features],
                        )

                    # Insert use cases
                    if agent_data.use_cases:
                        await conn.executemany(
                            """
                            INSERT INTO public.listings_use_cases 
                            (listing_id, name)
                            VALUES ($1, $2)
                            """,
                            [
                                (listing_id, use_case)
                                for use_case in agent_data.use_cases
                            ],
                        )

                    # Insert pricing tiers
                    if agent_data.pricing_tiers:
                        await conn.executemany(
                            """
                            INSERT INTO public.pricing_tiers 
                            (listing_id, price)
                            VALUES ($1, $2)
                            """,
                            [(listing_id, price) for price in agent_data.pricing_tiers],
                        )

                    # Insert source type relation
                    await conn.execute(
                        """
                        INSERT INTO public.listings_source_types 
                        (listing_id, source_type_id)
                        VALUES ($1, $2)
                        """,
                        listing_id,
                        source_type_id,
                    )

                    # Insert category assignment
                    await conn.execute(
                        """
                        INSERT INTO public.listings_categories 
                        (listing_id, category_id)
                        VALUES ($1, $2)
                        """,
                        listing_id,
                        agent_data.category_id,
                    )

                    # Insert tag relations
                    if agent_data.tag_scores:
                        # First verify all tags exist
                        for tag_score in agent_data.tag_scores:
                            tag_exists = await conn.fetchval(
                                """
                                SELECT id FROM public.tags 
                                WHERE id = $1
                                """,
                                tag_score.tag_id,
                            )
                            if not tag_exists:
                                raise ValueError(
                                    f"Tag with ID {tag_score.tag_id} not found in database"
                                )

                        # Insert tag relations
                        await conn.executemany(
                            """
                            INSERT INTO public.listings_tags 
                            (listing_id, tag_id)
                            VALUES ($1, $2)
                            """,
                            [(listing_id, tag.tag_id) for tag in agent_data.tag_scores],
                        )
                    print(f"Inserted AI agent '{agent_data.name}' into database")
                    return f"Inserted AI agent '{agent_data.name}' into database"
    except Exception as e:
        return f"Error inserting AI agent into database: {str(e)}"


model = OpenAIModel("gpt-4o-mini")
system_prompt = """
You are a database and content manager expert. You will be provided with a list of AI agents and their information. Your task is to insert the information into the database.

Reply just with the success or error message indicating names of the agents that were inserted.
"""

db_inserter_agent = Agent(
    model,
    system_prompt=system_prompt,
    result_type=InsertionResult,
)


@db_inserter_agent.tool_plain
async def insert_agent_listing(
    name: str,
    short_description: str,
    long_description: str,
    website_url: str,
    logo_url: str,
    video_url: str,
    github_url: str,
    features: List[str],
    use_cases: List[str],
    pricing_tiers: List[float],
    is_open_source: bool,
    open_source_confidence: float,
    category_id: str,
    tag_assignments: Optional[List[dict]] = None,
) -> str:
    """Insert an AI agent listing into the database with all its associated data.

    Args:
        name: The name of the AI agent
        short_description: Brief description (max 10 words)
        long_description: Detailed description (max 100 words)
        website_url: URL of the agent's website
        logo_url: URL of the agent's logo image
        video_url: URL of a demo video if available
        github_url: URL of the GitHub repository if available
        features: List of key features (max 10 words each)
        use_cases: List of use cases (max 5 words each)
        pricing_tiers: List of prices as floats (0 for free tier)
        is_open_source: Boolean indicating if agent is open source
        open_source_confidence: Confidence score (0-1) for open source classification
        category_id: ID of the single most appropriate category
        tag_assignments: List of dictionaries containing tag information with structure:
            [
                {
                    "tag_id": "uuid-string",  # UUID of the tag in the database
                    "tag_name": "tag name",   # Name of the tag for reference
                    "score": 0.95             # Confidence score between 0 and 1
                }
            ]
            If not provided, no tags will be assigned.

    Returns:
        Success or error message indicating the result of the database insertion
    """
    # Use empty list if tag_assignments is None
    if tag_assignments is None:
        tag_assignments = []

    tag_scores = [
        TagScore(tag_id=tag["tag_id"], tag_name=tag["tag_name"], score=tag["score"])
        for tag in tag_assignments
    ]

    agent_data = AIAgentListing(
        name=name,
        short_description=short_description,
        long_description=long_description,
        website_url=website_url,
        logo_url=logo_url,
        video_url=video_url,
        github_url=github_url,
        features=features,
        use_cases=use_cases,
        pricing_tiers=pricing_tiers,
        source_type=SourceTypeClassification(
            is_open_source=is_open_source, confidence_score=open_source_confidence
        ),
        category_id=category_id,
        tag_scores=tag_scores,
    )
    print("Inserting agent data to db", agent_data)
    print("-" * 100)
    return await insert_ai_agent_in_db(agent_data)
