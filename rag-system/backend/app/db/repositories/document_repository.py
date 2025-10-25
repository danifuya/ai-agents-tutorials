from typing import List, Dict, Any, Optional
from psycopg import AsyncConnection
import json


class DocumentRepository:
    """Repository for document table operations using psycopg3"""

    def __init__(self, connection: AsyncConnection):
        self.connection = connection

    async def create_document(
        self, title: str, summary: str, summary_embedding: List[float]
    ) -> int:
        """
        Create a new document record with summary embedding.

        Args:
            title: Document title
            summary: Document summary/description
            summary_embedding: Vector embedding of the summary (1024 dimensions)

        Returns:
            id of the created document
        """
        query = """
            INSERT INTO documents (title, summary, summary_embedding)
            VALUES (%s, %s, %s)
            RETURNING id
        """

        async with self.connection.cursor() as cur:
            await cur.execute(query, (title, summary, summary_embedding))
            result = await cur.fetchone()
            await self.connection.commit()

        return result[0]

    async def get_document_by_id(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        query = """
            SELECT id, title, summary, summary_embedding
            FROM documents 
            WHERE id = %s
        """

        async with self.connection.cursor() as cur:
            await cur.execute(query, (document_id,))
            result = await cur.fetchone()

        if result:
            return {
                "id": result[0],
                "title": result[1],
                "summary": result[2],
                "summary_embedding": result[3],
            }

        return None

    async def get_documents_by_title(self, title: str) -> List[Dict[str, Any]]:
        """Get documents by title (partial match)"""
        query = """
            SELECT id, title, summary, summary_embedding
            FROM documents 
            WHERE title ILIKE %s
        """

        async with self.connection.cursor() as cur:
            await cur.execute(query, (f"%{title}%",))
            results = await cur.fetchall()

        documents = []
        for result in results:
            documents.append(
                {
                    "id": result[0],
                    "title": result[1],
                    "summary": result[2],
                    "summary_embedding": result[3],
                }
            )

        return documents

    async def update_document_title(self, document_id: int, title: str) -> bool:
        """Update document title"""
        query = """
            UPDATE documents 
            SET title = %s
            WHERE id = %s
        """

        async with self.connection.cursor() as cur:
            await cur.execute(query, (title, document_id))
            await self.connection.commit()
            return cur.rowcount == 1

    async def update_document_summary(
        self, document_id: int, summary: str, summary_embedding: List[float]
    ) -> bool:
        """Update document summary and its embedding"""
        query = """
            UPDATE documents 
            SET summary = %s, summary_embedding = %s
            WHERE id = %s
        """

        async with self.connection.cursor() as cur:
            await cur.execute(query, (summary, summary_embedding, document_id))
            await self.connection.commit()
            return cur.rowcount == 1

    async def delete_document(self, document_id: int) -> bool:
        """Delete document and all related content (chunks will cascade delete)"""
        query = "DELETE FROM documents WHERE id = %s"

        async with self.connection.cursor() as cur:
            await cur.execute(query, (document_id,))
            await self.connection.commit()
            return cur.rowcount == 1

    async def search_documents_by_summary_similarity(
        self, query_embedding: List[float], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search documents by summary embedding similarity using cosine distance

        Args:
            query_embedding: The query vector to search against
            limit: Maximum number of results to return

        Returns:
            List of documents ordered by similarity (most similar first)
        """
        query = """
            SELECT id, title, summary,
                   (summary_embedding <=> %s::vector) as distance
            FROM documents 
            ORDER BY summary_embedding <=> %s::vector
            LIMIT %s
        """

        async with self.connection.cursor() as cur:
            await cur.execute(query, (query_embedding, query_embedding, limit))
            results = await cur.fetchall()

        documents = []
        for result in results:
            documents.append(
                {
                    "id": result[0],
                    "title": result[1],
                    "summary": result[2],
                    "similarity_distance": result[3],
                }
            )

        return documents

    async def search_documents_hybrid(
        self,
        query_embedding: List[float],
        query_text: str,
        similarity_threshold: float = 0.5,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining embedding similarity and full-text search

        Args:
            query_embedding: Query embedding vector
            query_text: Query text for full-text search
            similarity_threshold: Minimum similarity score (1-distance) to include
            limit: Maximum number of results to return

        Returns:
            List of documents with similarity distances
        """
        query = """
            SELECT 
                id,
                title, 
                summary,
                (summary_embedding <=> %s::vector) as similarity_distance
            FROM documents
            WHERE (
                (1 - (summary_embedding <=> %s::vector)) >= %s
                OR summary &@~ %s
            )
            ORDER BY (summary_embedding <=> %s::vector) ASC
            LIMIT %s
        """

        async with self.connection.cursor() as cur:
            await cur.execute(
                query,
                (
                    query_embedding,  # For similarity calculation
                    query_embedding,  # For similarity threshold
                    similarity_threshold,  # Similarity threshold
                    query_text,  # Summary pgroonga pattern
                    query_embedding,  # For final ordering
                    limit,
                ),
            )
            results = await cur.fetchall()

        documents = []
        for result in results:
            documents.append(
                {
                    "id": result[0],
                    "title": result[1],
                    "summary": result[2],
                    "similarity_distance": result[3],
                }
            )

        return documents

    async def get_all_documents(
        self, offset: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get all documents with pagination"""
        query = """
            SELECT id, title, summary, summary_embedding
            FROM documents 
            ORDER BY id
            OFFSET %s LIMIT %s
        """

        async with self.connection.cursor() as cur:
            await cur.execute(query, (offset, limit))
            results = await cur.fetchall()

        documents = []
        for result in results:
            documents.append(
                {
                    "id": result[0],
                    "title": result[1],
                    "summary": result[2],
                    "summary_embedding": result[3],
                }
            )

        return documents
