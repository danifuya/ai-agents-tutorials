"""
Voyage AI Reranker Service

This module provides reranking functionality using Voyage AI's rerank models
to improve the quality of retrieved chunks by reordering them based on relevance.
"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import voyageai


@dataclass
class RerankResult:
    """Result from reranking operation"""

    reranked_chunks: List[Dict[str, Any]]
    original_count: int
    reranked_count: int
    rerank_time: float
    model: str


class VoyageReranker:
    """
    Voyage AI Reranker for improving retrieval quality

    Uses Voyage AI's rerank models to reorder retrieved chunks
    based on their relevance to the query.
    """

    def __init__(
        self,
        model: str = "rerank-2.5",
        api_key: Optional[str] = None,
    ):
        """
        Initialize Voyage AI reranker

        Args:
            model: Voyage rerank model to use (default: rerank-2.5)
            api_key: Voyage API key (uses VOYAGE_API_KEY env var if None)
        """
        self.model = model
        self.api_key = api_key or os.getenv("VOYAGE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Voyage API key not found. Set VOYAGE_API_KEY environment variable "
                "or pass api_key parameter"
            )

        # Initialize async client
        self.client = voyageai.AsyncClient(api_key=self.api_key)

    async def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> RerankResult:
        """
        Rerank chunks based on relevance to query

        Args:
            query: Search query string
            chunks: List of chunk dictionaries with 'content' field
            top_k: Number of top results to return (None = return all)

        Returns:
            RerankResult with reranked chunks and metadata
        """
        import time

        if not chunks:
            return RerankResult(
                reranked_chunks=[],
                original_count=0,
                reranked_count=0,
                rerank_time=0.0,
                model=self.model,
            )

        start_time = time.time()

        # Extract document texts for reranking
        documents = [chunk.get("content", "") for chunk in chunks]

        # Call Voyage AI rerank API
        try:
            rerank_response = await self.client.rerank(
                query=query, documents=documents, model=self.model, top_k=top_k
            )
        except Exception as e:
            raise RuntimeError(f"Voyage AI rerank failed: {e}")

        rerank_time = time.time() - start_time

        # Reconstruct chunks with rerank scores
        reranked_chunks = []
        for result in rerank_response.results:
            original_chunk = chunks[result.index]
            reranked_chunk = {
                **original_chunk,
                "rerank_score": result.relevance_score,
                "rerank_index": result.index,  # Original position
            }
            reranked_chunks.append(reranked_chunk)

        return RerankResult(
            reranked_chunks=reranked_chunks,
            original_count=len(chunks),
            reranked_count=len(reranked_chunks),
            rerank_time=rerank_time,
            model=self.model,
        )
