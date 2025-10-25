from typing import Dict, Any, Optional
from dataclasses import dataclass
import re
from app.rag.embeddings.embedding_generator import EmbeddingGenerator


@dataclass
class ProcessedQuery:
    """Processed query with embedding and metadata"""

    original_text: str
    cleaned_text: str
    embedding: list[float]
    tokens_used: int
    processing_time: float


class QueryProcessor:
    """
    Basic query processing for retrieval system

    Handles:
    - Query text cleaning and preprocessing
    - Embedding generation
    - Query expansion (future)
    """

    def __init__(
        self,
        embedding_provider: str = "openai",
        embedding_api_key: Optional[str] = None,
    ):
        """
        Initialize query processor

        Args:
            embedding_provider: Provider for embeddings ("openai", "jina", "local")
            embedding_api_key: API key for external providers (if needed)
        """
        self.embedder = EmbeddingGenerator(
            provider=embedding_provider, api_key=embedding_api_key
        )

    def process_query(self, query_text: str) -> ProcessedQuery:
        """
        Process a user query for retrieval

        Args:
            query_text: Raw user query text

        Returns:
            ProcessedQuery with embedding and metadata
        """
        import time

        start_time = time.time()

        # Clean the query text
        cleaned_text = self._clean_query_text(query_text)

        # Generate embedding
        embedding_result = self.embedder.embed(cleaned_text)

        processing_time = time.time() - start_time

        return ProcessedQuery(
            original_text=query_text,
            cleaned_text=cleaned_text,
            embedding=embedding_result.embedding,
            tokens_used=embedding_result.tokens_used,
            processing_time=processing_time,
        )

    def _clean_query_text(self, text: str) -> str:
        """
        Clean and preprocess query text

        Args:
            text: Raw query text

        Returns:
            Cleaned query text
        """
        if not text:
            return ""

        # Basic cleaning
        cleaned = text.strip()

        # Remove excessive whitespace
        cleaned = " ".join(cleaned.split())

        # Remove special characters that might interfere with search
        # Keep basic punctuation for natural language processing

        # Remove excessive punctuation
        cleaned = re.sub(r"\.{2,}", ".", cleaned)
        cleaned = re.sub(r"\?{2,}", "?", cleaned)
        cleaned = re.sub(r"!{2,}", "!", cleaned)

        # Final cleanup
        cleaned = " ".join(cleaned.split())

        return cleaned

    def expand_query(self, query_text: str) -> Dict[str, Any]:
        """
        Basic query expansion (placeholder for future enhancement)

        Args:
            query_text: Original query text

        Returns:
            Dict with original and expanded queries
        """
        # For now, just return the original query
        # In the future, this could:
        # - Add synonyms
        # - Generate related terms
        # - Create multiple query variations

        cleaned = self._clean_query_text(query_text)

        return {
            "original": query_text,
            "cleaned": cleaned,
            "expanded_terms": [],  # Future: add synonyms, related terms
            "query_variations": [cleaned],  # Future: add multiple variations
        }

    def analyze_query_intent(self, query_text: str) -> Dict[str, Any]:
        """
        Analyze query intent and characteristics

        Args:
            query_text: Query text to analyze

        Returns:
            Dict with query analysis
        """
        cleaned = self._clean_query_text(query_text)
        words = cleaned.split()

        # Basic query analysis
        analysis = {
            "word_count": len(words),
            "character_count": len(cleaned),
            "is_short_query": len(words) <= 3,
            "is_long_query": len(words) >= 10,
            "has_question_words": any(
                word.lower() in ["what", "how", "why", "when", "where", "who", "which"]
                for word in words
            ),
            "is_question": cleaned.endswith("?"),
            "query_type": "unknown",
        }

        # Determine query type
        if analysis["is_question"] or analysis["has_question_words"]:
            analysis["query_type"] = "question"
        elif any(word.lower() in ["find", "search", "look", "show"] for word in words):
            analysis["query_type"] = "search_command"
        elif len(words) <= 3:
            analysis["query_type"] = "keyword_search"
        else:
            analysis["query_type"] = "descriptive"

        return analysis

    def batch_process_queries(self, queries: list[str]) -> list[ProcessedQuery]:
        """
        Process multiple queries efficiently

        Args:
            queries: List of query strings

        Returns:
            List of ProcessedQuery objects
        """
        import time

        start_time = time.time()

        if not queries:
            return []

        # Clean all queries
        cleaned_queries = [self._clean_query_text(q) for q in queries]

        # Generate embeddings in batch for efficiency
        batch_result = self.embedder.embed_batch(cleaned_queries)

        total_time = time.time() - start_time
        avg_time_per_query = total_time / len(queries)

        # Create ProcessedQuery objects
        processed_queries = []
        for i, (original, cleaned) in enumerate(zip(queries, cleaned_queries)):
            processed_queries.append(
                ProcessedQuery(
                    original_text=original,
                    cleaned_text=cleaned,
                    embedding=batch_result.embeddings[i],
                    tokens_used=batch_result.tokens_used
                    // len(queries),  # Approximate per query
                    processing_time=avg_time_per_query,
                )
            )

        return processed_queries

    def get_embedding_info(self) -> Dict[str, Any]:
        """Get information about the embedding model being used"""
        return {
            "provider": self.embedder.provider.name,
            "model_name": getattr(self.embedder.provider, "model_name", "unknown"),
            "embedding_dimensions": getattr(
                self.embedder.provider, "dimensions", "unknown"
            ),
            "supports_batch": True,
        }
