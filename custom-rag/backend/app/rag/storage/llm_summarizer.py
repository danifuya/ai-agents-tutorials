from typing import Optional
import openai
import os
from dataclasses import dataclass
import time
import tiktoken


@dataclass
class SummaryResult:
    """Result from LLM summary generation"""

    summary: str
    model_used: str
    tokens_used: int
    processing_time: float
    success: bool
    error_message: Optional[str] = None


class LLMSummarizer:
    """
    LLM-based document summarizer using OpenAI models

    Generates dense, keyword-rich summaries optimized for vector embeddings
    in hierarchical RAG systems using various OpenAI models.
    """

    # Available OpenAI models with fallbacks
    AVAILABLE_MODELS = {
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-5-mini": "gpt-5-mini",
        "gpt-5-nano": "gpt-5-nano",
    }

    SUMMARY_PROMPT = """You are an expert technical summarizer creating dense, keyword-rich summaries optimized for vector embeddings in a hierarchical RAG system. Your output is critical for similarity search.

**Goal:** Generate a highly concise (max 200 words) summary packed with the most unique and salient information from the document content. Maximize keyword density and specificity.

**Instructions:**

1. **Direct Extraction:** Immediately identify and state the core subject, purpose, key entities (people, projects, tools, concepts), or main outcome of the document.
2. **NO FILLER:** **CRITICAL:** Do **NOT** start with or include phrases like "This document is about...", "This document includes...", "The document contains...", "Summary:", "This summary covers...", etc. Jump straight into the essential information.
3. **Keyword Focus:** Extract and list specific nouns, named entities, technical terms, key actions, decisions, or data points. Prioritize terms that distinguish this document from others.
4. **Conciseness & Structure:** Be extremely concise. Use lists or comma-separated phrases for multiple items if needed to stay under the 200-word limit. Ensure logical flow, starting with the main topic/purpose.
5. **Context Awareness:** Use the document title for context but **do not repeat the title** in the summary unless a specific part adds critical unique information not present in the content.
6. **Structured Data Handling:** For tables or lists, state the main subject/purpose and list the key data categories, column headers, or types of items present.
7. **Output:** Generate only the summary content itself.

**Example Goal:** Instead of "This document outlines project tasks...", prefer "TeamMind project task: Awaiting feedback from Simone, Max for next steps. Blockers: feedback dependence. Priority: Medium. Mentions: project metadata, people, dates."

Now summarize the following document:

**Title:** {title}

**Content:**
{content}"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        max_tokens: int = 300,
        temperature: float = 0.3,
        max_input_tokens: int = 100000,
    ):
        """
        Initialize LLM summarizer

        Args:
            model: OpenAI model to use (e.g., "gpt-4o-mini", "gpt-4o", "gpt-4-turbo")
            api_key: OpenAI API key (uses OPENAI_API_KEY env var if not provided)
            max_tokens: Maximum tokens for summary generation
            temperature: Temperature for generation (0.0-2.0, lower = more focused)
            max_input_tokens: Maximum tokens for input content (default 100k)
        """
        # Validate model
        if model not in self.AVAILABLE_MODELS:
            available = ", ".join(self.AVAILABLE_MODELS.keys())
            raise ValueError(f"Model '{model}' not supported. Available: {available}")

        self.model = self.AVAILABLE_MODELS[model]
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_input_tokens = max_input_tokens

        # Set up OpenAI client - uses OPENAI_API_KEY from environment if api_key is None
        self.client = openai.OpenAI(api_key=api_key)

        # Initialize tokenizer for token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o-mini")
        except KeyError:
            # Fallback to cl100k_base encoding if model not found
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in the text

        Args:
            text: Text to analyze

        Returns:
            Estimated token count
        """
        return len(self.tokenizer.encode(text))

    def _truncate_content_to_token_limit(self, content: str, title: str) -> str:
        """
        Truncate content to fit within the token limit, preserving structure

        Args:
            content: Document content to truncate
            title: Document title

        Returns:
            Truncated content that fits within max_input_tokens
        """
        # Create the base prompt template to estimate its token usage
        base_prompt = self.SUMMARY_PROMPT.format(title=title, content="")
        base_tokens = self._estimate_tokens(base_prompt)

        # Reserve tokens for the base prompt and some buffer
        available_tokens = self.max_input_tokens - base_tokens - 100  # 100 token buffer

        # If content is already within limits, return as-is
        content_tokens = self._estimate_tokens(content)
        if content_tokens <= available_tokens:
            return content

        # Truncate content by approximating characters per token ratio
        # Typical ratio is ~4 characters per token for English text
        chars_per_token = len(content) / content_tokens if content_tokens > 0 else 4
        target_chars = int(available_tokens * chars_per_token)

        if target_chars >= len(content):
            return content

        # Truncate at word boundary and add truncation notice
        truncated = content[:target_chars].rsplit(' ', 1)[0]
        truncated += "\n\n[NOTE: Content truncated due to length - this is a partial document]"

        return truncated

    def generate_summary(self, content: str, title: str = "Document") -> SummaryResult:
        """
        Generate optimized summary using OpenAI LLM

        Args:
            content: Document content to summarize
            title: Document title for context

        Returns:
            SummaryResult with summary and metadata
        """
        start_time = time.time()

        try:
            # Truncate content to fit within token limits
            truncated_content = self._truncate_content_to_token_limit(content, title)

            # Prepare the prompt
            prompt = self.SUMMARY_PROMPT.format(title=title, content=truncated_content)

            # Call OpenAI API
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                max_output_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            processing_time = time.time() - start_time

            # Extract summary
            summary = response.output[0].content[0].text
            tokens_used = response.usage.total_tokens

            return SummaryResult(
                summary=summary,
                model_used=self.model,
                tokens_used=tokens_used,
                processing_time=processing_time,
                success=True,
            )

        except openai.RateLimitError as e:
            processing_time = time.time() - start_time
            return SummaryResult(
                summary="",
                model_used=self.model,
                tokens_used=0,
                processing_time=processing_time,
                success=False,
                error_message=f"Rate limit exceeded: {str(e)}",
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return SummaryResult(
                summary="",
                model_used=self.model,
                tokens_used=0,
                processing_time=processing_time,
                success=False,
                error_message=f"Unexpected error: {str(e)}",
            )

    def get_model_info(self) -> dict:
        """Get information about the current model configuration"""
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "max_input_tokens": self.max_input_tokens,
            "temperature": self.temperature,
            "available_models": list(self.AVAILABLE_MODELS.keys()),
        }
