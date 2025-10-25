from typing import List, Dict, Any, Optional
from psycopg import AsyncConnection
from dataclasses import dataclass

from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.document_chunks_repository import DocumentChunksRepository
from app.rag.reranking.voyage_reranker import VoyageReranker


@dataclass
class RetrievalResult:
    """Result from hierarchical retrieval"""

    chunks: List[Dict[str, Any]]
    document_candidates: List[Dict[str, Any]]
    total_documents_searched: int
    total_chunks_found: int
    stage1_time: float
    stage2_time: float
    rerank_time: float
    total_time: float
    reranked: bool


@dataclass
class ChunkMatch:
    """Individual chunk match with document context"""

    chunk_id: int
    content: str
    document_id: int
    document_title: str
    document_summary: str
    similarity_score: float
    embedding: List[float]


class HierarchicalRetrieval:
    """
    Two-stage hierarchical retrieval system:

    Stage 1: Document-level filtering using summary embeddings
    - Find candidate documents based on semantic similarity to query
    - Dramatically reduces search space

    Stage 2: Chunk-level retrieval within candidate documents
    - Search chunks only from candidate documents
    - Returns most relevant chunks with document context
    """

    def __init__(
        self,
        db_connection: AsyncConnection,
        stage1_similarity_threshold: float = 0.3,
        stage1_document_limit: int = 20,
        stage2_chunk_limit: int = 10,
        reranker: Optional[VoyageReranker] = None,
        use_reranking: bool = True,
    ):
        """
        Initialize hierarchical retrieval system

        Args:
            db_connection: Active database connection
            stage1_similarity_threshold: Minimum similarity for document candidates
            stage1_document_limit: Max documents to consider in stage 1
            stage2_chunk_limit: Max chunks to return from stage 2
            reranker: Optional VoyageReranker instance for reranking
            use_reranking: Whether to use reranking (requires reranker or VOYAGE_API_KEY)
        """
        self.doc_repo = DocumentRepository(db_connection)
        self.chunk_repo = DocumentChunksRepository(db_connection)
        self.connection = db_connection

        # Configuration
        self.stage1_threshold = stage1_similarity_threshold
        self.stage1_limit = stage1_document_limit
        self.stage2_limit = stage2_chunk_limit

        # Reranking setup
        self.use_reranking = use_reranking
        if use_reranking:
            self.reranker = reranker or VoyageReranker()
        else:
            self.reranker = None

    async def search(
        self,
        query_embedding: List[float],
        query_text: str,
        stage1_limit: Optional[int] = None,
        stage2_limit: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> RetrievalResult:
        """
        Perform two-stage hierarchical search

        Args:
            query_embedding: Vector embedding of the search query
            stage1_limit: Override for document candidate limit
            stage2_limit: Override for final chunk limit
            similarity_threshold: Override for similarity threshold

        Returns:
            RetrievalResult with chunks, timing, and metadata
        """
        import time

        total_start = time.time()

        # Use provided limits or defaults
        doc_limit = stage1_limit or self.stage1_limit
        chunk_limit = stage2_limit or self.stage2_limit
        threshold = similarity_threshold or self.stage1_threshold

        # Stage 1: Find document candidates
        stage1_start = time.time()
        document_candidates = await self._stage1_document_filtering(
            query_embedding, query_text, threshold, doc_limit
        )
        stage1_time = time.time() - stage1_start

        if not document_candidates:
            # No candidate documents found
            return RetrievalResult(
                chunks=[],
                document_candidates=[],
                total_documents_searched=0,
                total_chunks_found=0,
                stage1_time=stage1_time,
                stage2_time=0.0,
                rerank_time=0.0,
                total_time=time.time() - total_start,
                reranked=False,
            )

        # Stage 2: Find best chunks from candidate documents
        stage2_start = time.time()
        chunk_matches = await self._stage2_chunk_retrieval(
            query_embedding,
            query_text,
            [doc["id"] for doc in document_candidates],
            chunk_limit,
        )
        stage2_time = time.time() - stage2_start

        # Stage 3: Rerank chunks
        rerank_time = 0.0
        reranked = False
        if self.use_reranking and self.reranker and chunk_matches:
            rerank_result = await self.reranker.rerank(
                query=query_text, chunks=chunk_matches, top_k=chunk_limit
            )
            chunk_matches = rerank_result.reranked_chunks
            rerank_time = rerank_result.rerank_time
            reranked = True

        total_time = time.time() - total_start

        return RetrievalResult(
            chunks=chunk_matches,
            document_candidates=document_candidates,
            total_documents_searched=len(document_candidates),
            total_chunks_found=len(chunk_matches),
            stage1_time=stage1_time,
            stage2_time=stage2_time,
            rerank_time=rerank_time,
            total_time=total_time,
            reranked=reranked,
        )

    async def _stage1_document_filtering(
        self,
        query_embedding: List[float],
        query_text: str,
        threshold: float,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Stage 1: Filter documents by summary similarity OR full-text search
        Combines embedding similarity with full-text search for better recall

        Returns list of candidate documents with similarity scores
        """
        # Use hybrid search that combines embedding similarity and full-text search
        similar_docs = await self.doc_repo.search_documents_hybrid(
            query_embedding, query_text, threshold, limit
        )

        # Format results for consistency
        # Note: similarity calculation is already done in the database query (1 - distance)
        candidates = []
        for doc in similar_docs:
            similarity = 1 - doc["similarity_distance"]
            candidates.append(
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "summary": doc["summary"],
                    "similarity_score": similarity,
                    "distance": doc["similarity_distance"],
                }
            )

        return candidates

    async def _stage2_chunk_retrieval(
        self,
        query_embedding: List[float],
        query_text: str,
        document_ids: List[int],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Stage 2: Find best chunks from candidate documents using hybrid search

        Args:
            query_embedding: Query vector
            query_text: Query text for keyword matching
            document_ids: List of candidate document IDs from stage 1
            limit: Maximum chunks to return

        Returns:
            List of chunk matches with document context and hybrid scores
        """
        if not document_ids:
            return []

        # Search chunks across all candidate documents using hybrid approach
        # Combines semantic similarity (embedding) with keyword matching (PGroonga)
        query = """
            WITH all_chunks AS (
                SELECT
                    dc.id, dc.content, dc.document_id,
                    d.title, d.summary,
                    -- Semantic score using embedding similarity
                    (1 - (dc.embedding <=> %s::vector)) AS semantic_score,
                    (dc.embedding <=> %s::vector) as distance
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.document_id = ANY(%s)
            ),
            matching_chunks AS (
                SELECT
                    dc.id,
                    pgroonga_score(dc.tableoid, dc.ctid) AS keyword_score
                FROM document_chunks dc
                WHERE dc.content &@~ %s
                  AND dc.document_id = ANY(%s)
            )
            SELECT
                ac.id, ac.content, ac.document_id, ac.title, ac.summary,
                ac.semantic_score,
                COALESCE(mc.keyword_score, 0) AS keyword_score,
                ac.distance,
                -- Combined hybrid score (weighted average)
                (0.7 * ac.semantic_score + 0.3 * LEAST(COALESCE(mc.keyword_score, 0) / 10.0, 1.0)) AS hybrid_score
            FROM all_chunks ac
            LEFT JOIN matching_chunks mc ON ac.id = mc.id
            ORDER BY hybrid_score DESC
            LIMIT %s
        """

        async with self.connection.cursor() as cur:
            await cur.execute(
                query,
                (
                    query_embedding,
                    query_embedding,
                    document_ids,
                    query_text,
                    document_ids,
                    limit,
                ),
            )
            results = await cur.fetchall()

        # Format results with hybrid scoring
        chunk_matches = []
        for result in results:
            chunk_matches.append(
                {
                    "chunk_id": result[0],
                    "content": result[1],
                    "document_id": result[2],
                    "document_title": result[3],
                    "document_summary": result[4],
                    "semantic_score": result[5],
                    "keyword_score": result[6],
                    "distance": result[7],
                    "hybrid_score": result[8],
                    "similarity_score": result[5],  # Keep for backward compatibility
                }
            )

        return chunk_matches

    async def search_with_context(
        self,
        query_embedding: List[float],
        query_text: str,
        context_window: int = 1,
        **kwargs,
    ) -> RetrievalResult:
        """
        Search with additional context chunks around matches

        Args:
            query_embedding: Query vector
            query_text: Query text for keyword matching
            context_window: Number of adjacent chunks to include on each side
            **kwargs: Other arguments passed to search()

        Returns:
            RetrievalResult with expanded context chunks
        """
        # First get the basic results
        result = await self.search(query_embedding, query_text, **kwargs)

        if not result.chunks or context_window <= 0:
            return result

        # Expand each chunk with context
        expanded_chunks = []
        for chunk in result.chunks:
            expanded_chunk = await self._get_chunk_with_context(
                chunk["chunk_id"], chunk["document_id"], context_window
            )
            expanded_chunks.append(expanded_chunk)

        # Update result with expanded chunks
        result.chunks = expanded_chunks
        return result

    async def _get_chunk_with_context(
        self, chunk_id: int, document_id: int, context_window: int
    ) -> Dict[str, Any]:
        """
        Get a chunk with surrounding context chunks

        Args:
            chunk_id: ID of the main chunk
            document_id: Document ID
            context_window: Number of chunks on each side

        Returns:
            Dict with main chunk and context
        """
        # Get all chunks for the document, ordered by ID (which approximates order)
        all_chunks = await self.chunk_repo.get_chunks_by_document_id(document_id)

        # Find the index of our target chunk
        target_idx = None
        for i, chunk in enumerate(all_chunks):
            if chunk["id"] == chunk_id:
                target_idx = i
                break

        if target_idx is None:
            # Fallback: return just the chunk
            return await self.chunk_repo.get_chunk_by_id(chunk_id)

        # Get context window
        start_idx = max(0, target_idx - context_window)
        end_idx = min(len(all_chunks), target_idx + context_window + 1)
        context_chunks = all_chunks[start_idx:end_idx]

        # Mark the target chunk
        target_chunk = all_chunks[target_idx]

        return {
            "main_chunk": target_chunk,
            "context_chunks": context_chunks,
            "context_window_size": context_window,
            "total_context_chunks": len(context_chunks),
        }

    async def get_retrieval_stats(self) -> Dict[str, Any]:
        """Get statistics about the retrieval system"""
        # Get document and chunk counts
        sample_docs = await self.doc_repo.get_all_documents(limit=1000)
        total_docs = len(sample_docs)

        total_chunks = 0
        for doc in sample_docs:
            chunk_count = await self.chunk_repo.get_chunk_count_by_document_id(
                doc["id"]
            )
            total_chunks += chunk_count

        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "avg_chunks_per_document": total_chunks / total_docs
            if total_docs > 0
            else 0,
            "stage1_threshold": self.stage1_threshold,
            "stage1_document_limit": self.stage1_limit,
            "stage2_chunk_limit": self.stage2_limit,
            "search_space_reduction": f"{(self.stage1_limit / max(1, total_docs)) * 100:.1f}%"
            if total_docs > 0
            else "N/A",
        }
