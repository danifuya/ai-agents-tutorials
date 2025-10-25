from typing import List, Dict, Any, Optional
from psycopg import AsyncConnection
from dataclasses import dataclass

from app.db.repositories.document_repository import DocumentRepository
from app.db.repositories.document_chunks_repository import DocumentChunksRepository
from app.rag.chunking.markdown_chunker import GFMContextPathChunker, ChunkerOptions
from app.rag.embeddings.embedding_generator import EmbeddingGenerator
from app.rag.storage.llm_summarizer import LLMSummarizer


@dataclass
class StorageResult:
    """Result of document storage operation"""

    document_id: int
    title: str
    summary: str
    chunk_ids: List[int]
    total_chunks: int
    total_tokens: int
    processing_time: float


@dataclass
class ChunkInfo:
    """Information about a stored chunk"""

    chunk_id: int
    content: str
    tokens_used: int


class DocumentStore:
    """
    Document storage and management class that orchestrates:
    1. Document chunking
    2. Embedding generation  
    3. Database storage via repositories

    This class provides CRUD operations for documents and chunks.
    For search functionality, use the retrieval pipeline components.
    """

    def __init__(
        self,
        db_connection: AsyncConnection,
        embedding_provider: str = "local",
        embedding_api_key: Optional[str] = None,
        max_chunk_tokens: int = 512,
        max_chunk_words: int = 200,
        llm_model: str = "gpt-4o-mini",
        use_llm_summary: bool = True,
    ):
        """
        Initialize DocumentStore with database connection and configuration

        Args:
            db_connection: Active psycopg3 connection
            embedding_provider: Provider for embeddings ("openai", "jina", "local")
            embedding_api_key: API key for external providers (if needed)
            max_chunk_tokens: Maximum tokens per chunk
            max_chunk_words: Maximum words per chunk
            llm_model: OpenAI model for summary generation ("gpt-4o-mini", "gpt-4o", etc.)
            use_llm_summary: Whether to use LLM for summary generation (True) or simple extraction (False)
        """
        # Database repositories
        self.doc_repo = DocumentRepository(db_connection)
        self.chunk_repo = DocumentChunksRepository(db_connection)

        # RAG components
        chunker_options = ChunkerOptions(
            max_tokens_per_chunk=max_chunk_tokens, max_words_per_chunk=max_chunk_words
        )
        self.chunker = GFMContextPathChunker(chunker_options)
        self.embedder = EmbeddingGenerator(provider=embedding_provider)

        # LLM summarizer (optional)
        self.use_llm_summary = use_llm_summary
        if use_llm_summary:
            self.summarizer = LLMSummarizer(model=llm_model)

    async def store_document(
        self, title: str, content: str, generate_summary: bool = True
    ) -> StorageResult:
        """
        Store a document with automatic chunking and embedding generation

        Args:
            title: Document title
            content: Document content (markdown format)
            generate_summary: Whether to auto-generate summary from content

        Returns:
            StorageResult with document_id, chunk_ids, and processing stats
        """
        import time

        start_time = time.time()

        # Step 1: Generate or use provided summary
        if generate_summary:
            if self.use_llm_summary and hasattr(self, "summarizer"):
                summary_result = self.summarizer.generate_summary(content, title)
                if not summary_result.success:
                    raise ValueError(
                        f"LLM summary generation failed: {summary_result.error_message}"
                    )
                summary = summary_result.summary
        else:
            # Use first 200 characters as fallback summary
            summary = content[:200].strip() + ("..." if len(content) > 200 else "")

        # Step 2: Generate embedding for document summary
        summary_embedding_result = self.embedder.embed(summary)

        # Step 3: Store document in database
        document_id = await self.doc_repo.create_document(
            title=title,
            summary=summary,
            summary_embedding=summary_embedding_result.embedding,
        )

        # Step 4: Chunk the document content
        chunk_texts = self.chunker.chunk(content, title)

        # Step 5: Generate embeddings for all chunks
        if chunk_texts:
            batch_embedding_result = self.embedder.embed_batch(chunk_texts)

            # Step 6: Store chunks with embeddings
            chunk_data = []
            for i, chunk_text in enumerate(chunk_texts):
                chunk_data.append(
                    {
                        "content": chunk_text,
                        "embedding": batch_embedding_result.embeddings[i],
                        "document_id": document_id,
                    }
                )

            chunk_ids = await self.chunk_repo.create_chunks_batch(chunk_data)
            total_tokens = (
                batch_embedding_result.total_tokens
                + summary_embedding_result.tokens_used
            )
        else:
            chunk_ids = []
            total_tokens = summary_embedding_result.tokens_used

        processing_time = time.time() - start_time

        return StorageResult(
            document_id=document_id,
            title=title,
            summary=summary,
            chunk_ids=chunk_ids,
            total_chunks=len(chunk_ids),
            total_tokens=total_tokens,
            processing_time=processing_time,
        )

    async def get_document_with_chunks(
        self, document_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a document with all its chunks

        Args:
            document_id: ID of document to retrieve

        Returns:
            Document dict with chunks list, or None if not found
        """
        # Get document
        document = await self.doc_repo.get_document_by_id(document_id)
        if not document:
            return None

        # Get all chunks for this document
        chunks = await self.chunk_repo.get_chunks_by_document_id(document_id)

        return {"document": document, "chunks": chunks, "chunk_count": len(chunks)}

    async def delete_document(self, document_id: int) -> bool:
        """
        Delete document and all its chunks

        Args:
            document_id: ID of document to delete

        Returns:
            True if document was deleted, False if not found
        """
        # Delete chunks first (though they should cascade delete)
        await self.chunk_repo.delete_chunks_by_document_id(document_id)

        # Delete document
        return await self.doc_repo.delete_document(document_id)


    async def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored documents and chunks

        Returns:
            Dictionary with storage statistics
        """
        # Get sample of documents to count
        documents = await self.doc_repo.get_all_documents(limit=1000)
        total_documents = len(documents)

        # Count total chunks across all documents
        total_chunks = 0
        if documents:
            for doc in documents:
                chunk_count = await self.chunk_repo.get_chunk_count_by_document_id(
                    doc["id"]
                )
                total_chunks += chunk_count

        return {
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "avg_chunks_per_document": total_chunks / total_documents
            if total_documents > 0
            else 0,
            "embedding_provider": self.embedder.provider.name,
        }
